#!/usr/bin/env python3
"""Restore the visible second line of the 필중 spirit-command description."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_system_dialog_unicode_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "Logic_system_dialog_spirit_priority_fixed_20260812.psarc.sdat"
REPORT = BUILD / "logic_system_dialog_spirit_priority_fixed_20260812_report.json"
ENTRY = 26
OFFSET = 1284
SPAN = 36
CURRENT_TEXT = "(번뜩임이 우선)."
TARGET_TEXT = "（번뜩임이 우선）"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def proxy_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]
    return mapping


def encode_text(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    source_plain = BUILD / "LOGIC_spirit_priority_source.psarc"
    output_plain = BUILD / "LOGIC_spirit_priority_fixed.psarc"
    verify_plain = BUILD / "LOGIC_spirit_priority_verify.psarc"
    source_archive = None
    candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        mapping = proxy_map()
        current = encode_text(CURRENT_TEXT, mapping)
        target = encode_text(TARGET_TEXT, mapping)
        actual = bytes(entry[OFFSET : OFFSET + SPAN]).split(b"\0", 1)[0]
        if actual != current:
            raise AssertionError(f"unexpected current priority line: {actual.hex()}")
        if len(target) > SPAN:
            raise AssertionError("priority line does not fit")
        entry[OFFSET : OFFSET + SPAN] = target + b"\0" * (SPAN - len(target))

        fixed = rebuild_fixed_entry_spans(
            source_plain, {ENTRY: bytes(entry)}, output_plain
        )
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as source, verify_plain.open("wb") as target_stream:
            decrypt_stream(source, 0, target_stream)
        candidate = PSARC(str(verify_plain))
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
            "source_sha256": digest(SOURCE),
            "output_sha256": digest(OUTPUT),
            "entry": ENTRY,
            "offset": OFFSET,
            "span": SPAN,
            "current_text": CURRENT_TEXT,
            "target_text": TARGET_TEXT,
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
        if candidate is not None:
            candidate.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)
        verify_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
