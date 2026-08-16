#!/usr/bin/env python3
"""Remove the literal @ side effect from the Sure Hit description."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = Path(r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC\Logic.psarc.sdat")
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_sure_hit_inline_note_fixed_20260814.psarc.sdat"
REPORT = BUILD / "logic_sure_hit_inline_note_fixed_20260814_report.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mapping() -> dict[str, str]:
    result = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv", "general2d_compact_aliases.tsv", "logic_suffix_aliases.tsv"):
        path = BUILD / name
        if path.exists():
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    result[row["hangul"]] = row["proxy"]
    return result


def enc(text: str, table: dict[str, str]) -> bytes:
    return "".join(table.get(char, char) for char in text).encode("utf-8")


def main() -> None:
    source_plain = BUILD / "LOGIC_sure_hit_inline_source.psarc"
    output_plain = BUILD / "LOGIC_sure_hit_inline_fixed.psarc"
    verify_plain = BUILD / "LOGIC_sure_hit_inline_verify.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        table = mapping()
        data = bytearray(source_archive.read_entry(26))
        offset, span = 1213, 70
        target_text = "1턴 동안 명중률이 100%가 됩니다.(번뜩임이 우선)"
        replacement = enc(target_text, table)
        if len(replacement) > span:
            raise AssertionError(f"replacement overflow: {len(replacement)} > {span}")
        before = bytes(data[offset:offset + span]).split(b"\0", 1)[0]
        data[offset:offset + span] = replacement + b"\0" * (span - len(replacement))
        replacements = {26: bytes(data)}

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        if OUTPUT.stat().st_size < SOURCE.stat().st_size:
            with OUTPUT.open("ab") as stream:
                stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))
        with OUTPUT.open("rb") as source, verify_plain.open("wb") as target:
            decrypt_stream(source, 0, target)
        candidate = PSARC(str(verify_plain))
        mismatches = [i for i in range(source_archive.n)
                      if candidate.read_entry(i) != replacements.get(i, source_archive.read_entry(i))]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")
        stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "changed_entries": [26],
            "changes": [{"offset": offset, "span": span, "before_hex": before.hex(),
                         "target": target_text, "target_bytes": len(replacement)}],
            "semantic_mismatches": 0, "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        for path in (source_plain, output_plain, verify_plain):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
