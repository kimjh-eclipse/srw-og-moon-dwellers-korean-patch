#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack the V4 Korean font without any Japanese-character PoC redirect."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader
from sdat_encode import encode


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"{path} is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", default="work_ogmd/korean_build_v4")
    parser.add_argument("--tag", default="font")
    args = parser.parse_args()

    root = Path("work_ogmd")
    build = Path(args.build_dir)
    font = (build / "font_ko.bin").read_bytes()
    source_psarc = root / "COMMON.psarc"
    source_sdat = root / "original_backups" / "Common.psarc.sdat.orig"
    out_psarc = build / f"COMMON_{args.tag}.psarc"
    out_sdat = build / f"Common_{args.tag}.psarc.sdat"

    rebuild(str(source_psarc), {3: font}, str(out_psarc))
    pad_file(out_psarc, source_psarc.stat().st_size)
    encode(str(out_psarc), source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback = PSARC(SDATReader(stream, 0)).read_entry(3)
    if readback != font:
        raise AssertionError("SDAT -> PSARC -> font readback mismatch")

    print(f"font sha256: {hashlib.sha256(font).hexdigest()}")
    print(f"PSARC size: {out_psarc.stat().st_size}")
    print(f"SDAT size: {out_sdat.stat().st_size}")
    print(f"SDAT sha256: {hashlib.sha256(out_sdat.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
