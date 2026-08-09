#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OGMD FTTF에 한글 글리프를 주입하고 번역문을 대체 CJK 코드로 인코딩한다.

게임의 FTTF는 BMP Unicode 페이지 테이블만 가지며 Hangul Syllables(U+AC00~)
페이지가 없다. 따라서 원문에서 쓰지 않는 CJK 코드포인트를 대체 문자로
사용하고, 해당 메트릭이 새 한글 글리프 셀을 가리키도록 한다.

아틀라스는 1024x4096 DXT5, 32x32 셀 4096개이며 블록은 선형 배열이다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다


PAGE_DIR_OFFSET = 0x54
TEXTURE_OFFSET = 0x18600
# The game samples the DXT5 payload with a 1024px physical row stride.
ATLAS_WIDTH = 1024
ATLAS_HEIGHT = 4096
CELL_SIZE = 32
METRIC_CELLS_X = 32
METRIC_CELLS_Y = 128
PHYSICAL_CELLS_X = ATLAS_WIDTH // CELL_SIZE
PHYSICAL_CELLS_Y = ATLAS_HEIGHT // CELL_SIZE
BLOCKS_X = ATLAS_WIDTH // 4
FONT_SLOTS = METRIC_CELLS_X * METRIC_CELLS_Y


def page_offset(font: bytes | bytearray, cp: int) -> int:
    if not 0 <= cp <= 0xFFFF:
        return 0
    p = PAGE_DIR_OFFSET + (cp >> 8) * 4
    return struct.unpack(">I", font[p : p + 4])[0]


def metric_offset(font: bytes | bytearray, cp: int) -> int | None:
    page = page_offset(font, cp)
    if not page:
        return None
    return page + (cp & 0xFF) * 4


def metric_slot(font: bytes | bytearray, cp: int) -> int | None:
    off = metric_offset(font, cp)
    if off is None:
        return None
    x, y = font[off + 2], font[off + 3]
    if x >= METRIC_CELLS_X or y >= METRIC_CELLS_Y:
        return None
    return y * METRIC_CELLS_X + x


def read_tsv_texts(folder: Path) -> tuple[dict[int, str], set[str]]:
    rows: dict[int, str] = {}
    chars: set[str] = set()
    for path in sorted(folder.glob("batch_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            rows[int(uid)] = text
            chars.update(text)
    return rows, chars


def is_korean(ch: str) -> bool:
    cp = ord(ch)
    return 0xAC00 <= cp <= 0xD7A3 or 0x3130 <= cp <= 0x318F


def protect_codepoints(source_chars: set[str], translated_chars: set[str]) -> set[int]:
    protected = {ord(ch) for ch in source_chars}
    protected.update(ord(ch) for ch in translated_chars if not is_korean(ch))

    # 추출 누락 가능성이 있는 고정 UI용 기본 문자군도 보존한다.
    for lo, hi in (
        (0x20, 0x7E),
        (0x2000, 0x26FF),
        (0x3000, 0x30FF),
        (0xFF00, 0xFFEF),
    ):
        protected.update(range(lo, hi + 1))
    return protected


def render_glyph(ch: str, face: ImageFont.FreeTypeFont) -> Image.Image:
    image = Image.new("L", (CELL_SIZE, CELL_SIZE), 0)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), ch, font=face)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = (CELL_SIZE - width) // 2 - box[0]
    y = (CELL_SIZE - height) // 2 - box[1]
    draw.text((x, y), ch, font=face, fill=255)
    return image


def dxt5_alpha_block(values: list[int]) -> bytes:
    """4x4 알파 값을 DXT5 블록으로 근사 인코딩한다."""
    a0 = max(values)
    a1 = min(values)
    if a0 == a1:
        palette = (a0,) * 8
    else:
        # a0 > a1인 8-alpha 모드
        palette = (
            a0,
            a1,
            (6 * a0 + a1) // 7,
            (5 * a0 + 2 * a1) // 7,
            (4 * a0 + 3 * a1) // 7,
            (3 * a0 + 4 * a1) // 7,
            (2 * a0 + 5 * a1) // 7,
            (a0 + 6 * a1) // 7,
        )

    bits = 0
    for i, value in enumerate(values):
        idx = min(range(8), key=lambda j: abs(palette[j] - value))
        bits |= idx << (3 * i)
    # 게임은 텍스트 색상을 별도로 적용한다. 컬러 블록은 원본처럼 0으로 둔다.
    # The shader multiplies atlas RGB by the requested text color.  Use white
    # as the neutral base; a black block forces every injected glyph to black.
    white_color_block = b"\xff\xff\xff\xff\0\0\0\0"
    return bytes((a0, a1)) + bits.to_bytes(6, "little") + white_color_block


def inject_cell(font: bytearray, slot: int, glyph: Image.Image) -> None:
    cell_x = slot % PHYSICAL_CELLS_X
    cell_y = slot // PHYSICAL_CELLS_X
    pix = glyph.load()
    for local_by in range(CELL_SIZE // 4):
        for local_bx in range(CELL_SIZE // 4):
            values = []
            for py in range(4):
                for px in range(4):
                    values.append(pix[local_bx * 4 + px, local_by * 4 + py])
            block_x = cell_x * (CELL_SIZE // 4) + local_bx
            block_y = cell_y * (CELL_SIZE // 4) + local_by
            block_index = block_y * BLOCKS_X + block_x
            dst = TEXTURE_OFFSET + block_index * 16
            font[dst : dst + 16] = dxt5_alpha_block(values)


def encode_text(text: str, char_map: dict[str, str]) -> str:
    return "".join(char_map.get(ch, ch) for ch in text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="work_ogmd/font_dump/font.bin")
    ap.add_argument("--source-tsv", default="work_ogmd/extract/for_chatgpt")
    ap.add_argument("--translated-tsv", default="work_ogmd/translated")
    ap.add_argument(
        "--used-chars",
        default="work_ogmd/extract_all/used_chars.txt",
        help="Optional all-entry scan output to add to the protected character set",
    )
    ap.add_argument("--out-dir", default="work_ogmd/korean_build")
    ap.add_argument("--face", default=config.KOREAN_FONT_BOLD)
    ap.add_argument("--size", type=int, default=28)
    args = ap.parse_args()

    font_path = Path(args.font)
    source_dir = Path(args.source_tsv)
    translated_dir = Path(args.translated_tsv)
    out_dir = Path(args.out_dir)
    encoded_dir = out_dir / "translated_proxy"
    out_dir.mkdir(parents=True, exist_ok=True)
    encoded_dir.mkdir(parents=True, exist_ok=True)

    original = font_path.read_bytes()
    font = bytearray(original)
    if len(font) != TEXTURE_OFFSET + 0x400000:
        raise ValueError(f"예상하지 못한 font.bin 크기: {len(font):#x}")

    source_rows, source_chars = read_tsv_texts(source_dir)
    translated_rows, translated_chars = read_tsv_texts(translated_dir)
    used_chars_path = Path(args.used_chars)
    if used_chars_path.exists():
        source_chars.update(used_chars_path.read_text(encoding="utf-8"))
    if source_rows.keys() != translated_rows.keys():
        raise ValueError("원문/번역 UID 집합이 다릅니다")

    korean_chars = sorted(ch for ch in translated_chars if is_korean(ch))
    protected_cps = protect_codepoints(source_chars, translated_chars)
    protected_slots = {
        slot
        for cp in protected_cps
        if (slot := metric_slot(original, cp)) not in (None, 0)
    }
    free_slots = [slot for slot in range(1, FONT_SLOTS) if slot not in protected_slots]

    # 실제 텍스트에 존재하지 않고 페이지 테이블이 준비된 CJK 코드포인트.
    occupied_cps = {ord(ch) for ch in source_chars | translated_chars}
    proxy_cps = [
        cp
        for cp in range(0x4E00, 0xA000)
        if cp not in occupied_cps and metric_offset(original, cp) is not None
    ]

    capacity = min(len(free_slots), len(proxy_cps))
    if len(korean_chars) > capacity:
        raise ValueError(
            f"한글 글리프 용량 부족: 필요 {len(korean_chars)}, 사용 가능 {capacity}"
        )

    face = ImageFont.truetype(args.face, args.size)
    char_map: dict[str, str] = {}
    records = []
    preview = Image.new("L", (16 * 64, 8 * 64), 0)
    preview_draw = ImageDraw.Draw(preview)
    label_face = ImageFont.truetype(config.KOREAN_FONT, 10)

    for i, ch in enumerate(korean_chars):
        proxy_cp = proxy_cps[i]
        proxy = chr(proxy_cp)
        slot = free_slots[i]
        x = slot % METRIC_CELLS_X
        y = slot // METRIC_CELLS_X
        glyph = render_glyph(ch, face)
        inject_cell(font, slot, glyph)

        off = metric_offset(font, proxy_cp)
        assert off is not None
        font[off : off + 4] = bytes((0, CELL_SIZE, x, y))
        char_map[ch] = proxy
        records.append(
            {
                "hangul": ch,
                "hangul_cp": f"U+{ord(ch):04X}",
                "proxy": proxy,
                "proxy_cp": f"U+{proxy_cp:04X}",
                "slot": slot,
                "x": x,
                "y": y,
            }
        )

        if i < 128:
            px = (i % 16) * 64
            py = (i // 16) * 64
            preview.paste(glyph.resize((48, 48), Image.Resampling.NEAREST), (px, py))
            preview_draw.text((px, py + 50), f"{ord(ch):04X}", font=label_face, fill=180)

    font_out = out_dir / "font_ko.bin"
    font_out.write_bytes(font)
    preview.save(out_dir / "font_ko_preview.png")

    with (out_dir / "korean_font_map.tsv").open("w", encoding="utf-8", newline="\n") as f:
        f.write("hangul\thangul_cp\tproxy\tproxy_cp\tslot\tx\ty\n")
        for r in records:
            f.write(
                f"{r['hangul']}\t{r['hangul_cp']}\t{r['proxy']}\t"
                f"{r['proxy_cp']}\t{r['slot']}\t{r['x']}\t{r['y']}\n"
            )

    for src_path in sorted(translated_dir.glob("batch_*.tsv")):
        output_lines = []
        for line in src_path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            output_lines.append(f"{uid}\t{encode_text(text, char_map)}")
        (encoded_dir / src_path.name).write_text(
            "\n".join(output_lines) + "\n", encoding="utf-8", newline="\n"
        )

    # 모든 한글이 대체됐고 UTF-8 바이트 길이가 유지되는지 검사한다.
    for uid, text in translated_rows.items():
        encoded = encode_text(text, char_map)
        if any(is_korean(ch) for ch in encoded):
            raise AssertionError(f"UID {uid}: 인코딩되지 않은 한글")
        if len(encoded.encode("utf-8")) != len(text.encode("utf-8")):
            raise AssertionError(f"UID {uid}: 대체 후 UTF-8 길이 변화")

    manifest = {
        "font_source": str(font_path),
        "font_output": str(font_out),
        "font_size": len(font),
        "font_sha256": hashlib.sha256(font).hexdigest(),
        "face": args.face,
        "face_size": args.size,
        "korean_glyphs": len(korean_chars),
        "protected_slots": len(protected_slots),
        "free_slots_before_injection": len(free_slots),
        "remaining_slots": len(free_slots) - len(korean_chars),
        "proxy_codepoints_available": len(proxy_cps),
        "translation_uids": len(translated_rows),
    }
    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
