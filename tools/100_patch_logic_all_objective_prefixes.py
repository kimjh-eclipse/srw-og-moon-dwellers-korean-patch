#!/usr/bin/env python3
"""Normalize every active scenario objective prefix to safe ASCII punctuation.

The mission-objective renderer maps the Japanese ideographic space in
``１．　`` to a visible Korean glyph (reported as a stray ``토``).  The current
archive already fixed the first eleven records, but the remaining active
scenario scripts still use the unsafe full-width prefix.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_sure_hit_split_lines_20260814.psarc.sdat"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
MASTER = ROOT / "extract" / "master.jsonl"
OUTPUT = BUILD / "Logic_sure_hit_objective_prefixes_20260814.psarc.sdat"
REPORT = BUILD / "logic_sure_hit_objective_prefixes_20260814_report.json"

FULLWIDTH_PREFIXES = {
    digit: f"{fullwidth}．".encode("utf-8")
    for digit, fullwidth in zip("123456789", "１２３４５６７８９")
}
SAFE_PREFIXES = {digit: f"{digit}. ".encode("ascii") for digit in "123456789"}
IDEOGRAPHIC_SPACE = "　".encode("utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def objective_rows() -> list[dict]:
    rows: list[dict] = []
    pattern = re.compile(r"^[\uFF11-\uFF19]\uFF0E")
    with MASTER.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row.get("psarc") == "LOGIC"
                and row.get("file", "").startswith("/Dat/logic/scr")
                and pattern.match(row.get("text", ""))
            ):
                rows.append(row)
    keys = [(row["entry"], row["off"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise AssertionError("duplicate active objective offsets in master extraction")
    return rows


def main() -> None:
    source_plain = BUILD / "_logic_objective_prefix_source.psarc"
    output_plain = BUILD / "_logic_objective_prefix_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        rows = objective_rows()
        replacements: dict[int, bytes] = {}
        changed: list[dict] = []
        already_safe: list[dict] = []

        for row in rows:
            entry = row["entry"]
            offset = row["off"]
            span = row["blen"]
            data = bytearray(replacements.get(entry, source_archive.read_entry(entry)))
            field = bytes(data[offset : offset + span])
            current = field.split(b"\0", 1)[0]

            fullwidth_digit = next(
                (digit for digit, prefix in FULLWIDTH_PREFIXES.items() if current.startswith(prefix)),
                None,
            )
            safe_digit = next(
                (digit for digit, prefix in SAFE_PREFIXES.items() if current.startswith(prefix)),
                None,
            )
            if fullwidth_digit is not None:
                old_prefix = FULLWIDTH_PREFIXES[fullwidth_digit]
                body = current[len(old_prefix) :]
                removed_ideographic_space = body.startswith(IDEOGRAPHIC_SPACE)
                if removed_ideographic_space:
                    body = body[len(IDEOGRAPHIC_SPACE) :]
                updated = SAFE_PREFIXES[fullwidth_digit] + body
                if len(updated) >= span:
                    raise AssertionError(
                        f"normalized objective no longer fits entry {entry} off {offset}"
                    )
                data[offset : offset + span] = updated + b"\0" * (span - len(updated))
                if data[offset + span] != 0:
                    raise AssertionError(f"separator changed at entry {entry} off {offset}")
                replacements[entry] = bytes(data)
                changed.append(
                    {
                        "file": row["file"],
                        "entry": entry,
                        "offset": offset,
                        "span": span,
                        "digit": fullwidth_digit,
                        "removed_ideographic_space": removed_ideographic_space,
                    }
                )
            elif safe_digit is not None:
                already_safe.append(
                    {
                        "file": row["file"],
                        "entry": entry,
                        "offset": offset,
                        "digit": safe_digit,
                    }
                )
            else:
                raise AssertionError(
                    f"unexpected objective prefix at entry {entry} off {offset}: {current[:12].hex()}"
                )

        if len(rows) != 276 or len(changed) != 265 or len(already_safe) != 11:
            raise AssertionError(
                f"audit count changed: total={len(rows)} changed={len(changed)} safe={len(already_safe)}"
            )

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
                index
                for index in range(source_archive.n)
                if candidate.read_entry(index)
                != replacements.get(index, source_archive.read_entry(index))
            ]
            if mismatches:
                raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

            unsafe_after: list[tuple[int, int]] = []
            safe_after = 0
            for row in rows:
                field = candidate.read_entry(row["entry"])[
                    row["off"] : row["off"] + row["blen"]
                ]
                current = field.split(b"\0", 1)[0]
                if any(current.startswith(prefix) for prefix in FULLWIDTH_PREFIXES.values()):
                    unsafe_after.append((row["entry"], row["off"]))
                if any(current.startswith(prefix) for prefix in SAFE_PREFIXES.values()):
                    safe_after += 1
            if unsafe_after or safe_after != len(rows):
                raise AssertionError(
                    f"post-build prefix audit failed: unsafe={unsafe_after[:10]} safe={safe_after}"
                )

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        changed_by_file = Counter(item["file"] for item in changed)
        report = {
            "source": str(SOURCE),
            "source_sha256": digest(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "active_numbered_objectives": len(rows),
            "active_scenario_files": len({row["file"] for row in rows}),
            "already_safe": len(already_safe),
            "normalized": len(changed),
            "ideographic_spaces_removed": sum(
                item["removed_ideographic_space"] for item in changed
            ),
            "unsafe_after": 0,
            "safe_after": safe_after,
            "changed_entries": len(replacements),
            "changed_by_file": dict(sorted(changed_by_file.items())),
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
