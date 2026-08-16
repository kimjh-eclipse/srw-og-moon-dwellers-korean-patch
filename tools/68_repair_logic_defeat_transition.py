#!/usr/bin/env python3
"""Restore the scenario game-over control key without changing archive layout."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
SOURCE = ROOT / "korean_build_v3" / "Logic_current_fixed_spans_20260812.psarc.sdat"
OUTPUT = ROOT / "korean_build_v3" / "Logic_defeat_transition_fixed_20260812.psarc.sdat"
REPORT = ROOT / "korean_build_v3" / "logic_defeat_transition_fixed_20260812_report.json"
CONTROL_UID = 8437
CONTROL_TEXT = load_table('CONTROL_TEXT')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    source_plain = ROOT / "korean_build_v3" / "LOGIC_defeat_source.psarc"
    original_plain = ROOT / "korean_build_v3" / "LOGIC_defeat_original.psarc"
    output_plain = ROOT / "korean_build_v3" / "LOGIC_defeat_fixed.psarc"
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            source_size, _ = decrypt_stream(source, 0, target)
        with ORIGINAL.open("rb") as source, original_plain.open("wb") as target:
            original_size, _ = decrypt_stream(source, 0, target)
        if source_size != original_size:
            raise AssertionError("logical PSARC size differs from retail")

        source = PSARC(str(source_plain))
        original = PSARC(str(original_plain))
        if source.manifest() != original.manifest():
            raise AssertionError("manifest mismatch")
        if any(a["offset"] != b["offset"] for a, b in zip(source.entries, original.entries)):
            raise AssertionError("source entry offsets are not retail-identical")

        rows = [
            json.loads(line)
            for line in (ROOT / "extract" / "master.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        targets = [
            row
            for row in rows
            if row.get("uid") == CONTROL_UID
            and row.get("text") == CONTROL_TEXT
            and row.get("file", "").startswith("/Dat/logic/")
        ]
        if len(targets) != 166:
            raise AssertionError(f"unexpected control-key count: {len(targets)}")

        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in targets:
            grouped[int(row["entry"])].append(row)

        replacements: dict[int, bytes] = {}
        changed_occurrences = 0
        for entry, entry_rows in grouped.items():
            current = bytearray(source.read_entry(entry))
            retail = original.read_entry(entry)
            for row in entry_rows:
                start = int(row["off"])
                end = start + int(row["blen"])
                expected = CONTROL_TEXT.encode("utf-8")
                if retail[start:end] != expected:
                    raise AssertionError(f"retail key mismatch: entry {entry} offset {start}")
                if current[start:end] != expected:
                    current[start:end] = expected
                    changed_occurrences += 1
            replacements[entry] = bytes(current)

        if changed_occurrences != len(targets):
            raise AssertionError(
                f"expected {len(targets)} translated keys, changed {changed_occurrences}"
            )

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != source_plain.stat().st_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as stream:
            candidate_plain = ROOT / "korean_build_v3" / "LOGIC_defeat_verify.psarc"
            try:
                with candidate_plain.open("wb") as target:
                    decrypt_stream(stream, 0, target)
                candidate = PSARC(str(candidate_plain))
                mismatches = [
                    entry
                    for entry in range(source.n)
                    if candidate.read_entry(entry)
                    != replacements.get(entry, source.read_entry(entry))
                ]
                offset_mismatches = sum(
                    a["offset"] != b["offset"]
                    for a, b in zip(candidate.entries, original.entries)
                )
            finally:
                candidate_obj = locals().get("candidate")
                if candidate_obj is not None:
                    candidate_obj.f.close()
                candidate_plain.unlink(missing_ok=True)
        if mismatches or offset_mismatches:
            raise AssertionError(
                f"verification failed: semantic={mismatches[:10]}, offsets={offset_mismatches}"
            )

        report = {
            "source": str(SOURCE),
            "output": str(OUTPUT),
            "source_sha256": digest(SOURCE),
            "output_sha256": digest(OUTPUT),
            "control_uid": CONTROL_UID,
            "restored_occurrences": changed_occurrences,
            "changed_entries": len(replacements),
            "semantic_mismatches": 0,
            "entry_offset_mismatches_from_retail": 0,
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for name in ("source", "original"):
            archive = locals().get(name)
            if archive is not None and hasattr(archive, "f"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        original_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
