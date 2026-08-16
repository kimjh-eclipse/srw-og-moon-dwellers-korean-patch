#!/usr/bin/env python3
"""Blank retail control glyphs that collide with Korean 트/특 proxies."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "General2d_self_target_fixed_20260812.psarc.sdat"
RETAIL = ROOT / "original_backups" / "General2d.psarc.sdat.orig"
OUTPUT = BUILD / "General2d_control_glyphs_blank_20260813.psarc.sdat"
REPORT = BUILD / "general2d_control_glyphs_blank_20260813_report.json"
BLANK = "　".encode("utf-8")  # U+3000, same three-byte width
TARGETS = {0xA010: "트", 0xA011: "특"}


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
    source_plain = BUILD / "GENERAL2D_control_blank_source.psarc"
    retail_plain = BUILD / "GENERAL2D_control_blank_retail.psarc"
    output_plain = BUILD / "GENERAL2D_control_blank_fixed.psarc"
    verify_plain = BUILD / "GENERAL2D_control_blank_verify.psarc"
    source_archive = retail_archive = verify_archive = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        with RETAIL.open("rb") as source, retail_plain.open("wb") as target:
            decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        retail_archive = PSARC(str(retail_plain))
        replacements: dict[int, bytes] = {}
        details = []
        totals = {name: 0 for name in TARGETS.values()}

        for index in range(source_archive.n):
            current = source_archive.read_entry(index)
            retail = retail_archive.read_entry(index)
            data = bytearray(current)
            entry_counts = {name: 0 for name in TARGETS.values()}
            for cp, name in TARGETS.items():
                token = chr(cp).encode("utf-8")
                start = 0
                while True:
                    pos = current.find(token, start)
                    if pos < 0:
                        break
                    # Blank only positions inherited from retail. Korean
                    # translation uses at other positions remain untouched.
                    if retail[pos : pos + 3] == token:
                        data[pos : pos + 3] = BLANK
                        entry_counts[name] += 1
                        totals[name] += 1
                    start = pos + 3
            if data != current:
                replacements[index] = bytes(data)
                details.append({"entry": index, "blanked": entry_counts})

        if totals != {"트": 8, "특": 10}:
            raise AssertionError(f"unexpected retail-use counts: {totals}")
        fixed = rebuild_fixed_blocks(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)
        with OUTPUT.open("rb") as source, verify_plain.open("wb") as target:
            decrypt_stream(source, 0, target)
        verify_archive = PSARC(str(verify_plain))
        mismatches = [
            index for index in range(source_archive.n)
            if verify_archive.read_entry(index)
            != replacements.get(index, source_archive.read_entry(index))
        ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "blank": "U+3000", "totals": totals, "entries": details,
            "changed_entries": len(replacements), "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, retail_archive, verify_archive):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        for path in (source_plain, retail_plain, output_plain, verify_plain):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
