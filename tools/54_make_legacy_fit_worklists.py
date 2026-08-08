#!/usr/bin/env python3
"""Build 15 balanced worklists for legacy reviewed battle lines that do not fit."""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "battle_review_legacy_fit"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    OUT.mkdir(exist_ok=True)
    builder = load(ROOT / "32_build_battle_safe_full.py", "legacy_fit_builder")
    checker = load(ROOT / "47_build_battle_c117_review4000_test.py", "legacy_fit_checker")
    mapping = builder.load_map(ROOT / "korean_build_v5")
    reviews = builder.load_parallel_review_overrides(ROOT)
    draft = [
        json.loads(line)
        for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    uid_by_source = {draft[uid]["jp"]: uid for uid in range(19138)}

    archive = PSARC(str(ROOT / "korean_build_v5" / "Battle_C117_android0137_v5.psarc"))
    names = archive.manifest()
    name_to_entry = {name: index + 1 for index, name in enumerate(names)}
    bmd_cache = {}
    failed = defaultdict(list)
    for row in (
        json.loads(line)
        for line in (ROOT / "extract_bmd" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ):
        uid = uid_by_source.get(row["jp"])
        if uid is None:
            continue
        ko = reviews[row["jp"]]
        entry = name_to_entry[row["file"]]
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry))
        span = bmd_cache[entry].records[row["idx"]][1]
        fits = False
        for candidate in checker.candidate_texts(builder, ko, row["jp"]):
            raw = builder.encode(candidate, mapping)
            if raw is not None and len(raw) + 1 <= span:
                fits = True
                break
        if not fits:
            failed[uid].append({"file": row["file"], "idx": row["idx"], "span": span})

    rows = []
    for uid in sorted(failed):
        source = draft[uid]["jp"]
        occurrences = failed[uid]
        rows.append(
            {
                "uid": uid,
                "jp": source,
                "current_ko": reviews[source],
                "target_max_bytes_with_nul": min(item["span"] for item in occurrences),
                "failed_occurrence_count": len(occurrences),
                "occurrences": occurrences,
            }
        )

    chunk_count = 15
    boundaries = [round(len(rows) * index / chunk_count) for index in range(chunk_count + 1)]
    summary = []
    for index in range(chunk_count):
        chunk = rows[boundaries[index] : boundaries[index + 1]]
        path = OUT / f"legacy_fit_{index + 1:02d}.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in chunk),
            encoding="utf-8",
        )
        summary.append(
            {
                "chunk": index + 1,
                "rows": len(chunk),
                "first_uid": chunk[0]["uid"],
                "last_uid": chunk[-1]["uid"],
            }
        )

    print(json.dumps({"failed_unique": len(rows), "chunks": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
