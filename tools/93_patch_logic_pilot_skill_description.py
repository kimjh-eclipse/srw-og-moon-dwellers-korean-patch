#!/usr/bin/env python3
"""Correct the pilot skill-stat description in its fixed 146-byte field."""
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
SOURCE = Path(r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC\Logic.psarc.sdat")
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_pilot_skill_desc_20260814.psarc.sdat"
REPORT = BUILD / "logic_pilot_skill_desc_20260814_report.json"
ENTRY = 22
OFFSET = 21085
SPAN = 146
TARGET = "파일럿의 전투 기술력입니다. 수치가 클수록\n크리티컬 발생률과 특수기 「카운터」의 발동률이 상승합니다."
HP_ENTRY = 12
HP_OFFSET = 95572
HP_SPAN = 105
HP_BEFORE = "최대ＨＰ"
HP_AFTER = "최대 HP"
COMBO_FIELDS = ((12, 72578, 133), (24, 4110, 142))
OBJECTIVE_FIELDS = {
    38: ((35166, 26, 1), (35206, 26, 1), (35359, 26, 1), (35399, 40, 1)),
    39: ((64041, 50, 1), (64095, 40, 1), (64150, 37, 2)),
}


def load_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv", "general2d_compact_aliases.tsv", "logic_suffix_aliases.tsv"):
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
    source_plain = BUILD / "_logic_pilot_skill_source.psarc"
    output_plain = BUILD / "_logic_pilot_skill_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        table = load_map()
        data = bytearray(source_archive.read_entry(ENTRY))
        before = bytes(data[OFFSET:OFFSET + SPAN]).split(b"\0", 1)[0]
        replacement = encoded(TARGET, table)
        if len(replacement) > SPAN:
            raise AssertionError(f"overflow {len(replacement)} > {SPAN}")
        data[OFFSET:OFFSET + SPAN] = replacement + b"\0" * (SPAN - len(replacement))
        hp_data = bytearray(source_archive.read_entry(HP_ENTRY))
        hp_field = bytes(hp_data[HP_OFFSET:HP_OFFSET + HP_SPAN]).split(b"\0", 1)[0]
        hp_before = encoded(HP_BEFORE, table)
        hp_after = encoded(HP_AFTER, table)
        if hp_field.count(hp_before) != 1:
            raise AssertionError(f"HP token count is {hp_field.count(hp_before)}, expected 1")
        hp_replacement = hp_field.replace(hp_before, hp_after)
        if len(hp_replacement) > HP_SPAN:
            raise AssertionError(f"HP field overflow {len(hp_replacement)} > {HP_SPAN}")
        hp_data[HP_OFFSET:HP_OFFSET + HP_SPAN] = hp_replacement + b"\0" * (HP_SPAN - len(hp_replacement))
        replacements = {HP_ENTRY: bytes(hp_data), ENTRY: bytes(data)}
        combo_changes = []
        for combo_entry, combo_offset, combo_span in COMBO_FIELDS:
            combo_data = bytearray(replacements.get(combo_entry, source_archive.read_entry(combo_entry)))
            combo_before = bytes(combo_data[combo_offset:combo_offset + combo_span]).split(b"\0", 1)[0]
            if not combo_before:
                raise AssertionError(f"empty combination field in entry {combo_entry}")
            combo_after = b" " + combo_before
            if len(combo_after) > combo_span:
                raise AssertionError(f"combination field overflow in entry {combo_entry}")
            combo_data[combo_offset:combo_offset + combo_span] = combo_after + b"\0" * (combo_span - len(combo_after))
            replacements[combo_entry] = bytes(combo_data)
            combo_changes.append({"entry": combo_entry, "offset": combo_offset, "span": combo_span, "left_padding": 1})

        objective_changes = []
        fullwidth_prefix = {1: "１．　".encode("utf-8"), 2: "２．　".encode("utf-8")}
        for objective_entry, fields in OBJECTIVE_FIELDS.items():
            objective_data = bytearray(source_archive.read_entry(objective_entry))
            for objective_offset, objective_span, number in fields:
                before_field = bytes(objective_data[objective_offset:objective_offset + objective_span]).split(b"\0", 1)[0]
                prefix = fullwidth_prefix[number]
                if not before_field.startswith(prefix):
                    raise AssertionError(f"objective prefix mismatch entry {objective_entry} off {objective_offset}")
                after_field = f"{number}. ".encode("ascii") + before_field[len(prefix):]
                objective_data[objective_offset:objective_offset + objective_span] = after_field + b"\0" * (objective_span - len(after_field))
                objective_changes.append({"entry": objective_entry, "offset": objective_offset, "span": objective_span, "number": number})
            replacements[objective_entry] = bytes(objective_data)

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
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
                index for index in range(source_archive.n)
                if candidate.read_entry(index) != replacements.get(index, source_archive.read_entry(index))
            ]
            actual = candidate.read_entry(ENTRY)[OFFSET:OFFSET + SPAN].split(b"\0", 1)[0]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")
        if actual != replacement:
            raise AssertionError("target bytes do not round-trip")

        stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = {
            "source_sha256": digest(SOURCE),
            "output_sha256": digest(OUTPUT),
            "changed_entries": sorted(replacements),
            "entry": ENTRY,
            "offset": OFFSET,
            "span": SPAN,
            "before_hex": before.hex(),
            "target": TARGET,
            "target_bytes": len(replacement),
            "hp_change": {
                "entry": HP_ENTRY,
                "offset": HP_OFFSET,
                "span": HP_SPAN,
                "before": HP_BEFORE,
                "after": HP_AFTER,
                "field_bytes": len(hp_replacement),
            },
            "combination_left_padding": combo_changes,
            "normal_route_objective_prefixes": objective_changes,
            "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size,
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
