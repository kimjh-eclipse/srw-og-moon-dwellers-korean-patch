#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inject only one Korean glyph into a slot referenced by no original metric."""
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader
from sdat_encode import encode


OUTER_SIZE = 505_828_992


def load_font_builder():
    path = Path(__file__).with_name("16_build_korean_font.py")
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"{path} is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    root = Path("work_ogmd")
    out = root / "minimal_poc"
    out.mkdir(parents=True, exist_ok=True)
    builder = load_font_builder()

    original_font = (root / "font_dump" / "font.bin").read_bytes()
    font = bytearray(original_font)

    referenced_slots = {
        slot
        for cp in range(0x10000)
        if (slot := builder.metric_slot(original_font, cp)) is not None
    }
    candidates = sorted(set(range(1, builder.FONT_SLOTS)) - referenced_slots)
    if not candidates:
        raise ValueError("no completely unreferenced font slot")
    slot = candidates[0]

    face = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24)
    glyph = builder.render_glyph(load_table("_INLINE")[0], face)
    # A binary coverage mask keeps this diagnostic glyph highly compressible.
    # Full anti-aliasing will return after the storage/mapping test is isolated.
    glyph = glyph.point(lambda value: 255 if value >= 128 else 0)
    builder.inject_cell(font, slot, glyph)

    target_metric = builder.metric_offset(font, ord(load_table("_INLINE")[1]))
    assert target_metric is not None
    x = slot % builder.METRIC_CELLS_X
    y = slot // builder.METRIC_CELLS_X
    old_metric = bytes(font[target_metric : target_metric + 4])
    new_metric = bytes((0, 32, x, y))
    font[target_metric : target_metric + 4] = new_metric

    font_path = out / "font_minimal_pu_to_ga.bin"
    psarc_path = out / "COMMON_minimal_poc.psarc"
    sdat_path = out / "Common_minimal_poc.psarc.sdat"
    font_path.write_bytes(font)

    source_psarc = root / "COMMON.psarc"
    rebuilt_size = rebuild(str(source_psarc), {3: bytes(font)}, str(psarc_path))
    pad_file(psarc_path, source_psarc.stat().st_size)

    source_sdat = root / "original_backups" / "Common.psarc.sdat.orig"
    encode(str(psarc_path), source_sdat.read_bytes()[:0x100], str(sdat_path))
    pad_file(sdat_path, OUTER_SIZE)

    with sdat_path.open("rb") as stream:
        check = PSARC(SDATReader(stream, 0)).read_entry(3)
    if check != bytes(font):
        raise AssertionError("SDAT -> PSARC -> font readback mismatch")

    print(f"all original referenced slots: {len(referenced_slots)}")
    print(f"completely unreferenced slots: {len(candidates)}")
    print(f"selected slot: {slot} (metric x={x}, y={y})")
    print(f"redirect U+30D7: {old_metric.hex()} -> {new_metric.hex()}")
    print(f"font sha256: {hashlib.sha256(font).hexdigest()}")
    print(f"SDAT size: {sdat_path.stat().st_size}")
    print(f"SDAT sha256: {hashlib.sha256(sdat_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
