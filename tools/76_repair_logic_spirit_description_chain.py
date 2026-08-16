#!/usr/bin/env python3
"""Restore the adjacent SpiritData description chain for 필중."""

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
SOURCE = BUILD / "Logic_system_dialogs_ascii_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "Logic_system_dialogs_spirit_chain_fixed_20260812.psarc.sdat"
REPORT = BUILD / "logic_system_dialogs_spirit_chain_fixed_20260812_report.json"
ENTRY = 26
PATCHES = (
    (1213, 70, "1턴 동안 공격의 명중률이 100%가 됩니다."),
    (1284, 36, "（번뜩임이 우선）"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def proxy_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    # Match the exact precedence used by the main Logic builder.  Some glyphs
    # are deliberately reassigned in the later compact/suffix maps.
    for name in (
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
        "logic_suffix_aliases.tsv",
    ):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]
    return mapping


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    source_plain = BUILD / "LOGIC_spirit_chain_source.psarc"
    output_plain = BUILD / "LOGIC_spirit_chain_fixed.psarc"
    verify_plain = BUILD / "LOGIC_spirit_chain_verify.psarc"
    source_archive = None
    candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        mapping = proxy_map()
        changes = []
        for offset, span, text in PATCHES:
            encoded = proxy_encode(text, mapping)
            actual = bytes(entry[offset : offset + span]).split(b"\0", 1)[0]
            if actual != encoded:
                raise AssertionError(
                    f"unexpected current description at {offset}: "
                    f"{actual.hex()} != {encoded.hex()}"
                )
            if len(encoded) > span:
                raise AssertionError(f"description does not fit at {offset}")
            # Fill the fixed content span with spaces.  The one real NUL
            # separator immediately after each span remains untouched.
            entry[offset : offset + span] = encoded + b" " * (span - len(encoded))
            if entry[offset + span] != 0:
                raise AssertionError(f"missing separator after {offset}")
            changes.append(
                {
                    "offset": offset,
                    "span": span,
                    "text": text,
                    "encoded_bytes": len(encoded),
                    "space_padding": span - len(encoded),
                    "separator_offset": offset + span,
                }
            )

        # The sequential string reader must now see exactly the two reviewed
        # descriptions, separated by one NUL each, with no interior NULs.
        for offset, span, _ in PATCHES:
            if b"\0" in entry[offset : offset + span]:
                raise AssertionError(f"interior NUL remains at {offset}")

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
            "changes": changes,
            "interior_nuls": 0,
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
