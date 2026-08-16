#!/usr/bin/env python3
"""Restore the scenario title-transition control key in the current Logic archive."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

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
OUTPUT = BUILD / "Logic_title_transition_fixed_20260814.psarc.sdat"
REPORT = BUILD / "logic_title_transition_fixed_20260814_report.json"
TARGETS = ((106, 84724), (107, 51568), (193, 83802), (194, 27670))
CONTROL = load_table("_INLINE")[0].encode("utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "LOGIC_title_control_source.psarc"
    retail_plain = BUILD / "LOGIC_title_control_retail.psarc"
    output_plain = BUILD / "LOGIC_title_control_fixed.psarc"
    verify_plain = BUILD / "LOGIC_title_control_verify.psarc"
    source = retail = candidate = None
    try:
        with SOURCE.open("rb") as inp, source_plain.open("wb") as out:
            logical_size, _ = decrypt_stream(inp, 0, out)
        with RETAIL.open("rb") as inp, retail_plain.open("wb") as out:
            retail_size, _ = decrypt_stream(inp, 0, out)
        if logical_size != retail_size:
            raise AssertionError("logical PSARC size differs from retail")
        source = PSARC(str(source_plain))
        retail = PSARC(str(retail_plain))
        if source.manifest() != retail.manifest():
            raise AssertionError("manifest mismatch")

        replacements: dict[int, bytes] = {}
        changes = []
        for entry_index, offset in TARGETS:
            data = bytearray(replacements.get(entry_index, source.read_entry(entry_index)))
            original = retail.read_entry(entry_index)
            if original[offset:offset + len(CONTROL)] != CONTROL:
                raise AssertionError(f"retail control mismatch at {entry_index}:{offset}")
            before = bytes(data[offset:offset + len(CONTROL)])
            if before == CONTROL:
                raise AssertionError(f"control already restored at {entry_index}:{offset}")
            data[offset:offset + len(CONTROL)] = CONTROL
            replacements[entry_index] = bytes(data)
            changes.append({"entry": entry_index, "offset": offset,
                            "before_hex": before.hex(), "restored": load_table("_INLINE")[0]})

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        if OUTPUT.stat().st_size < SOURCE.stat().st_size:
            with OUTPUT.open("ab") as stream:
                stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as inp, verify_plain.open("wb") as out:
            decrypt_stream(inp, 0, out)
        candidate = PSARC(str(verify_plain))
        mismatches = [i for i in range(source.n)
                      if candidate.read_entry(i) != replacements.get(i, source.read_entry(i))]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")
        stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = {
            "source": str(SOURCE), "output": str(OUTPUT),
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "control_key": load_table("_INLINE")[0], "restored_occurrences": len(changes),
            "changed_entries": sorted(replacements), "changes": changes,
            "semantic_mismatches": 0, "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source, retail, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        for path in (source_plain, retail_plain, output_plain, verify_plain):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
