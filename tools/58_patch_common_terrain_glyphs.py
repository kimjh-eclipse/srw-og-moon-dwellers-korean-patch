#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redirect the four dynamic terrain glyphs to existing Korean glyph cells.

Some status screens render 空/陸/海/宇 directly from game code instead of a
WTD record.  Reuse the already-installed Korean font atlas and change only the
four metric records, keeping every texture and container size unchanged.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


FONT_ENTRY = 3
PAGE_DIR = 0x54
TARGETS = {"空": "공", "陸": "지", "海": "해", "宇": "우"}


def metric_offset(font: bytes | bytearray, cp: int) -> int:
    page = struct.unpack_from(">I", font, PAGE_DIR + (cp >> 8) * 4)[0]
    if not page:
        raise ValueError(f"missing metric page U+{cp:04X}")
    return page + (cp & 0xFF) * 4


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"output exceeds source: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sdat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("korean_build_v3"))
    parser.add_argument("--tag", default="terrain_glyphs_20260808")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    out_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    source_plain = out_dir / f"COMMON_{args.tag}_source.psarc"
    output_plain = out_dir / f"COMMON_{args.tag}.psarc"
    output_sdat = out_dir / f"Common_{args.tag}.psarc.sdat"

    header = args.source_sdat.read_bytes()[:0x100]
    with args.source_sdat.open("rb") as source, source_plain.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)
    archive = PSARC(str(source_plain))
    manifest = archive.manifest()
    if manifest[FONT_ENTRY - 1] != "/Dat/Font/font.bin":
        raise AssertionError(manifest[FONT_ENTRY - 1])

    font = bytearray(archive.read_entry(FONT_ENTRY))
    mapping: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        path = root / "korean_build_v5" / name
        if not path.exists():
            path = root / "korean_build_v3" / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]

    changes = []
    for source_char, korean_char in TARGETS.items():
        proxy = mapping[korean_char]
        source_off = metric_offset(font, ord(source_char))
        proxy_off = metric_offset(font, ord(proxy))
        old = bytes(font[source_off : source_off + 4])
        new = bytes(font[proxy_off : proxy_off + 4])
        if new == b"\0\0\0\0":
            raise ValueError(f"empty proxy metric for {korean_char}")
        font[source_off : source_off + 4] = new
        changes.append(
            {"source": source_char, "target": korean_char, "proxy": proxy,
             "old_metric": old.hex(), "new_metric": new.hex()}
        )

    rebuilt_size = rebuild(str(source_plain), {FONT_ENTRY: bytes(font)}, str(output_plain))
    pad(output_plain, logical_size)
    # PSARC owns an open Windows file handle; release it before removing the
    # temporary decrypted source to keep peak disk use below one gigabyte.
    archive.f.close()
    source_plain.unlink()
    encode(str(output_plain), header, str(output_sdat))
    pad(output_sdat, args.source_sdat.stat().st_size)
    output_plain.unlink()

    with output_sdat.open("rb") as stream:
        check = PSARC(SDATReader(stream, 0))
        if check.manifest() != manifest or check.read_entry(FONT_ENTRY) != bytes(font):
            raise AssertionError("Common readback mismatch")

    report = {
        "source_sha256": hashlib.sha256(args.source_sdat.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(output_sdat.read_bytes()).hexdigest(),
        "sdat_size": output_sdat.stat().st_size,
        "changes": changes,
    }
    report_path = out_dir / f"common_{args.tag}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
