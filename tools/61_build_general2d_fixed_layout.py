#!/usr/bin/env python3
"""Graft the accepted General2D window data into the retail fixed layout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_backups" / "General2d.psarc.sdat.orig"
ACCEPTED = ROOT / "korean_build_v3" / "General2d_menu_all_ui14_bootsafe_terrain_next_20260808.psarc.sdat"
OUT_DIR = ROOT / "korean_build_v3"
OUTPUT = OUT_DIR / "General2d_fixed_layout_20260808.psarc.sdat"
REPORT = OUT_DIR / "general2d_fixed_layout_20260808_report.json"
ENTRY = 3751
ENTRY_NAME = "/Dat/Window/WindowToolData/windowdataMain.wtd"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_plain = OUT_DIR / "GENERAL2D_fixed_layout_source.psarc"
    output_plain = OUT_DIR / "GENERAL2D_fixed_layout.psarc"
    header = ORIGINAL.read_bytes()[:0x100]
    try:
        with ORIGINAL.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        retail = PSARC(str(source_plain))
        manifest = retail.manifest()
        if manifest[ENTRY - 1] != ENTRY_NAME:
            raise AssertionError(manifest[ENTRY - 1])
        with ACCEPTED.open("rb") as stream:
            accepted = PSARC(SDATReader(stream, 0))
            if accepted.manifest() != manifest:
                raise AssertionError("manifest mismatch")
            replacement = accepted.read_entry(ENTRY)
        if len(replacement) != retail.entries[ENTRY]["orig_size"]:
            raise AssertionError("entry size mismatch")

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: replacement}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), header, str(OUTPUT))
        pad(OUTPUT, ORIGINAL.stat().st_size)

        mismatches = []
        with OUTPUT.open("rb") as cs, ACCEPTED.open("rb") as acs:
            candidate = PSARC(SDATReader(cs, 0))
            accepted = PSARC(SDATReader(acs, 0))
            if candidate.manifest() != accepted.manifest():
                raise AssertionError("candidate manifest mismatch")
            for entry in range(candidate.n):
                left = candidate.read_entry(entry)
                right = accepted.read_entry(entry)
                if left != right:
                    mismatches.append(entry)
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "original": str(ORIGINAL),
            "accepted": str(ACCEPTED),
            "output": str(OUTPUT),
            "original_sha256": file_hash(ORIGINAL),
            "accepted_sha256": file_hash(ACCEPTED),
            "output_sha256": file_hash(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "entry": ENTRY,
            "entry_name": ENTRY_NAME,
            "entry_size": len(replacement),
            "entries_compared": retail.n,
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        obj = locals().get("retail")
        if obj is not None:
            obj.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
