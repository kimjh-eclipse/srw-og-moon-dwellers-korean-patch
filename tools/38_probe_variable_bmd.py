#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only-install probe for variable-length Battle BMD rebuilding.

Creates a disposable SDAT and proves that a longer BMD message survives a
PSARC + SDAT round trip.  It never copies anything into the game directory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import rebuild_var
from sdat import SDATReader
from sdat_encode import encode


ROOT = Path("work_ogmd")
SOURCE = ROOT / "original_backups" / "Battle.psarc.sdat.orig"
OUT = ROOT / "korean_build_v3" / "Battle_variable_bmd_probe.psarc.sdat"
TARGET = "/Dat/Battle/Message/@Ja/0002_ja.bmd"


def main() -> None:
    with SOURCE.open("rb") as stream:
        header = stream.read(0x100)
        psarc = PSARC(SDATReader(stream, 0))
        entry = psarc.manifest().index(TARGET) + 1
        original = psarc.read_entry(entry)
    bmd = BmdFile(original)
    original_text = bmd.texts()[0]
    expected = original_text + " 확장검증"
    changed = bmd.replace_variable({0: expected})
    raw_psarc = OUT.with_suffix(".psarc")
    # Rebuild needs the decrypted PSARC source already present in the workspace.
    psarc_source = ROOT / "BATTLE.psarc"
    if not psarc_source.exists():
        raise FileNotFoundError(psarc_source)
    rebuild_var(str(psarc_source), {entry: changed}, str(raw_psarc))
    encode(str(raw_psarc), header, str(OUT))
    with OUT.open("rb") as stream:
        rebuilt = PSARC(SDATReader(stream, 0))
        got = BmdFile(rebuilt.read_entry(entry)).texts()[0]
    if got != expected:
        raise AssertionError((got, expected))
    print({"ok": True, "size": OUT.stat().st_size, "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()})


if __name__ == "__main__":
    main()
