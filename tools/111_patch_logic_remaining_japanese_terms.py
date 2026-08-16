#!/usr/bin/env python3
"""Replace the remaining Japanese terminology in the final Korean Logic data.

The Korean dialogue fields are already proxy encoded.  Rebuilding all dialogue
from the retail archive would discard the later structural fixes, so this pass
changes only the two literal Japanese byte sequences that survived translation.
Each replacement is shorter, and the freed bytes are moved to NUL padding at
the end of the same string.  Entry sizes and every following offset stay fixed.
"""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

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
SOURCE = BUILD / "Logic_sure_hit_structure_fixed_20260814.psarc.sdat"
OUTPUT = BUILD / "Logic_remaining_terms_20260815.psarc.sdat"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
REPORT = BUILD / "logic_remaining_terms_20260815_report.json"

EXPECTED = load_table('EXPECTED')
REPLACEMENTS = load_table('REPLACEMENTS')


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def load_proxy_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in (BUILD / "korean_font_map.tsv", BUILD / "compact_aliases.tsv"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            result.update(
                {row["hangul"]: row["proxy"] for row in csv.DictReader(stream, delimiter="\t")}
            )
    return result


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    encoded_text = "".join(mapping.get(char, char) for char in text)
    missing = {
        char
        for char in encoded_text
        if 0xAC00 <= ord(char) <= 0xD7A3 or 0x3130 <= ord(char) <= 0x318F
    }
    if missing:
        raise ValueError(f"missing Korean proxies: {sorted(missing)}")
    return encoded_text.encode("utf-8")


def replace_in_string(data: bytearray, start: int, old: bytes, new: bytes) -> None:
    end = data.find(b"\0", start)
    if end < 0:
        raise AssertionError(f"unterminated string at {start}")
    segment = bytes(data[start:end])
    if not segment.startswith(old):
        raise AssertionError("replacement position moved")
    replaced = new + segment[len(old):]
    if len(replaced) > len(segment):
        raise AssertionError("replacement does not fit the existing field")
    data[start:end] = replaced + b"\0" * (len(segment) - len(replaced))


def main() -> None:
    source_plain = BUILD / "_logic_remaining_terms_source.psarc"
    output_plain = BUILD / "_logic_remaining_terms_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as encrypted, source_plain.open("wb") as plain:
            logical_size, _ = decrypt_stream(encrypted, 0, plain)
        source_archive = PSARC(str(source_plain))
        mapping = load_proxy_map()
        encoded = {
            old: (old.encode("utf-8"), proxy_encode(new, mapping))
            for old, new in REPLACEMENTS.items()
        }

        counts = {term: 0 for term in REPLACEMENTS}
        modified: dict[int, bytes] = {}
        changed_locations: list[dict] = []
        for entry in range(source_archive.n):
            original = source_archive.read_entry(entry)
            patched = bytearray(original)
            changed = False
            for term, (old, new) in encoded.items():
                cursor = 0
                while True:
                    position = patched.find(old, cursor)
                    if position < 0:
                        break
                    replace_in_string(patched, position, old, new)
                    counts[term] += 1
                    changed_locations.append(
                        {"entry": entry, "offset": position, "from": term, "to": REPLACEMENTS[term]}
                    )
                    cursor = position + len(new)
                    changed = True
            if changed:
                modified[entry] = bytes(patched)

        if counts != EXPECTED:
            raise AssertionError(f"unexpected occurrence counts: {counts} != {EXPECTED}")

        pack_report = rebuild_fixed_entry_spans(source_plain, modified, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        with OUTPUT.open("ab") as stream:
            stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            mismatches = []
            residual = {term: 0 for term in REPLACEMENTS}
            for entry in range(source_archive.n):
                actual = candidate.read_entry(entry)
                expected = modified.get(entry, source_archive.read_entry(entry))
                if actual != expected:
                    mismatches.append(entry)
                for term, (old, _) in encoded.items():
                    residual[term] += actual.count(old)
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")
        if any(residual.values()):
            raise AssertionError(f"Japanese terms remain: {residual}")

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "source": str(SOURCE),
            "source_sha256": digest(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "occurrences": counts,
            "replacement_entries": len(modified),
            "locations": changed_locations,
            "residual_japanese_terms": residual,
            "semantic_mismatches": 0,
            **pack_report,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Keep console output portable on Windows hosts whose active code page
        # cannot encode Japanese source terms.
        print(json.dumps(report, ensure_ascii=True, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
