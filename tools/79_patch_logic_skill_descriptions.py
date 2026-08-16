#!/usr/bin/env python3
"""Repair the visible Sure Hit note and balance the Potential description."""

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
SOURCE = BUILD / "Logic_system_dialogs_nfd_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "Logic_skill_descriptions_fixed_20260812.psarc.sdat"
REPORT = BUILD / "logic_skill_descriptions_fixed_20260812_report.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def proxy_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in (
        "korean_font_map.tsv", "compact_aliases.tsv",
        "general2d_compact_aliases.tsv", "logic_suffix_aliases.tsv",
    ):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]
    return mapping


def enc(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def patch_span(entry: bytearray, offset: int, span: int, target: str,
               mapping: dict[str, str], *, expected_prefix: str | None = None) -> dict:
    if expected_prefix is not None:
        actual = bytes(entry[offset:offset + span]).split(b"\0", 1)[0]
        if not actual.startswith(enc(expected_prefix, mapping)):
            raise AssertionError(f"unexpected span at {offset}: {actual.hex()}")
    replacement = enc(target, mapping)
    if len(replacement) > span:
        raise AssertionError(f"replacement does not fit at {offset}: {len(replacement)} > {span}")
    entry[offset:offset + span] = replacement + b"\0" * (span - len(replacement))
    return {"offset": offset, "span": span, "target": target,
            "target_bytes": len(replacement)}


def pad(path: Path, size: int) -> None:
    if path.stat().st_size > size:
        raise AssertionError("encoded SDAT grew")
    if path.stat().st_size < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - path.stat().st_size))


def main() -> None:
    source_plain = BUILD / "LOGIC_skill_descriptions_source.psarc"
    output_plain = BUILD / "LOGIC_skill_descriptions_fixed.psarc"
    verify_plain = BUILD / "LOGIC_skill_descriptions_verify.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        mapping = proxy_map()
        replacements: dict[int, bytes] = {}
        changes = []

        # The panel only reads the first SpiritData description string.  Put
        # the priority note in that visible string using the UI's '@' break.
        spirit = bytearray(source_archive.read_entry(26))
        changes.append(patch_span(
            spirit, 1213, 70,
            "1턴 동안 명중률이 100%가 됩니다.@(번뜩임이 우선)", mapping,
            expected_prefix="1턴 동안 공격의 명중률이 100%가 됩니다.",
        ))
        changes.append(patch_span(spirit, 1284, 36, "", mapping))
        replacements[26] = bytes(spirit)

        # SkillData duplicates this description in two tables.  Keep both in
        # sync and put a deliberate line break in the main string instead of
        # leaving only a short tail on line two.
        potential = "스킬 레벨과 남은 HP에 따라@명중률·회피율·장갑·크리티컬률이 상승합니다."
        for entry_index, first_offset, first_span, tail_offset, tail_span in (
            (12, 71411, 108, 71544, 28),
            (24, 2806, 120, 2954, 15),
        ):
            data = bytearray(source_archive.read_entry(entry_index))
            changes.append(patch_span(
                data, first_offset, first_span, potential, mapping,
                expected_prefix="스킬 레벨이 높을수록 탑승 기체 남은",
            ))
            changes.append(patch_span(data, tail_offset, tail_span, "", mapping))
            replacements[entry_index] = bytes(data)

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
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
            != replacements.get(index, source_archive.read_entry(index))
        ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "changed_entries": sorted(replacements), "changes": changes,
            "semantic_mismatches": 0, "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
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
