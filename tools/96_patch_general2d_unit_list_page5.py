#!/usr/bin/env python3
"""Patch the remaining unit-list page 5 labels in General2d."""
from __future__ import annotations

import csv
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
OUTPUT = BUILD / "General2d_unit_list_page5_20260814.psarc.sdat"
REPORT = BUILD / "general2d_unit_list_page5_20260814_report.json"
ENTRY = 3751

# One active duplicate of the page title was missed.  The replacement is the
# same 16-byte fixed-width text already used by the four corrected duplicates.
MAX_ATTACK_OFFSET = 140500

# These are every remaining retail `ＡＬＬ` record still translated as `모든`.
ALL_OFFSETS = (
    399320, 399880, 399936,
    644568, 656204,
    1575988, 1576548, 1576604,
)


def load_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv", "general2d_compact_aliases.tsv"):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def encoded(text: str, table: dict[str, str]) -> bytes:
    return "".join(table.get(char, char) for char in text).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_record(
    data: bytearray,
    offset: int,
    expected: bytes,
    replacement: bytes,
    label: str,
) -> dict[str, object]:
    length = struct.unpack_from(">I", data, offset)[0]
    start, end = offset + 4, offset + 4 + length
    actual = bytes(data[start:end]).rstrip(b"\0")
    if actual != expected:
        raise AssertionError(f"{offset}: {actual.hex()} != {expected.hex()} ({label})")
    # General2d's fixed-width records can consume the full declared span.  Four
    # existing maximum-attack duplicates already use this exact 16-byte form.
    if len(replacement) > length:
        raise AssertionError(f"{offset}: overflow {len(replacement)} > {length} ({label})")
    data[start:end] = replacement + b"\0" * (length - len(replacement))
    return {
        "offset": offset,
        "label": label,
        "record_length": length,
        "before_hex": actual.hex(),
        "after_hex": replacement.hex(),
    }


def main() -> None:
    source_plain = BUILD / "_g2_page5_source.psarc"
    output_plain = BUILD / "_g2_page5_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        data = bytearray(source_archive.read_entry(ENTRY))
        table = load_map()
        changes: list[dict[str, object]] = []

        max_replacement = encoded("최대 공격력", table)
        # Assert byte-for-byte identity with a corrected duplicate already in
        # the installed source rather than inventing a new representation.
        reference_length = struct.unpack_from(">I", data, 140224)[0]
        reference = bytes(data[140228:140228 + reference_length]).rstrip(b"\0")
        if max_replacement != reference:
            raise AssertionError("maximum-attack replacement differs from corrected duplicate")
        changes.append(
            patch_record(
                data,
                MAX_ATTACK_OFFSET,
                encoded("최대 공", table),
                max_replacement,
                "최대 공 -> 최대 공격력",
            )
        )

        for offset in ALL_OFFSETS:
            changes.append(
                patch_record(data, offset, encoded("모든", table), b"ALL", "모든 -> ALL")
            )

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
            "source_sha256": sha256(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": sha256(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "semantic_mismatches": 0,
            "changes": changes,
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
