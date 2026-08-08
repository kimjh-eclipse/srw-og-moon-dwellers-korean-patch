#!/usr/bin/env python3
"""Create UID-partitioned worklists for reviewed battle rows that did not fit.

This is analysis only.  It reads the same C117 base and font mapping used by
the safe builder and records the tightest original BMD span for every source.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bmd_rebuild import BmdFile
from psarc import PSARC


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    build = ROOT / "korean_build_v5"
    review_dir = ROOT / "battle_review_parallel"
    out_dir = ROOT / "battle_review_oversize"
    out_dir.mkdir(exist_ok=True)
    builder = load(ROOT / "32_build_battle_safe_full.py", "oversize_builder")
    chooser = load(ROOT / "47_build_battle_c117_review4000_test.py", "oversize_chooser")
    mapping = builder.load_map(build)

    reviewed = {}
    for path in sorted(review_dir.glob("review_unit_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            reviewed[row["jp"]] = {
                "uid": row["uid"], "jp": row["jp"], "current_ko": row["new_ko"]
            }

    archive = PSARC(str(build / "Battle_C117_android0137_v5.psarc"))
    names = archive.manifest()
    name_to_entry = {name: index + 1 for index, name in enumerate(names)}
    cache = {}
    failures = defaultdict(list)
    master = [
        json.loads(line)
        for line in (ROOT / "extract_bmd" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    for occurrence in master:
        source = reviewed.get(occurrence["jp"])
        if source is None:
            continue
        entry = name_to_entry[occurrence["file"]]
        if entry not in cache:
            cache[entry] = BmdFile(archive.read_entry(entry))
        span = cache[entry].records[occurrence["idx"]][1]
        fits = False
        sizes = []
        for candidate in chooser.candidate_texts(
            builder, source["current_ko"], source["jp"]
        ):
            raw = builder.encode(candidate, mapping)
            if raw is not None:
                sizes.append(len(raw) + 1)
                if len(raw) + 1 <= span:
                    fits = True
                    break
        if not fits:
            failures[source["uid"]].append(
                {
                    "file": occurrence["file"],
                    "idx": occurrence["idx"],
                    "span_with_nul": span,
                    "current_size_with_nul": min(sizes) if sizes else None,
                }
            )

    ranges = [(0, 1333), (1334, 2666), (2667, 3999)]
    summary = []
    for number, (lo, hi) in enumerate(ranges, 1):
        rows = []
        for uid in sorted(failures):
            if lo <= uid <= hi:
                source = reviewed[next(jp for jp, row in reviewed.items() if row["uid"] == uid)]
                occurrences = failures[uid]
                rows.append(
                    {
                        **source,
                        "target_max_bytes_with_nul": min(
                            item["span_with_nul"] for item in occurrences
                        ),
                        "failed_occurrence_count": len(occurrences),
                        "occurrences": occurrences,
                    }
                )
        path = out_dir / f"oversize_group_{number:02d}.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary.append({"group": number, "uid_range": [lo, hi], "sources": len(rows)})

    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "failed_occurrences": sum(len(items) for items in failures.values()),
                "unique_failed_sources": len(failures),
                "groups": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
