#!/usr/bin/env python3
"""Make the formation EVENT label visible by removing markup delimiters."""
from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC\General2d.psarc.sdat"
)
RETAIL = ROOT / "original_backups" / "General2d.psarc.sdat.orig"
OUTPUT = BUILD / "General2d_event_label_20260814.psarc.sdat"
REPORT = BUILD / "general2d_event_label_20260814_report.json"
ENTRY = 3751
OFFSET = 1475408


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "_g2_event_source.psarc"
    output_plain = BUILD / "_g2_event_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        data = bytearray(source_archive.read_entry(ENTRY))

        length = struct.unpack_from(">I", data, OFFSET)[0]
        start, end = OFFSET + 4, OFFSET + 4 + length
        actual = bytes(data[start:end]).rstrip(b"\0")
        if actual != b"<EVENT>":
            raise AssertionError(f"unexpected EVENT record: {actual!r}")
        replacement = b"EVENT"
        data[start:end] = replacement + b"\0" * (length - len(replacement))

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: bytes(data)}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        with OUTPUT.open("ab") as stream:
            stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            mismatches = [
                index
                for index in range(source_archive.n)
                if candidate.read_entry(index)
                != (bytes(data) if index == ENTRY else source_archive.read_entry(index))
            ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "source": str(SOURCE),
            "source_sha256": digest(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "entry": ENTRY,
            "offset": OFFSET,
            "record_length": length,
            "before": "<EVENT>",
            "after": "EVENT",
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
