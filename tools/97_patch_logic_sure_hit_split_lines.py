#!/usr/bin/env python3
"""Restore the two fixed SpiritData fields used by the Sure Hit description."""
from __future__ import annotations

import csv
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
SOURCE = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC\Logic.psarc.sdat"
)
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_sure_hit_split_lines_20260814.psarc.sdat"
REPORT = BUILD / "logic_sure_hit_split_lines_20260814_report.json"
ENTRY = 26

MAIN_OFFSET, MAIN_SPAN = 1213, 70
NOTE_OFFSET, NOTE_SPAN = 1284, 36


def mapping() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in (
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
        "logic_suffix_aliases.tsv",
    ):
        path = BUILD / name
        if path.exists():
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    result[row["hangul"]] = row["proxy"]
    return result


def encoded(text: str, table: dict[str, str]) -> bytes:
    return "".join(table.get(char, char) for char in text).encode("utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "_logic_sure_hit_split_source.psarc"
    output_plain = BUILD / "_logic_sure_hit_split_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        data = bytearray(source_archive.read_entry(ENTRY))
        table = mapping()

        expected_main = encoded("1턴 동안 명중률이 100%가 됩니다.(번뜩임이 우선)", table)
        actual_main = bytes(data[MAIN_OFFSET:MAIN_OFFSET + MAIN_SPAN]).split(b"\0", 1)[0]
        actual_note = bytes(data[NOTE_OFFSET:NOTE_OFFSET + NOTE_SPAN])
        if actual_main != expected_main:
            raise AssertionError(
                f"unexpected current main line: {actual_main.hex()} != {expected_main.hex()}"
            )
        if actual_note.strip(b"\0 "):
            raise AssertionError(f"unexpected current note field: {actual_note.hex()}")

        # The panel clips the first glyph at its left edge.  A leading ASCII
        # space is intentionally consumed by that clip so the visible text
        # begins with `1턴`, not `턴`.
        main_text = " 1턴 동안 명중률이 100%가 됩니다."
        # Full-width parentheses keep this continuation field enabled in both
        # the command panel and the search panel.
        note_text = "（번뜩임이 우선）"
        main = encoded(main_text, table)
        note = encoded(note_text, table)
        if len(main) > MAIN_SPAN or len(note) > NOTE_SPAN:
            raise AssertionError(
                f"replacement overflow: main {len(main)}/{MAIN_SPAN}, note {len(note)}/{NOTE_SPAN}"
            )

        # These adjacent fields are read sequentially by the UI.  Interior NUL
        # padding would terminate the chain, so use spaces up to the one real
        # separator byte after each fixed span.
        data[MAIN_OFFSET:MAIN_OFFSET + MAIN_SPAN] = main + b" " * (MAIN_SPAN - len(main))
        data[NOTE_OFFSET:NOTE_OFFSET + NOTE_SPAN] = note + b" " * (NOTE_SPAN - len(note))
        if data[MAIN_OFFSET + MAIN_SPAN] != 0 or data[NOTE_OFFSET + NOTE_SPAN] != 0:
            raise AssertionError("fixed-field separator changed")
        if b"\0" in data[MAIN_OFFSET:MAIN_OFFSET + MAIN_SPAN]:
            raise AssertionError("interior NUL in main field")
        if b"\0" in data[NOTE_OFFSET:NOTE_OFFSET + NOTE_SPAN]:
            raise AssertionError("interior NUL in note field")

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
            "main": {
                "offset": MAIN_OFFSET,
                "span": MAIN_SPAN,
                "text": main_text,
                "encoded_bytes": len(main),
                "space_padding": MAIN_SPAN - len(main),
            },
            "note": {
                "offset": NOTE_OFFSET,
                "span": NOTE_SPAN,
                "text": note_text,
                "encoded_bytes": len(note),
                "space_padding": NOTE_SPAN - len(note),
            },
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
