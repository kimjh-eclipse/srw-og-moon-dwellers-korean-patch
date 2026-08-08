#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace ideographic spaces in BGM titles on top of a known-good Logic SDAT.

The installed archive is decrypted verbatim and used as the rebuild source.
Only /Dat/FixedData/BGMData.dat (entry 6) is replaced.  The plaintext PSARC
and encrypted SDAT sizes are kept identical to the known-good source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ENTRY = 6


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"rebuilt Logic exceeds source size: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sdat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("korean_build_v3"))
    parser.add_argument("--tag", default="bgm_spacing_fix_20260807")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    source_plain = output_dir / f"Logic_{args.tag}_source.psarc"
    out_plain = output_dir / f"Logic_{args.tag}.psarc"
    out_sdat = output_dir / f"Logic_{args.tag}.psarc.sdat"

    with args.source_sdat.open("rb") as source, source_plain.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)

    archive = PSARC(str(source_plain))
    manifest = archive.manifest()
    if manifest[ENTRY - 1] != "/Dat/FixedData/BGMData.dat":
        raise AssertionError(f"unexpected Logic entry {ENTRY}: {manifest[ENTRY - 1]}")

    original = archive.read_entry(ENTRY)
    ideographic_space = "\u3000".encode("utf-8")
    replacement_count = original.count(ideographic_space)
    patched = original.replace(ideographic_space, b"   ")
    if len(patched) != len(original):
        raise AssertionError("BGMData size changed")

    rebuild(str(source_plain), {ENTRY: patched}, str(out_plain))
    pad_file(out_plain, logical_size)
    encode(str(out_plain), args.source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, args.source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback_archive = PSARC(SDATReader(stream, 0))
        if readback_archive.manifest() != manifest:
            raise AssertionError("Logic manifest changed")
        if readback_archive.read_entry(ENTRY) != patched:
            raise AssertionError("BGMData SDAT readback mismatch")

    report = {
        "source_sdat": str(args.source_sdat.resolve()),
        "source_sha256": hashlib.sha256(args.source_sdat.read_bytes()).hexdigest(),
        "entry": ENTRY,
        "entry_name": manifest[ENTRY - 1],
        "ideographic_spaces_replaced": replacement_count,
        "logical_psarc_size": logical_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
    }
    report_path = output_dir / f"logic_{args.tag}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
