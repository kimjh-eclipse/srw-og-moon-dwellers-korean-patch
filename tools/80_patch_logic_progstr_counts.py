#!/usr/bin/env python3
"""Restore ProgStrData character-count invariants for system prompts."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_skill_descriptions_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "Logic_progstr_counts_fixed_20260812.psarc.sdat"
REPORT = BUILD / "logic_progstr_counts_fixed_20260812_report.json"
ENTRY = 22

# count offset, expected count, corrected Unicode code-point count,
# string offset, expected NFC display text
PATCHES = (
    (9482, 21, 13, 9486, "계속할까요?"),
    (10314, 22, 24, 10318, "저장이 끝났습니다.\n게임을 계속하시겠습니까?"),
    (32139, 18, 13, 32143, "계속할까요?"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad(path: Path, size: int) -> None:
    if path.stat().st_size > size:
        raise AssertionError("encoded SDAT grew")
    if path.stat().st_size < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - path.stat().st_size))


def main() -> None:
    import unicodedata

    source_plain = BUILD / "LOGIC_progstr_counts_source.psarc"
    output_plain = BUILD / "LOGIC_progstr_counts_fixed.psarc"
    verify_plain = BUILD / "LOGIC_progstr_counts_verify.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        changes = []

        for count_offset, expected, corrected, string_offset, display in PATCHES:
            if entry[count_offset - 2:count_offset] != b"\x00\x01":
                raise AssertionError(f"missing record marker at {count_offset - 2}")
            if entry[count_offset + 2:count_offset + 4] != b"\x00\x00":
                raise AssertionError(f"missing record separator at {count_offset + 2}")
            current = struct.unpack(">H", entry[count_offset:count_offset + 2])[0]
            if current != expected:
                raise AssertionError(f"unexpected count at {count_offset}: {current}")
            end = entry.index(0, string_offset)
            text = bytes(entry[string_offset:end]).decode("utf-8")
            if unicodedata.normalize("NFC", text) != display:
                raise AssertionError(f"unexpected text at {string_offset}: {text!r}")
            if len(text) != corrected:
                raise AssertionError(
                    f"code-point count mismatch at {string_offset}: {len(text)} != {corrected}"
                )
            entry[count_offset:count_offset + 2] = struct.pack(">H", corrected)
            changes.append({
                "count_offset": count_offset,
                "string_offset": string_offset,
                "old_count": expected,
                "new_count": corrected,
                "display_text": display,
                "normalization": "NFD" if text != display else "NFC",
            })

        fixed = rebuild_fixed_entry_spans(
            source_plain, {ENTRY: bytes(entry)}, output_plain
        )
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as source, verify_plain.open("wb") as target:
            decrypt_stream(source, 0, target)
        candidate = PSARC(str(verify_plain))
        mismatches = [
            index for index in range(source_archive.n)
            if candidate.read_entry(index)
            != (bytes(entry) if index == ENTRY else source_archive.read_entry(index))
        ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "entry": ENTRY, "changes": changes, "changed_bytes": 6,
            "semantic_mismatches": 0, "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
