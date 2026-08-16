#!/usr/bin/env python3
"""Repair the two-line Sure Hit SpiritData record without re-encoding its text.

The record stores the first/second-line character counts in its header and uses
an `F` control prefix before the first line.  The previous split-line patch
replaced `F` with a space, retained the Japanese counts (23/12), and filled the
unused fixed spans with spaces.  That makes both UI consumers read the tail of
the first line again.  Reuse the already verified proxy bytes, restore the
control prefix, update the counts to Korean (21/9), and restore NUL padding.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_sure_hit_objective_prefixes_20260814.psarc.sdat"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_sure_hit_structure_fixed_20260814.psarc.sdat"
REPORT = BUILD / "logic_sure_hit_structure_fixed_20260814_report.json"

ENTRY = 26
COUNT1_OFFSET = 1206
COUNT2_OFFSET = 1208
MAIN_OFFSET, MAIN_SPAN = 1213, 70
NOTE_OFFSET, NOTE_SPAN = 1284, 36

# Bytes currently installed by the previous split-line candidate.  Keeping
# these exact proxy sequences avoids any alias-table re-encoding ambiguity.
CURRENT_MAIN = bytes.fromhex(
    "20"
    "31e9b6b420e5bdaae7bf8c20e6b5b4e8acace6a5bcc2a8"
    "2031303025e4b89420e681a2e5b3a0c2a62e"
)
CURRENT_NOTE = bytes.fromhex(
    "efbc88e788bde69983e89a8ac2a820e89290e7a481efbc89"
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "_logic_sure_hit_structure_source.psarc"
    output_plain = BUILD / "_logic_sure_hit_structure_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        data = bytearray(source_archive.read_entry(ENTRY))

        if data[COUNT1_OFFSET:COUNT1_OFFSET + 2] != b"\x00\x17":
            raise AssertionError("unexpected first-line count header")
        if data[COUNT2_OFFSET:COUNT2_OFFSET + 4] != b"\x00\x00\x00\x0c":
            raise AssertionError("unexpected second-line count header")
        if bytes(data[MAIN_OFFSET:MAIN_OFFSET + MAIN_SPAN]).rstrip(b" ") != CURRENT_MAIN:
            raise AssertionError("unexpected current first-line bytes")
        if bytes(data[NOTE_OFFSET:NOTE_OFFSET + NOTE_SPAN]).rstrip(b" ") != CURRENT_NOTE:
            raise AssertionError("unexpected current second-line bytes")
        if data[MAIN_OFFSET + MAIN_SPAN] != 0 or data[NOTE_OFFSET + NOTE_SPAN] != 0:
            raise AssertionError("fixed-field separator changed")

        repaired_main = b"F" + CURRENT_MAIN[1:]
        repaired_note = CURRENT_NOTE
        data[COUNT1_OFFSET:COUNT1_OFFSET + 2] = (21).to_bytes(2, "big")
        data[COUNT2_OFFSET:COUNT2_OFFSET + 4] = (9).to_bytes(4, "big")
        data[MAIN_OFFSET:MAIN_OFFSET + MAIN_SPAN] = repaired_main + b"\0" * (
            MAIN_SPAN - len(repaired_main)
        )
        data[NOTE_OFFSET:NOTE_OFFSET + NOTE_SPAN] = repaired_note + b"\0" * (
            NOTE_SPAN - len(repaired_note)
        )

        replacement = {ENTRY: bytes(data)}
        fixed = rebuild_fixed_entry_spans(source_plain, replacement, output_plain)
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
                != replacement.get(index, source_archive.read_entry(index))
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
            "header": {"first_line_chars": 21, "second_line_chars": 9},
            "first_line": {
                "offset": MAIN_OFFSET,
                "span": MAIN_SPAN,
                "control_prefix": "F",
                "encoded_bytes": len(repaired_main),
                "nul_padding": MAIN_SPAN - len(repaired_main),
            },
            "second_line": {
                "offset": NOTE_OFFSET,
                "span": NOTE_SPAN,
                "encoded_bytes": len(repaired_note),
                "nul_padding": NOTE_SPAN - len(repaired_note),
            },
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
