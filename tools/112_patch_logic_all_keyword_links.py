#!/usr/bin/env python3
"""Translate every Japanese glossary-link label left in Korean Logic data.

The retail game stores glossary links as visible ``<title>`` text.  Many
otherwise translated records retained the Japanese title inside those angle
brackets.  This pass uses the original extraction metadata to patch only the
known fixed-size string fields, preserving every entry span and archive
offset.  If a Korean title needs a few more bytes, ASCII spaces *outside* the
angle-bracket link are removed until the original field capacity is met.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_remaining_terms_20260815.psarc.sdat"
OUTPUT = BUILD / "Logic_keyword_links_ko_20260815.psarc.sdat"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
MASTER = ROOT / "extract_all" / "master_all.jsonl"
TRANSLATIONS = ROOT / "jp2ko.json"
REPORT = BUILD / "logic_keyword_links_20260815_report.json"

# This title has no standalone jp2ko key, but occurs as one glossary link.
MANUAL_TITLES = {"\u63a8\u529b": "추력"}
EXPECTED_UNIQUE_TERMS = 119
EXPECTED_OCCURRENCES = 859


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def load_proxy_maps() -> tuple[dict[str, str], dict[str, str]]:
    forward: dict[str, str] = {}
    for path in (BUILD / "korean_font_map.tsv", BUILD / "compact_aliases.tsv"):
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                forward[row["hangul"]] = row["proxy"]
    reverse = {proxy: hangul for hangul, proxy in forward.items()}
    if len(reverse) != len(forward):
        raise ValueError("proxy map is not one-to-one")
    return forward, reverse


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


def proxy_decode(data: bytes, reverse: dict[str, str]) -> str:
    return "".join(reverse.get(char, char) for char in data.decode("utf-8"))


def is_japanese_term(text: str) -> bool:
    return any(
        0x3040 <= ord(char) <= 0x30FF or 0x4E00 <= ord(char) <= 0x9FFF
        for char in text
    )


def load_title_map() -> dict[str, str]:
    translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    source_terms: set[str] = set()
    with MASTER.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("psarc") != "LOGIC":
                continue
            source_terms.update(
                term
                for term in re.findall(r"<([^<>]+)>", row.get("text", ""))
                if is_japanese_term(term)
            )
    result = {
        term: translations[term]
        for term in source_terms
        if term in translations
    }
    result.update(MANUAL_TITLES)
    return result


def remove_one_space_outside_link(text: str) -> str | None:
    """Remove one low-value ASCII space without changing a link title."""
    inside = False
    candidates: list[int] = []
    preferred: list[int] = []
    for index, char in enumerate(text):
        if char == "<":
            inside = True
        elif char == ">":
            inside = False
        elif char == " " and not inside:
            candidates.append(index)
            if index and text[index - 1] in ">.,!?、。！？":
                preferred.append(index)
            elif index + 1 < len(text) and text[index + 1] == "<":
                preferred.append(index)
    if not candidates:
        return None
    index = preferred[0] if preferred else candidates[-1]
    return text[:index] + text[index + 1 :]


def fit_field(text: str, capacity: int, mapping: dict[str, str]) -> tuple[str, int]:
    compacted = 0
    while len(proxy_encode(text, mapping)) > capacity:
        shortened = remove_one_space_outside_link(text)
        if shortened is None:
            raise ValueError(f"cannot fit translated links into {capacity} bytes: {text!r}")
        text = shortened
        compacted += 1
    return text, compacted


def main() -> None:
    source_plain = BUILD / "_logic_keyword_links_source.psarc"
    output_plain = BUILD / "_logic_keyword_links_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as encrypted, source_plain.open("wb") as plain:
            logical_size, _ = decrypt_stream(encrypted, 0, plain)
        source_archive = PSARC(str(source_plain))
        forward, reverse = load_proxy_maps()
        titles = load_title_map()
        rows: list[dict] = []
        with MASTER.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row.get("psarc") == "LOGIC" and any(
                    f"<{term}>" in row.get("text", "") for term in titles
                ):
                    rows.append(row)

        entry_data: dict[int, bytearray] = {}
        changed_rows: list[dict] = []
        changed_terms: dict[str, int] = {}
        occurrences = 0
        compacted_spaces = 0

        for row in rows:
            entry = row["entry"]
            data = entry_data.setdefault(
                entry, bytearray(source_archive.read_entry(entry))
            )
            start = row["off"]
            capacity = row["blen"]
            raw = bytes(data[start : start + capacity]).split(b"\0", 1)[0]
            current = proxy_decode(raw, reverse)
            patched = current
            row_terms: dict[str, int] = {}
            for source, target in sorted(
                titles.items(), key=lambda item: len(item[0]), reverse=True
            ):
                needle = f"<{source}>"
                count = patched.count(needle)
                if not count:
                    continue
                patched = patched.replace(needle, f"<{target}>")
                row_terms[source] = count
                changed_terms[source] = changed_terms.get(source, 0) + count
                occurrences += count
            if not row_terms:
                continue
            patched, removed = fit_field(patched, capacity, forward)
            encoded = proxy_encode(patched, forward)
            data[start : start + capacity] = encoded + b"\0" * (capacity - len(encoded))
            compacted_spaces += removed
            changed_rows.append(
                {
                    "entry": entry,
                    "offset": start,
                    "capacity": capacity,
                    "file": row["file"],
                    "terms": row_terms,
                    "spaces_removed": removed,
                }
            )

        if len(changed_terms) != EXPECTED_UNIQUE_TERMS:
            raise AssertionError(
                f"unexpected unique term count: {len(changed_terms)} != {EXPECTED_UNIQUE_TERMS}"
            )
        if occurrences != EXPECTED_OCCURRENCES:
            raise AssertionError(
                f"unexpected occurrence count: {occurrences} != {EXPECTED_OCCURRENCES}"
            )

        modified = {entry: bytes(data) for entry, data in entry_data.items()}
        pack_report = rebuild_fixed_entry_spans(source_plain, modified, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        with OUTPUT.open("ab") as stream:
            stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        residual: dict[str, int] = {}
        mismatches: list[int] = []
        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            for entry in range(source_archive.n):
                actual = candidate.read_entry(entry)
                expected = modified.get(entry, source_archive.read_entry(entry))
                if actual != expected:
                    mismatches.append(entry)
                for term in titles:
                    count = actual.count(f"<{term}>".encode("utf-8"))
                    if count:
                        residual[term] = residual.get(term, 0) + count
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")
        if residual:
            raise AssertionError(f"Japanese glossary links remain: {residual}")

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "source": str(SOURCE),
            "source_sha256": digest(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "unique_terms": len(changed_terms),
            "occurrences": occurrences,
            "changed_rows": len(changed_rows),
            "changed_entries": len(modified),
            "spaces_removed": compacted_spaces,
            "residual_japanese_links": 0,
            "semantic_mismatches": 0,
            "terms": changed_terms,
            "rows": changed_rows,
            **pack_report,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=True, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
