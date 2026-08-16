#!/usr/bin/env python3
"""Apply reviewed General2D spacing fixes and relocate the compact 총 alias."""

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
SOURCE = BUILD / "General2d_special_effect_spacing_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "General2d_ui_followups_fixed_20260812.psarc.sdat"
REPORT = BUILD / "general2d_ui_followups_fixed_20260812_report.json"
ENTRY = 3751

TEXT_PATCHES = (
    # The original one-cell label is 「効果」.  The machine translation was
    # shortened to the meaningless 「그」; the six-byte Korean label fits the
    # existing seven-byte records exactly.
    (431432, "그", "설명"),
    (434868, "그", "설명"),
    (970128, "그", "설명"),
    (970544, "대", "대상"),
    # Leading ASCII spaces are visually collapsed by this widget.  Parentheses
    # preserve a clear boundary even when that leading space is trimmed.
    (688364, "1기", " (1기)"),
    (688404, "1기", " (1기)"),
    (688444, "1기", " (1기)"),
    (688484, "1기", " (1기)"),
    (688524, "1기", " (1기)"),
    (688564, "1기", " (1기)"),
)

# These are the only WTD records intentionally encoded with the former
# U+00B7 compact alias.  U+00B7 itself must return to its retail behavior
# because it is also a hidden prefix used by the action menu.
TOTAL_PATCHES = (
    (1012236, "총"),
    (1132468, "총 턴 수"),
    (1132860, "총 자금"),
    (1134024, "총 AP"),
    (1144032, "총 격추수"),
    (1219040, "총액"),
    (1270580, "총"),
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


def replace_record(
    entry: bytearray,
    offset: int,
    current_text: str,
    target_text: str,
    current_map: dict[str, str],
    target_map: dict[str, str],
) -> dict:
    length = struct.unpack(">I", entry[offset : offset + 4])[0]
    start = offset + 4
    end = start + length
    current = encoded(current_text, current_map)
    target = encoded(target_text, target_map)
    actual = bytes(entry[start:end]).rstrip(b"\0")
    if actual != current:
        raise AssertionError(
            f"unexpected record at {offset}: {actual.hex()} != {current.hex()}"
        )
    if len(target) > length - 1:
        raise AssertionError(f"replacement does not fit at {offset}")
    entry[start:end] = target + b"\0" * (length - len(target))
    return {
        "offset": offset,
        "record_length": length,
        "current": current_text,
        "target": target_text,
        "target_bytes": len(target),
    }


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    source_plain = BUILD / "GENERAL2D_ui_followups_source.psarc"
    output_plain = BUILD / "GENERAL2D_ui_followups_fixed.psarc"
    source_archive = None
    candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        target_map = load_map()
        if target_map.get("총") != chr(0x0089):
            raise AssertionError("new compact 총 alias was not generated")
        legacy_map = dict(target_map)
        legacy_map["총"] = chr(0x00B7)

        changes = []
        for offset, current, target in TEXT_PATCHES:
            changes.append(
                replace_record(
                    entry, offset, current, target, legacy_map, target_map
                )
            )
        for offset, text in TOTAL_PATCHES:
            changes.append(
                replace_record(entry, offset, text, text, legacy_map, target_map)
            )

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: bytes(entry)}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            if candidate.manifest() != source_archive.manifest():
                raise AssertionError("manifest mismatch")
            mismatches = [
                index
                for index in range(source_archive.n)
                if candidate.read_entry(index)
                != (bytes(entry) if index == ENTRY else source_archive.read_entry(index))
            ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE),
            "output": str(OUTPUT),
            "source_sha256": sha(SOURCE),
            "output_sha256": sha(OUTPUT),
            "entry": ENTRY,
            "changes": changes,
            "relocated_total_alias": "U+00B7 -> U+0089",
            "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if source_archive is not None:
            source_archive.f.close()
        if candidate is not None and hasattr(candidate.f, "close"):
            candidate.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
