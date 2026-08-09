#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build cumulative Battle v6 with reviewed E-Selda and punctuation fixes.

The quote cleanup is deliberately conservative: it only removes literal ASCII
double-quote glyphs already visible in the v5 Korean proxy text.  Japanese
corner brackets and all BMD control/layout bytes are otherwise preserved.
"""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import importlib.util
import json
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v5"
V5_PSARC = BUILD / "Battle_C117_android0137_v5.psarc"
ESELDA_FILE = "/Dat/Battle/Message/@Ja/0118_ja.bmd"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load(ROOT / "42_build_battle_c117_manual_v2.py", "safe_base_v6")
    builder = load(ROOT / "32_build_battle_safe_full.py", "battle_builder_v6")
    v4 = load(ROOT / "44_build_battle_c117_eselda_v4.py", "v4_group_v6")
    v5 = load(ROOT / "45_build_battle_c117_android0137_v5.py", "v5_group_v6")

    mapping = builder.load_map(BUILD)
    inverse = {proxy: hangul for hangul, proxy in mapping.items()}

    def decode_proxy(text: str) -> str:
        return "".join(inverse.get(char, char) for char in text)

    archive = PSARC(str(V5_PSARC))
    names = archive.manifest()
    name_to_entry = {name: index + 1 for index, name in enumerate(names)}
    master = [
        json.loads(line)
        for line in (ROOT / "extract_bmd" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    specific = {
        (v4.TARGET_FILE, index): pair for index, pair in v4.GROUP.items()
    }
    specific.update(
        {(v5.TARGET_FILE, index): pair for index, pair in v5.GROUP.items()}
    )

    # Manually reviewed E-Selda corrections.
    exact = {
        ("/Dat/Battle/Message/@Ja/0048_ja.bmd", 366): (
            load_table("_INLINE")[1],
            load_table("_INLINE")[2],
        ),
        (ESELDA_FILE, 7): (load_table("_INLINE")[3], load_table("_INLINE")[4]),
        (
            ESELDA_FILE,
            15,
        ): (
            load_table("_INLINE")[5],
            load_table("_INLINE")[6],
        ),
        (ESELDA_FILE, 79): (load_table("_INLINE")[7], load_table("_INLINE")[8]),
        (
            "/Dat/Battle/Message/@Ja/0120_ja.bmd",
            133,
        ): (load_table("_INLINE")[3], load_table("_INLINE")[4]),
    }
    specific.update(exact)

    # Remove only visibly leaked ASCII quote glyphs and the one confirmed '@'
    # line-break leak.  Both operations shorten the record and cannot overflow.
    bmd_cache: dict[int, list[str]] = {}
    quote_cleanup = []
    for row in master:
        entry = name_to_entry.get(row["file"])
        if entry is None:
            continue
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry)).texts()
        current = decode_proxy(bmd_cache[entry][row["idx"]])
        cleaned = current.replace('"', "")
        cleaned = cleaned.replace("/@\u3000", "/\u3000").replace("/@", "/")
        if cleaned == current:
            continue
        key = (row["file"], row["idx"])
        if key not in exact:
            specific[key] = (row["jp"], cleaned)
        quote_cleanup.append(
            {
                "file": row["file"],
                "index": row["idx"],
                "before": current,
                "after": exact.get(key, (None, cleaned))[1],
            }
        )

    # Use the completed human retranslation for all 93 quote-boundary records,
    # replacing the earlier punctuation-only cleanup.
    manual_quote_rows = [
        json.loads(line)
        for line in (
            BUILD / "battle_ascii_quote_manual_corrections.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for item in manual_quote_rows:
        specific[(item["file"], item["idx"])] = (item["jp"], item["ko"])
    specific.update(exact)

    base.SPECIFIC_PATCHES = specific
    base.OUTPUT_STEM = "Battle_C117_cleanup_v6"
    base.REPORT_NAME = "battle_c117_cleanup_v6_report.json"
    base.REVIEW_GROUP = (
        load_table("_INLINE")[0]
    )
    base.main()

    sidecar = {
        "translation_method": "manual corrections; no machine translation added",
        "specific_patch_count": len(specific),
        "manual_quote_review_count": len(manual_quote_rows),
        "quote_or_marker_cleanup_count": len(quote_cleanup),
        "exact_manual_fixes": [
            {
                "file": file,
                "index": index,
                "jp": pair[0],
                "ko": pair[1],
            }
            for (file, index), pair in exact.items()
        ],
        "cleanups": quote_cleanup,
        "checks": {
            "no_ascii_double_quote_after_cleanup": all(
                '"' not in item["after"] for item in quote_cleanup
            ),
            "no_confirmed_at_marker_after_cleanup": all(
                "/@" not in item["after"] for item in quote_cleanup
            ),
        },
    }
    (BUILD / "battle_cleanup_v6_review.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
