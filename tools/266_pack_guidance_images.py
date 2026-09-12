#!/usr/bin/env python3
"""한글로 다시 그린 가이던스 본문 15장을 Logic 아카이브에 넣는다.

`/Dat/logic/Resource/summary/Img/@Ja/@ps3/guidance_01~15.dds` (entry 308~322).
967x392, 32비트 무압축 BGRA, 밉맵 없음이라 헤더를 그대로 두고 픽셀만 바꾼다.
크기가 한 바이트도 달라지지 않으므로 제자리 교체다.

입력: 제목까지 번역된 Logic_guidance_ko_20260912.psarc.sdat
출력: Logic_guidance_full_ko_20260912.psarc.sdat
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image

from psarc import PSARC
from sdat import SDATReader, decrypt_stream
from guidance_render import render_page, to_dds, measure
from guidance_pages import PAGES

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_guidance_ko_20260912.psarc.sdat"
OUTPUT = BUILD / "Logic_guidance_full_ko_20260912.psarc.sdat"
REPORT = BUILD / "guidance_images_20260912_report.json"
WORK = ROOT / "guidance_work"
FIRST_ENTRY = 308


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


finish = load("p163_266", "163_patch_reports_20260824.py").finish


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def main() -> None:
    # 배치표 폭 검사부터
    overflow = 0
    for name, spec in PAGES.items():
        for line in spec["lines"]:
            width = measure(line["parts"], line.get("size", 22))
            limit = line.get("limit", 958)
            if line["x"] + width > limit:
                print(f"  ★ {name} y={line['y']} 폭 {line['x'] + width} > {limit}")
                overflow += 1
    if overflow:
        raise SystemExit("폭 초과가 있어 중단한다")

    with SOURCE.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        names = archive.manifest()
        modified: dict[int, bytes] = {}
        rows = []
        for index in range(15):
            entry = FIRST_ENTRY + index
            name = names[entry - 1]
            stem = name.split("/")[-1].replace(".dds", "")
            if stem not in PAGES:
                raise AssertionError(f"배치표에 {stem} 없음")
            template = archive.read_entry(entry)
            height, width = struct.unpack_from("<II", template, 12)
            if (width, height) != (967, 392):
                raise AssertionError(f"{stem}: 크기 {width}x{height}")
            image = render_page(WORK / "orig" / f"{stem}.png", PAGES[stem])
            data = to_dds(image, template)
            if len(data) != len(template):
                raise AssertionError(f"{stem}: 바이트 수 변화")
            if data[:128] != template[:128]:
                raise AssertionError(f"{stem}: DDS 헤더가 바뀜")
            modified[entry] = data
            rows.append({"entry": entry, "file": stem, "lines": len(PAGES[stem]["lines"]),
                         "keep": len(PAGES[stem]["keep"])})
            print(f"  e{entry} {stem}  한글 {len(PAGES[stem]['lines']):2d}줄, "
                  f"원본 보존 {len(PAGES[stem]['keep'])}곳")

    plain = BUILD / "_guidance_img_logic.psarc"
    try:
        with SOURCE.open("rb") as stream, plain.open("wb") as target:
            logical_size, _ = decrypt_stream(stream, 0, target)
        result = finish(SOURCE, OUTPUT, plain, modified, logical_size,
                        "Logic.psarc.sdat.orig", fixed_spans=True)
    finally:
        for temporary in (plain, BUILD / (plain.stem + "_out.psarc")):
            temporary.unlink(missing_ok=True)

    with SOURCE.open("rb") as a, OUTPUT.open("rb") as b:
        A, B = PSARC(SDATReader(a, 0)), PSARC(SDATReader(b, 0))
        changed = sorted(e for e in range(1, A.n) if A.read_entry(e) != B.read_entry(e))
        expected = sorted(modified)
        if changed != expected:
            raise AssertionError(f"예상 밖 변경: {set(changed) ^ set(expected)}")
        for entry in expected:
            out = B.read_entry(entry)
            if len(out) != len(A.read_entry(entry)):
                raise AssertionError(f"e{entry} 크기 변화")
            if out[:128] != A.read_entry(entry)[:128]:
                raise AssertionError(f"e{entry} 헤더 변화")
    print(f"\n대조: entry {expected[0]}~{expected[-1]} 15개만 변경, 크기·헤더 동일")

    REPORT.write_text(json.dumps({"pages": rows, **result}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"출력 {OUTPUT.name}  {digest(OUTPUT)}")


if __name__ == "__main__":
    main()
