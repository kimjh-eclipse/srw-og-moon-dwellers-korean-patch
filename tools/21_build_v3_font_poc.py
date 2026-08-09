from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
load_table("_INLINE")[0]

from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader
from sdat_encode import encode


OUTER_SIZE = 505_828_992


def load_builder():
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
    build = root / "korean_build_v3"
    builder = load_builder()
    font = bytearray((build / "font_ko.bin").read_bytes())

    with (build / "korean_font_map.tsv").open(encoding="utf-8", newline="") as stream:
        ga = next(row for row in csv.DictReader(stream, delimiter="\t") if row["hangul"] == load_table("_INLINE")[2])
    proxy_cp = int(ga["proxy_cp"][2:], 16)
    proxy_metric_offset = builder.metric_offset(font, proxy_cp)
    target_metric_offset = builder.metric_offset(font, ord(load_table("_INLINE")[1]))
    assert proxy_metric_offset is not None and target_metric_offset is not None
    old_metric = bytes(font[target_metric_offset : target_metric_offset + 4])
    proxy_metric = bytes(font[proxy_metric_offset : proxy_metric_offset + 4])
    font[target_metric_offset : target_metric_offset + 4] = proxy_metric

    font_path = build / "font_ko_poc_pu_to_ga.bin"
    psarc_path = build / "COMMON_ko_poc.psarc"
    sdat_path = build / "Common_ko_poc.psarc.sdat"
    font_path.write_bytes(font)

    source_psarc = root / "COMMON.psarc"
    rebuild(str(source_psarc), {3: bytes(font)}, str(psarc_path))
    pad_file(psarc_path, source_psarc.stat().st_size)

    source_sdat = root / "original_backups" / "Common.psarc.sdat.orig"
    encode(str(psarc_path), source_sdat.read_bytes()[:0x100], str(sdat_path))
    pad_file(sdat_path, OUTER_SIZE)

    with sdat_path.open("rb") as stream:
        readback = PSARC(SDATReader(stream, 0)).read_entry(3)
    if readback != bytes(font):
        raise AssertionError("SDAT -> PSARC -> font readback mismatch")

    print(f"가 proxy: U+{proxy_cp:04X}, slot {ga['slot']}")
    print(f"donor metric: {old_metric.hex()} -> {proxy_metric.hex()}")
    print(f"font sha256: {hashlib.sha256(font).hexdigest()}")
    print(f"SDAT size: {sdat_path.stat().st_size}")
    print(f"SDAT sha256: {hashlib.sha256(sdat_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
