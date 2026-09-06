#!/usr/bin/env python3
"""전투 HUD 아틀라스(cosl.dds) 공격 종류 라벨 9개 한글화 (2026-09-06).

v20260816 의 이미지 한글화는 이 파일의 y=96..282 띠를 가로 전체로 다시 그려
같은 띠에 있던 HP/EN 작은 숫자 폰트, EN/HP 라벨, 기체명 프레임을 지웠고,
그 결과 전투 HUD 표시가 사라져 배포에서 제외됐다.  144 는 좌표를 잘못 잡아
엉뚱한 자리에 한글을 찍었다.

이 스크립트는 원본 글리프의 알파 경계를 실측한 9개 사각형 안에서만 픽셀을
바꾸고, 그 밖의 모든 픽셀이 소매판과 바이트 단위로 동일함을 검증한 뒤에만
PSARC 로 패킹한다.

  라벨 사각형은 후보 상자를 14px 확장해 재측정했고(첫 측정은 상자 윗변에
  잘려 있었다), 프레임 선이 통과하는 행은 링 검사로 걸러냈다.
  작은 숫자 폰트의 실제 세로 범위는 y=200..221 이고 라벨은 227 부터라
  사이에 5행의 빈 틈이 있다.

렌더 레시피 (원본 全体攻撃 실측):
  맑은 고딕 Bold 28px -> 잉크 높이 32px (한자와 동일), 기울기 dx/dy=0.258,
  채움 (241,241,241), 외곽 (30,40,240) 스트로크 1px + 블러 0.5 + 알파 x0.7.
  4글자+공백 라벨은 한자 4자 폭(109px)보다 넓어 가로만 0.86~0.95 축소한다.
  용어는 jp2ko.json 의 텍스트 번역과 동일하게 맞춘다.

고정 스팬 제약:
  원본은 zlib-9 로 압축되어 블록 여유가 0 이다.  Zopfli 재압축으로 블록당
  +188~+853B 가 생기지만 한글 4개가 겹치는 블록 15 는 그래도 1.2KB 넘쳤다.
  알파를 16단계로 양자화하고 채움/외곽 색을 스냅해 엔트로피를 줄이면
  블록 15 가 +8KB 여유로 바뀐다(시각 차이 없음).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from psarc import PSARC
from sdat import decrypt_stream

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
IMG = ROOT / "image_localization"
SOURCE_DDS = IMG / "extracted_battle/Dat/Battle/Console/Dds/@Ja/cosl.dds"
OUT_DDS = IMG / "localized/Dat/Battle/Console/Dds/@Ja/cosl.dds"
PREVIEW = IMG / "hud_labels_preview_20260906.png"
SOURCE_SDAT = BUILD / "Battle_names_ko_20260825.psarc.sdat"
OUTPUT_SDAT = BUILD / "Battle_hud_labels_ko_20260906.psarc.sdat"
REPORT = BUILD / "hud_labels_20260906_report.json"
ENTRY_PATH = "/Dat/Battle/Console/Dds/@Ja/cosl.dds"

FONT = Path(r"C:\Windows\Fonts\malgunbd.ttf")
SIZE, STROKE, BLUR, HALO, SHEAR = 28, 1, 0.5, 0.7, 0.258
FILL, BLUE = (241, 241, 241), (30, 40, 240)
W, H = 1024, 384

# (한글, 원본 글리프 알파 경계 -- 이 안만 바꾼다)
LABELS = [
    ("콤비네이션 공격", (467, 114, 730, 148)),
    ("더블 어택",       (790, 115, 975, 148)),
    ("맥시멈 브레이크", (313, 155, 549, 188)),
    ("포위 공격",       (312, 194, 421, 227)),
    ("원호 공격",       (457, 194, 566, 228)),
    ("원호 방어",       (17, 227, 126, 259)),   # y=267 프레임 선은 상자 밖
    ("합체 공격",       (159, 227, 268, 261)),
    ("전체 공격",       (305, 236, 415, 269)),
    ("재공격",          (444, 235, 528, 269)),
]
# 절대 바뀌면 안 되는 영역 (실측)
GUARDS = [("HP/EN 작은 숫자", (1, 200, 290, 222)), ("EN/HP 라벨", (548, 237, 582, 264))]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_hud", "163_patch_reports_20260824.py")
finish = PREV.finish


def render(text: str) -> Image.Image:
    font = ImageFont.truetype(str(FONT), SIZE)
    cw, ch = 760, 110
    core = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(core).text((40, 20), text, font=font, fill=FILL + (255,))
    ring = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(ring).text((40, 20), text, font=font, fill=BLUE + (255,),
                              stroke_width=STROKE, stroke_fill=BLUE + (255,))
    ring = ring.filter(ImageFilter.GaussianBlur(BLUR))
    r, g, b, a = ring.split()
    ring = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * HALO))))
    out = Image.alpha_composite(ring, core)
    out = out.transform((cw + int(ch * SHEAR), ch), Image.AFFINE,
                        (1, SHEAR, -SHEAR * ch, 0, 1, 0), Image.BICUBIC)
    return out.crop(out.getbbox())


def quantize(glyph: Image.Image, levels: int = 16) -> Image.Image:
    """알파 16단계 + 색 스냅.  고정 스팬 안에 들어가도록 엔트로피를 줄인다."""
    r, g, b, a = glyph.split()
    step = 255 / (levels - 1)
    a = a.point(lambda v: 0 if v < 8 else 255 if v > 247 else int(round(v / step) * step))
    px_a, px_r, px_g, px_b = a.load(), r.load(), g.load(), b.load()
    for y in range(glyph.height):
        for x in range(glyph.width):
            av = px_a[x, y]
            if av == 0:
                continue
            if av >= 250:
                px_r[x, y], px_g[x, y], px_b[x, y] = FILL
            elif av < 180:
                px_r[x, y], px_g[x, y], px_b[x, y] = BLUE
    return Image.merge("RGBA", (r, g, b, a))


def paint(original: Image.Image) -> tuple[Image.Image, list[dict]]:
    work = original.copy()
    draw = ImageDraw.Draw(work)
    placed = []
    for text, (x0, y0, x1, y1) in LABELS:
        bw, bh = x1 - x0, y1 - y0
        glyph = render(text)
        fx, fy = min(1.0, bw / glyph.width), min(1.0, bh / glyph.height)
        if fx < 1 or fy < 1:
            glyph = glyph.resize((max(1, int(glyph.width * fx)),
                                  max(1, int(glyph.height * fy))), Image.LANCZOS)
        glyph = quantize(glyph)
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(0, 0, 0, 0))
        work.alpha_composite(glyph, (x0 + (bw - glyph.width) // 2, y0 + (bh - glyph.height) // 2))
        placed.append({"text": text, "box": [x0, y0, x1, y1],
                       "rendered": [glyph.width, glyph.height], "x_scale": round(fx, 3)})
    return work, placed


def verify_pixels(original: Image.Image, work: Image.Image) -> dict:
    ob, wb = original.tobytes(), work.tobytes()
    inside = bytearray(W * H)
    for _, (x0, y0, x1, y1) in LABELS:
        for y in range(y0, y1):
            inside[y * W + x0:y * W + x1] = b"\x01" * (x1 - x0)
    outside_changed = sum(1 for i in range(W * H)
                          if not inside[i] and ob[i * 4:i * 4 + 4] != wb[i * 4:i * 4 + 4])
    guards = {}
    for name, (x0, y0, x1, y1) in GUARDS:
        guards[name] = sum(1 for y in range(y0, y1) for x in range(x0, x1)
                           if ob[(y * W + x) * 4:(y * W + x) * 4 + 4] != wb[(y * W + x) * 4:(y * W + x) * 4 + 4])
    if outside_changed or any(guards.values()):
        raise AssertionError(f"상자 밖 변경 {outside_changed}, 보호영역 {guards}")
    return {"outside_changed": outside_changed, "guards_changed": guards}


def main() -> None:
    src = SOURCE_DDS.read_bytes()
    header, raw = src[:128], src[128:]
    original = Image.frombytes("RGBA", (W, H), raw, "raw", "BGRA")
    work, placed = paint(original)
    pixel_report = verify_pixels(original, work)

    payload = work.tobytes("raw", "BGRA")
    if len(payload) != len(raw):
        raise AssertionError("DDS 페이로드 길이 변화")
    new_dds = header + payload
    OUT_DDS.parent.mkdir(parents=True, exist_ok=True)
    OUT_DDS.write_bytes(new_dds)

    band = work.crop((0, 96, 1024, 283))
    bg = Image.new("RGBA", band.size, (40, 40, 40, 255))
    bg.alpha_composite(band)
    bg.convert("RGB").resize((2048, 374), Image.NEAREST).save(PREVIEW)

    # -- PSARC 패킹: v20260826 과 같은 경로 --
    plain = BUILD / "_hud_battle_source.psarc"
    out_plain = BUILD / (plain.stem + "_out.psarc")
    try:
        with SOURCE_SDAT.open("rb") as stream, plain.open("wb") as target:
            logical_size, _ = decrypt_stream(stream, 0, target)
        archive = PSARC(str(plain))
        try:
            entry = archive.manifest().index(ENTRY_PATH) + 1
            current = archive.read_entry(entry)
            if current != src:
                raise AssertionError("입력 SDAT 의 cosl.dds 가 소매판 원본과 다름 -- 체인 확인 필요")
            result = finish(SOURCE_SDAT, OUTPUT_SDAT, plain, {entry: new_dds},
                            logical_size, "Battle.psarc.sdat.orig", fixed_spans=True)
        finally:
            archive.f.close()
    finally:
        for temporary in (plain, out_plain):
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                print(f"임시 파일 제거 실패: {temporary.name} ({error})")

    result.update({"entry": entry, "dds_sha256": hashlib.sha256(new_dds).hexdigest().upper(),
                   "labels": placed, **pixel_report})
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in placed:
        print(f"  {item['text']:10s} box={item['box']} 렌더={item['rendered']} x축소={item['x_scale']}")
    print(f"상자 밖 변경 {pixel_report['outside_changed']} / 보호영역 {pixel_report['guards_changed']}")
    print(f"pack={result.get('pack')}")
    print(f"sha256={result['sha256']}")


if __name__ == "__main__":
    main()
