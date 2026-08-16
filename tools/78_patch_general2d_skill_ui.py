#!/usr/bin/env python3
"""Patch the reviewed skill-tab label and spirit target spacing."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "General2d_ui_followups_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "General2d_skill_ui_fixed_20260812.psarc.sdat"
REPORT = BUILD / "general2d_skill_ui_fixed_20260812_report.json"
ENTRY = 3751

TARGET_RECORDS = (688364, 688404, 688444, 688484, 688524, 688564)
SPECIAL_SKILL_RECORDS = (
    140624, 191108, 205676, 233980, 431244, 611032,
    864428, 976420, 976468, 980324, 1318652,
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in (
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
    ):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]
    return mapping


def encoded(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def replace_record(entry: bytearray, offset: int, current: str, target: str,
                   mapping: dict[str, str]) -> dict:
    length = struct.unpack(">I", entry[offset:offset + 4])[0]
    start = offset + 4
    end = start + length
    actual = bytes(entry[start:end]).rstrip(b"\0")
    expected = encoded(current, mapping)
    replacement = encoded(target, mapping)
    if actual != expected:
        raise AssertionError(f"unexpected record at {offset}: {actual.hex()}")
    if len(replacement) > length - 1:
        raise AssertionError(f"replacement does not fit at {offset}")
    entry[start:end] = replacement + b"\0" * (length - len(replacement))
    return {
        "offset": offset,
        "record_length": length,
        "current": current,
        "target": target,
        "target_bytes": len(replacement),
    }


def pad(path: Path, size: int) -> None:
    if path.stat().st_size > size:
        raise AssertionError("encoded SDAT grew")
    if path.stat().st_size < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - path.stat().st_size))


def main() -> None:
    source_plain = BUILD / "GENERAL2D_skill_ui_source.psarc"
    output_plain = BUILD / "GENERAL2D_skill_ui_fixed.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        mapping = load_map()
        changes = []

        # ASCII spaces and parentheses are collapsed/hidden by this widget.
        # A Japanese full-width space is retained and creates a stable gap.
        for offset in TARGET_RECORDS:
            changes.append(replace_record(entry, offset, " (1기)", "　1기", mapping))

        for offset in SPECIAL_SKILL_RECORDS:
            changes.append(replace_record(entry, offset, "특수기", "특수기술", mapping))

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: bytes(entry)}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            mismatches = [
                index for index in range(source_archive.n)
                if candidate.read_entry(index)
                != (bytes(entry) if index == ENTRY else source_archive.read_entry(index))
            ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": sha(SOURCE), "output_sha256": sha(OUTPUT),
            "entry": ENTRY, "changes": changes, "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if source_archive is not None:
            source_archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
