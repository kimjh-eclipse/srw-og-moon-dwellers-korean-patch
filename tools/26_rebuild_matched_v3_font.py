#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the Common font matched to the V3 Logic/Battle proxy maps.

The Logic and Battle builders encode Korean using the immutable proxy tables in
``korean_build_v3``.  A later Common font was made with the same main map but
without V3's seven compact aliases and without the matching advance metrics.
This script deliberately *does not* select new proxy characters.  It renders
the glyphs into exactly the slots recorded in the V3 map/alias artifacts and
updates only their advance bytes, producing a font that matches the encoder.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

from PIL import ImageFont


V3_MAP_SHA256 = "4579adc90141a9045937ee674a7793926e788fe26b79c36d04473d05a7eb1281"
V3_ALIASES_SHA256 = "c26fd1daaf35f48ca4da2049b44c69ebce8c29a59b106e13d724cb2d230ffec0"
KOREAN_ADVANCE = 22
SPACE_ADVANCE = 10


def load_builder():
    path = Path(__file__).with_name("16_build_korean_font.py")
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default="work_ogmd/font_dump/font.bin")
    parser.add_argument("--map-dir", default="work_ogmd/korean_build_v3")
    parser.add_argument("--out-dir", default="work_ogmd/korean_build_v3_matched")
    parser.add_argument("--face", default="C:/Windows/Fonts/malgunbd.ttf")
    parser.add_argument("--size", type=int, default=28)
    args = parser.parse_args()

    builder = load_builder()
    source_font = Path(args.font)
    map_dir = Path(args.map_dir)
    out_dir = Path(args.out_dir)
    map_path = map_dir / "korean_font_map.tsv"
    aliases_path = map_dir / "compact_aliases.tsv"

    if sha256(map_path) != V3_MAP_SHA256:
        raise AssertionError(f"unexpected V3 main map hash: {sha256(map_path)}")
    if sha256(aliases_path) != V3_ALIASES_SHA256:
        raise AssertionError(
            f"unexpected V3 compact-alias hash: {sha256(aliases_path)}"
        )

    original = source_font.read_bytes()
    if len(original) != builder.TEXTURE_OFFSET + 0x400000:
        raise ValueError(f"unexpected font.bin length: {len(original):#x}")
    font = bytearray(original)
    face = ImageFont.truetype(args.face, args.size)

    main_rows = load_tsv(map_path)
    alias_rows = load_tsv(aliases_path)
    slots: set[int] = set()
    metric_offsets: set[int] = set()

    def inject(row: dict[str, str], *, check_metric: bool) -> None:
        ch = row["hangul"]
        proxy_cp = int(row["proxy_cp"][2:], 16)
        slot = int(row["slot"])
        metric_off = builder.metric_offset(original, proxy_cp)
        if metric_off is None:
            raise AssertionError(f"missing proxy metric for {ch!r}")
        actual_slot = builder.metric_slot(original, proxy_cp)
        if actual_slot != slot:
            raise AssertionError(
                f"slot mismatch for {ch!r}: map={slot}, original={actual_slot}"
            )
        if check_metric and original[metric_off : metric_off + 4].hex() != row["metric"]:
            raise AssertionError(f"metric mismatch for {ch!r}")
        if slot in slots:
            raise AssertionError(f"duplicate font slot {slot} for {ch!r}")
        slots.add(slot)
        metric_offsets.add(metric_off)
        builder.inject_cell(font, slot, builder.render_glyph(ch, face))
        font[metric_off : metric_off + 2] = KOREAN_ADVANCE.to_bytes(2, "big")

    for row in main_rows:
        inject(row, check_metric=True)
    for row in alias_rows:
        inject(row, check_metric=False)

    space_off = builder.metric_offset(original, ord(" "))
    if space_off is None:
        raise AssertionError("ASCII space metric is missing")
    font[space_off : space_off + 2] = SPACE_ADVANCE.to_bytes(2, "big")
    metric_offsets.add(space_off)

    # No page tables or glyph coordinate bytes may move; the text encoders rely
    # on the V3 proxy-to-slot mapping exactly as recorded above.
    expected_header = bytearray(original[: builder.TEXTURE_OFFSET])
    for offset in metric_offsets:
        expected_header[offset : offset + 2] = KOREAN_ADVANCE.to_bytes(2, "big")
    expected_header[space_off : space_off + 2] = SPACE_ADVANCE.to_bytes(2, "big")
    if font[: builder.TEXTURE_OFFSET] != expected_header:
        raise AssertionError("unexpected font-header mutation")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_font = out_dir / "font_ko.bin"
    out_font.write_bytes(font)
    shutil.copy2(map_path, out_dir / map_path.name)
    shutil.copy2(aliases_path, out_dir / aliases_path.name)
    manifest = {
        "base_font_sha256": hashlib.sha256(original).hexdigest(),
        "font_sha256": hashlib.sha256(font).hexdigest(),
        "main_map_sha256": V3_MAP_SHA256,
        "compact_aliases_sha256": V3_ALIASES_SHA256,
        "main_glyphs": len(main_rows),
        "compact_aliases": len(alias_rows),
        "metric_advance": KOREAN_ADVANCE,
        "space_advance": SPACE_ADVANCE,
        "modified_metric_records": len(metric_offsets),
        "modified_slots": len(slots),
    }
    (out_dir / "matched_font_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
