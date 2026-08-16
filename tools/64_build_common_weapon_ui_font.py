#!/usr/bin/env python3
"""Graft the weapon-UI extended Korean font into retail Common layout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_backups" / "Common.psarc.sdat.orig"
FONT = ROOT / "korean_build_v3_matched" / "font_ko_weapon_ui.bin"
OUTPUT = ROOT / "korean_build_v3" / "Common_weapon_ui_font_20260811.psarc.sdat"
REPORT = ROOT / "korean_build_v3" / "common_weapon_ui_font_20260811_report.json"
ENTRY = 3
ENTRY_NAME = "/Dat/Font/font.bin"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source_plain = ROOT / "korean_build_v3" / "COMMON_weapon_ui_source.psarc"
    output_plain = ROOT / "korean_build_v3" / "COMMON_weapon_ui.psarc"
    header = ORIGINAL.read_bytes()[:0x100]
    try:
        with ORIGINAL.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        retail = PSARC(str(source_plain))
        if retail.manifest()[ENTRY - 1] != ENTRY_NAME:
            raise AssertionError(retail.manifest()[ENTRY - 1])
        replacement = FONT.read_bytes()
        if len(replacement) != retail.entries[ENTRY]["orig_size"]:
            raise AssertionError("font size differs from retail entry")

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: replacement}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), header, str(OUTPUT))
        if OUTPUT.stat().st_size > ORIGINAL.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        if OUTPUT.stat().st_size < ORIGINAL.stat().st_size:
            with OUTPUT.open("ab") as stream:
                stream.write(b"\0" * (ORIGINAL.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as stream:
            check = PSARC(SDATReader(stream, 0))
            if check.manifest() != retail.manifest():
                raise AssertionError("manifest changed")
            if check.read_entry(ENTRY) != replacement:
                raise AssertionError("font readback mismatch")
        report = {
            "original": str(ORIGINAL),
            "font": str(FONT),
            "output": str(OUTPUT),
            "original_sha256": sha(ORIGINAL),
            "font_sha256": sha(FONT),
            "output_sha256": sha(OUTPUT),
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=True, indent=2))
    finally:
        obj = locals().get("retail")
        if obj is not None:
            obj.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
