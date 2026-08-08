#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a non-installed variable-length FixedData probe.

The normal localization builder preserves every original byte span.  This
probe grows one KeyWordData string by one byte and rebuilds the containing
PSARC entry with its new uncompressed length.  It is deliberately isolated
from the production package: a successful readback proves archive integrity;
runtime testing will determine whether the game's FixedData parser has any
hidden absolute offsets that also need relocating.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild_var
from sdat import SDATReader
from sdat_encode import encode

import importlib.util


ROOT = Path("work_ogmd")
# Start from the current production Korean PSARC so the probe preserves every
# already-installed translation and adds only the variable-length test.
SOURCE_PSARC = ROOT / "korean_build_v3" / "LOGIC_full_fixed.psarc"
SOURCE_SDAT = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUT_PSARC = ROOT / "korean_build_v3" / "Logic_variable_fixeddata_probe.psarc"
OUT_SDAT = ROOT / "korean_build_v3" / "Logic_variable_fixeddata_probe.psarc.sdat"
TARGET_UID = 1921
TARGET_FILE = "/Dat/FixedData/KeyWordData.dat"


def load_builder():
    path = ROOT / "27_build_logic_translation.py"
    spec = importlib.util.spec_from_file_location("logic_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builder = load_builder()
    master = [
        json.loads(line)
        for line in (ROOT / "extract" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    row = next(
        item
        for item in master
        if item["psarc"] == "LOGIC"
        and item["uid"] == TARGET_UID
        and item["file"] == TARGET_FILE
    )
    translations = builder.load_translations(ROOT / "translated")
    proxy_map = builder.load_proxy_map(ROOT / "korean_build_v3" / "korean_font_map.tsv")
    proxy_map.update(builder.load_proxy_map(ROOT / "korean_build_v3" / "compact_aliases.tsv"))

    text = builder.normalize_translation(builder.translated_text(row, translations))
    encoded = builder.proxy_encode(text, proxy_map)
    if len(encoded) <= row["blen"]:
        raise AssertionError("probe target no longer exceeds its original field")

    psarc = PSARC(str(SOURCE_PSARC))
    original = psarc.read_entry(row["entry"])
    start = row["off"]
    end = start + row["blen"]
    if original[start:end] != row["text"].encode("utf-8"):
        raise AssertionError("source span does not match manifest")
    # Replace a manifest span (which excludes its following NUL); all later
    # record bytes move together while the original terminator is retained.
    patched = original[:start] + encoded + original[end:]
    if len(patched) != len(original) + len(encoded) - row["blen"]:
        raise AssertionError("unexpected entry size")

    rebuild_var(str(SOURCE_PSARC), {row["entry"]: patched}, str(OUT_PSARC))
    encode(str(OUT_PSARC), SOURCE_SDAT.read_bytes()[:0x100], str(OUT_SDAT))
    with OUT_SDAT.open("rb") as stream:
        rebuilt = PSARC(SDATReader(stream, 0)).read_entry(row["entry"])
    if rebuilt != patched:
        raise AssertionError("SDAT/PSARC readback mismatch")
    print(
        json.dumps(
            {
                "uid": TARGET_UID,
                "file": TARGET_FILE,
                "old_entry_size": len(original),
                "new_entry_size": len(patched),
                "old_field_bytes": row["blen"],
                "new_text_bytes": len(encoded),
                "sdat_sha256": hashlib.sha256(OUT_SDAT.read_bytes()).hexdigest(),
                "output": str(OUT_SDAT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
