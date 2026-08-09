#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Korean glyphs by reusing existing, unused 3-byte BMP metrics.

No metric table bytes are changed.  Each Korean character is encoded as an
unused BMP proxy whose original metric already points at a reclaimable slot.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import ImageFont
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다


COMPACT_ALIASES = {
    "본": 0x00A4,
    "다": 0x00A6,
    "이": 0x00A8,
    "지": 0x00B4,
    "기": 0x00F7,
    "는": 0x041C,
    "하": 0x041E,
}
KOREAN_ADVANCE = 22
SPACE_ADVANCE = 10


def load_builder():
    path = Path(__file__).with_name("16_build_korean_font.py")
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def cell_bytes(font: bytes | bytearray, slot: int, builder) -> bytes:
    cell_x = slot % builder.PHYSICAL_CELLS_X
    cell_y = slot // builder.PHYSICAL_CELLS_X
    chunks = []
    for by in range(builder.CELL_SIZE // 4):
        for bx in range(builder.CELL_SIZE // 4):
            block_x = cell_x * (builder.CELL_SIZE // 4) + bx
            block_y = cell_y * (builder.CELL_SIZE // 4) + by
            offset = builder.TEXTURE_OFFSET + (
                block_y * builder.BLOCKS_X + block_x
            ) * 16
            chunks.append(bytes(font[offset : offset + 16]))
    return b"".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default="work_ogmd/font_dump/font.bin")
    parser.add_argument("--translated-tsv", default="work_ogmd/translated")
    parser.add_argument("--used-chars", default="work_ogmd/extract_all/used_chars.txt")
    parser.add_argument(
        "--extra-jsonl",
        default="work_ogmd/general2d_translation/wtd_strings.jsonl",
        help="Optional JSONL rows whose ko field contributes additional glyphs",
    )
    parser.add_argument("--out-dir", default="work_ogmd/korean_build_v3")
    parser.add_argument("--face", default=config.KOREAN_FONT_BOLD)
    parser.add_argument("--size", type=int, default=28)
    args = parser.parse_args()

    builder = load_builder()
    out_dir = Path(args.out_dir)
    encoded_dir = out_dir / "translated_proxy"
    out_dir.mkdir(parents=True, exist_ok=True)
    encoded_dir.mkdir(parents=True, exist_ok=True)

    original = Path(args.font).read_bytes()
    font = bytearray(original)
    space_metric_off = builder.metric_offset(original, ord(" "))
    if space_metric_off is None:
        raise AssertionError("ASCII space metric is missing")
    font[space_metric_off : space_metric_off + 2] = SPACE_ADVANCE.to_bytes(
        2, "big"
    )
    translated_rows, translated_chars = builder.read_tsv_texts(
        Path(args.translated_tsv)
    )
    extra_path = Path(args.extra_jsonl)
    if extra_path.exists():
        for line in extra_path.read_text(encoding="utf-8").splitlines():
            translated_chars.update(json.loads(line)["ko"])
    source_chars = set(Path(args.used_chars).read_text(encoding="utf-8"))
    korean_chars = sorted(ch for ch in translated_chars if builder.is_korean(ch))

    protected_cps = builder.protect_codepoints(source_chars, translated_chars)
    protected_slots = {
        slot
        for cp in protected_cps
        if (slot := builder.metric_slot(original, cp)) not in (None, 0)
    }
    occupied_cps = {ord(ch) for ch in source_chars | translated_chars}

    # Prefer CJK proxies for easier inspection, then use the remaining 3-byte
    # BMP pages.  Keep exactly one proxy per original metric slot.
    raw_candidates = []
    for cp in range(0x800, 0x10000):
        if 0xD800 <= cp <= 0xDFFF or cp in occupied_cps:
            continue
        slot = builder.metric_slot(original, cp)
        if slot in (None, 0) or slot in protected_slots:
            continue
        raw_candidates.append((0 if 0x4E00 <= cp <= 0x9FFF else 1, cp, slot))

    proxy_by_slot: dict[int, int] = {}
    for _priority, cp, slot in sorted(raw_candidates):
        proxy_by_slot.setdefault(slot, cp)
    candidates = [(cp, slot) for slot, cp in sorted(proxy_by_slot.items())]
    if len(candidates) < len(korean_chars):
        raise ValueError(
            f"safe existing-metric capacity {len(candidates)} < {len(korean_chars)}"
        )

    face = ImageFont.truetype(args.face, args.size)
    char_map: dict[str, str] = {}
    records = []
    metric_edits = set()
    for ch, (proxy_cp, slot) in zip(korean_chars, candidates):
        builder.inject_cell(font, slot, builder.render_glyph(ch, face))
        metric_off = builder.metric_offset(original, proxy_cp)
        font[metric_off : metric_off + 2] = KOREAN_ADVANCE.to_bytes(2, "big")
        metric_edits.add(metric_off)
        proxy = chr(proxy_cp)
        char_map[ch] = proxy
        records.append(
            {
                "hangul": ch,
                "hangul_cp": f"U+{ord(ch):04X}",
                "proxy": proxy,
                "proxy_cp": f"U+{proxy_cp:04X}",
                "slot": slot,
                "metric": original[
                    builder.metric_offset(original, proxy_cp) :
                    builder.metric_offset(original, proxy_cp) + 4
                ].hex(),
            }
        )

    compact_aliases = {}
    for ch, proxy_cp in COMPACT_ALIASES.items():
        slot = builder.metric_slot(original, proxy_cp)
        if slot in (None, 0) or slot in protected_slots or slot in {
            row["slot"] for row in records
        }:
            raise AssertionError(
                f"unsafe compact alias U+{proxy_cp:04X} -> slot {slot}; "
                f"protected={slot in protected_slots}, "
                f"korean={slot in {row['slot'] for row in records}}"
            )
        builder.inject_cell(font, slot, builder.render_glyph(ch, face))
        metric_off = builder.metric_offset(original, proxy_cp)
        font[metric_off : metric_off + 2] = KOREAN_ADVANCE.to_bytes(2, "big")
        metric_edits.add(metric_off)
        compact_aliases[ch] = {
            "proxy": chr(proxy_cp),
            "proxy_cp": f"U+{proxy_cp:04X}",
            "slot": slot,
        }

    expected_header = bytearray(original[: builder.TEXTURE_OFFSET])
    expected_header[space_metric_off : space_metric_off + 2] = (
        SPACE_ADVANCE.to_bytes(2, "big")
    )
    for metric_off in metric_edits:
        expected_header[metric_off : metric_off + 2] = (
            KOREAN_ADVANCE.to_bytes(2, "big")
        )
    if font[: builder.TEXTURE_OFFSET] != expected_header:
        raise AssertionError("unexpected metric/header change")
    changed_protected = [
        slot
        for slot in protected_slots
        if cell_bytes(font, slot, builder) != cell_bytes(original, slot, builder)
    ]
    if changed_protected:
        raise AssertionError(
            f"protected texture slots changed: {changed_protected[:20]}"
        )

    font_path = out_dir / "font_ko.bin"
    font_path.write_bytes(font)
    with (out_dir / "korean_font_map.tsv").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("hangul\thangul_cp\tproxy\tproxy_cp\tslot\tmetric\n")
        for row in records:
            stream.write(
                f"{row['hangul']}\t{row['hangul_cp']}\t{row['proxy']}\t"
                f"{row['proxy_cp']}\t{row['slot']}\t{row['metric']}\n"
            )

    with (out_dir / "compact_aliases.tsv").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("hangul\tproxy\tproxy_cp\tslot\n")
        for ch, row in compact_aliases.items():
            stream.write(
                f"{ch}\t{row['proxy']}\t{row['proxy_cp']}\t{row['slot']}\n"
            )

    for src_path in sorted(Path(args.translated_tsv).glob("batch_*.tsv")):
        output_lines = []
        for line in src_path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            encoded = builder.encode_text(text, char_map)
            if any(builder.is_korean(ch) for ch in encoded):
                raise AssertionError(f"UID {uid}: unencoded Korean character")
            if len(encoded.encode("utf-8")) != len(text.encode("utf-8")):
                raise AssertionError(f"UID {uid}: UTF-8 length changed")
            output_lines.append(f"{uid}\t{encoded}")
        (encoded_dir / src_path.name).write_text(
            "\n".join(output_lines) + "\n", encoding="utf-8", newline="\n"
        )

    manifest = {
        "font_output": str(font_path),
        "font_sha256": hashlib.sha256(font).hexdigest(),
        "korean_glyphs": len(korean_chars),
        "protected_slots": len(protected_slots),
        "existing_metric_candidates": len(candidates),
        "remaining_candidates": len(candidates) - len(korean_chars),
        "compact_aliases": compact_aliases,
        "metric_region_unchanged": False,
        "metric_advance": KOREAN_ADVANCE,
        "space_advance": SPACE_ADVANCE,
        "metric_edits": len(metric_edits),
        "changed_protected_slots": 0,
        "translation_uids": len(translated_rows),
    }
    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
