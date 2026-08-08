#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a boot-safe C117 test containing all reviewed battle rows.

The known-good fixed-size C117 container is retained.  Human-reviewed rows
are added only when their encoded Korean text fits the original BMD record;
The review set is prevalidated so every selected row fits its original span.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v5"
BASE_PSARC = BUILD / "Battle_C117_android0137_v5.psarc"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_texts(builder, text: str, jp: str):
    text = builder.normalize_battle_text(text)
    text = builder.normalize_dialogue_quotes(text, jp)
    candidates = [text, text.replace("@　", "@"), text.replace("　", " ")]
    candidates += [item.replace("……", "…") for item in candidates[-2:]]
    if text.startswith("「") and text.endswith("」"):
        candidates.append(text[1:-1])
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            yield item


def main() -> None:
    safe = load(ROOT / "42_build_battle_c117_manual_v2.py", "safe_review4000")
    builder = load(ROOT / "32_build_battle_safe_full.py", "review4000_source")
    if not BASE_PSARC.is_file():
        raise FileNotFoundError(BASE_PSARC)
    mapping = builder.load_map(BUILD)
    reviews = builder.load_parallel_review_overrides(ROOT)
    if len(reviews) != 31076:
        raise AssertionError(f"expected 31076 reviewed sources, got {len(reviews)}")

    archive = PSARC(str(BASE_PSARC))
    names = archive.manifest()
    name_to_entry = {name: index + 1 for index, name in enumerate(names)}
    master = [
        json.loads(line)
        for line in (ROOT / "extract_bmd" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bmd_cache = {}
    patches = {}
    report_rows = []
    stats = Counter()

    for row in master:
        ko = reviews.get(row["jp"])
        if ko is None:
            continue
        stats["reviewed_occurrences"] += 1
        entry = name_to_entry[row["file"]]
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry))
        bmd = bmd_cache[entry]
        if row["idx"] >= len(bmd.records):
            stats["index_mismatch"] += 1
            continue
        span = bmd.records[row["idx"]][1]
        chosen = None
        encoded_size = None
        for candidate in candidate_texts(builder, ko, row["jp"]):
            raw = builder.encode(candidate, mapping)
            if raw is not None and len(raw) + 1 <= span:
                chosen = candidate
                encoded_size = len(raw) + 1
                break
        if chosen is None:
            stats["skipped_oversize_or_unencodable"] += 1
            continue
        key = (row["file"], row["idx"])
        patches[key] = (row["jp"], chosen)
        stats["applied_occurrences"] += 1
        report_rows.append({
            "file": row["file"], "idx": row["idx"], "jp": row["jp"],
            "ko": chosen, "span": span, "encoded_size_with_nul": encoded_size,
        })

    safe.SPECIFIC_PATCHES = patches
    safe.BASE_PSARC_OVERRIDE = BASE_PSARC
    safe.USE_ZOPFLI = True
    # V5 already contains the earlier hand-picked fixes.  Reapplying them
    # through the current mapping can exceed their original fixed spans.
    safe.INCLUDE_DEFAULT_TRANSLATIONS = False
    safe.OUTPUT_STEM = "Battle_C117_review31076_fitall_final"
    safe.REPORT_NAME = "battle_c117_review31076_fitall_final_build_report.json"
    safe.REVIEW_GROUP = "human-reviewed UID 0..31075 + all legacy fit overlays"
    safe.main()

    result = {
        "reviewed_unique_sources": len(reviews),
        **stats,
        "specific_patch_count": len(patches),
        "base_psarc": str(BASE_PSARC),
        "output_sdat": str(BUILD / "Battle_C117_review31076_fitall_final.psarc.sdat"),
        "rows": report_rows,
    }
    if (
        stats["index_mismatch"]
        or stats["skipped_oversize_or_unencodable"] != 0
    ):
        raise AssertionError(f"review selection failures: {dict(stats)}")
    (BUILD / "battle_c117_review31076_fitall_final_selection_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
