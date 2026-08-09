#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a size-preserving COMMON SDAT for the corrected Korean font PoC."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import csv
import hashlib
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat_encode import encode


METRIC_PAGE_DIR = 0x54
TARGET_CP = ord(load_table("_INLINE")[0])
ORIGINAL_OUTER_SIZE = 505_828_992


def metric_offset(font: bytes | bytearray, cp: int) -> int:
    page_ptr = METRIC_PAGE_DIR + (cp >> 8) * 4
    page = struct.unpack(">I", font[page_ptr : page_ptr + 4])[0]
    if not page:
        raise ValueError(f"missing font metric page for U+{cp:04X}")
    return page + (cp & 0xFF) * 4


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    root = Path("work_ogmd")
    build = root / "korean_build_v2"
    source_psarc = root / "COMMON.psarc"
    source_sdat = root / "original_backups" / "Common.psarc.sdat.orig"
    font_path = build / "font_ko.bin"
    map_path = build / "korean_font_map.tsv"
    poc_font_path = build / "font_ko_poc_pu_to_ga.bin"
    rebuilt_path = build / "COMMON_ko_poc.psarc"
    sdat_path = build / "Common_ko_poc.psarc.sdat"

    font = bytearray(font_path.read_bytes())
    with map_path.open(encoding="utf-8", newline="") as stream:
        ga = next(row for row in csv.DictReader(stream, delimiter="\t") if row["hangul"] == load_table("_INLINE")[1])
    metric = metric_offset(font, TARGET_CP)
    old_metric = bytes(font[metric : metric + 4])
    new_metric = bytes((0, 32, int(ga["x"]), int(ga["y"])))
    font[metric : metric + 4] = new_metric
    poc_font_path.write_bytes(font)

    rebuilt_size = rebuild(str(source_psarc), {3: bytes(font)}, str(rebuilt_path))
    original_plain_size = source_psarc.stat().st_size
    if rebuilt_size > original_plain_size:
        raise ValueError(
            f"rebuilt PSARC exceeds original: {rebuilt_size} > {original_plain_size}"
        )
    if rebuilt_size < original_plain_size:
        with rebuilt_path.open("ab") as stream:
            stream.write(b"\0" * (original_plain_size - rebuilt_size))

    original_header = source_sdat.read_bytes()[:0x100]
    encode(str(rebuilt_path), original_header, str(sdat_path))
    encoded_size = sdat_path.stat().st_size
    if encoded_size > ORIGINAL_OUTER_SIZE:
        raise ValueError(
            f"encoded SDAT exceeds original: {encoded_size} > {ORIGINAL_OUTER_SIZE}"
        )
    if encoded_size < ORIGINAL_OUTER_SIZE:
        with sdat_path.open("ab") as stream:
            stream.write(b"\0" * (ORIGINAL_OUTER_SIZE - encoded_size))

    check = PSARC(str(rebuilt_path))
    extracted_font = check.read_entry(3)
    if extracted_font != bytes(font):
        raise AssertionError("PSARC font readback differs from PoC font")

    print(f"redirect U+30D7 metric: {old_metric.hex()} -> {new_metric.hex()}")
    print(f"font sha256:  {sha256(bytes(font))}")
    print(f"PSARC: {rebuilt_path} ({rebuilt_path.stat().st_size:,} bytes)")
    print(f"SDAT:  {sdat_path} ({sdat_path.stat().st_size:,} bytes)")
    print(f"SDAT sha256:  {sha256(sdat_path.read_bytes())}")


if __name__ == "__main__":
    main()
