#!/usr/bin/env python3
"""Independently validate the directly translated UID 21238..26237 batch."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC


ROOT = Path(__file__).resolve().parent
START = 0
END = 19137
BASE_PSARC = ROOT / "korean_build_v5" / "Battle_C117_android0137_v5.psarc"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builder = load(ROOT / "32_build_battle_safe_full.py", "review5000_builder")
    checker = load(ROOT / "47_build_battle_c117_review4000_test.py", "review5000_checker")
    mapping = builder.load_map(ROOT / "korean_build_v5")

    expected = list(range(START, END + 1))
    draft = [
        json.loads(line)
        for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    all_reviews = builder.load_parallel_review_overrides(ROOT)
    selected = {
        uid: {
            "uid": uid,
            "source": draft[uid]["jp"],
            "new_ko": all_reviews[draft[uid]["jp"]],
        }
        for uid in expected
    }
    by_source = {}
    source_uids = {}
    slash_errors = 0
    for uid in expected:
        row = selected[uid]
        source = draft[uid]["jp"]
        if row["source"] != source:
            raise AssertionError(f"source mismatch at UID {uid}")
        ko = row["new_ko"]
        if not ko.strip():
            raise AssertionError(f"empty translation at UID {uid}")
        if source.count("/") != ko.count("/"):
            slash_errors += 1
        by_source[source] = ko
        source_uids[source] = uid
    if slash_errors:
        raise AssertionError(f"slash errors: {slash_errors}")

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
    occurrences = 0
    failures = []
    for row in master:
        ko = by_source.get(row["jp"])
        if ko is None:
            continue
        occurrences += 1
        entry = name_to_entry[row["file"]]
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry))
        bmd = bmd_cache[entry]
        span = bmd.records[row["idx"]][1]
        fits = False
        for candidate in checker.candidate_texts(builder, ko, row["jp"]):
            raw = builder.encode(candidate, mapping)
            if raw is not None and len(raw) + 1 <= span:
                fits = True
                break
        if not fits:
            failures.append({"uid": source_uids[row["jp"]], "file": row["file"], "idx": row["idx"], "jp": row["jp"], "span": span})

    result = {
        "uid_start": START,
        "uid_end": END,
        "translated_unique": len(selected),
        "slash_errors": slash_errors,
        "actual_occurrences": occurrences,
        "fit_failures": len(failures),
        "fit_failed_unique_uids": len({row["uid"] for row in failures}),
        "all_reviewed_unique_sources": len(all_reviews),
        "next_uid": END + 1,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures and START != 0:
        raise AssertionError(json.dumps(failures[:10], ensure_ascii=False))
    if len(all_reviews) != len(draft):
        raise AssertionError(
            f"expected {len(draft)} reviewed sources, got {len(all_reviews)}"
        )


if __name__ == "__main__":
    main()
