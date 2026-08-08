#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "32_build_battle_safe_full.py", "fit_builder")
review_builder = load(ROOT / "47_build_battle_c117_review4000_test.py", "fit_candidates")

from bmd_rebuild import BmdFile
from psarc import PSARC

mapping = builder.load_map(ROOT / "korean_build_v5")
reviews = {}
for line in (ROOT / "battle_review_next" / "review_19238_20237.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    uid = int(row["uid"])
    if 19238 <= uid <= 19537:
        reviews[uid] = row

overrides = {}
override_path = ROOT / "battle_review_next" / "fit_override_19238_19537.tsv"
if override_path.is_file():
    for line in override_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            uid, text = line.split("\t", 1)
            overrides[int(uid)] = text

master_by_jp = defaultdict(list)
for line in (ROOT / "extract_bmd" / "master.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        master_by_jp[row["jp"]].append(row)

archive = PSARC(str(ROOT / "korean_build_v5" / "Battle_C117_android0137_v5.psarc"))
name_to_entry = {name: index + 1 for index, name in enumerate(archive.manifest())}
bmd_cache = {}
failures = []
occurrences = 0

for uid in sorted(reviews):
    row = reviews[uid]
    jp = row.get("source", row.get("jp"))
    ko = overrides.get(uid, row.get("new_ko", row.get("ko")))
    source_occurrences = master_by_jp.get(jp, [])
    if not source_occurrences:
        failures.append({"uid": uid, "reason": "no_master_occurrence", "jp": jp, "ko": ko})
        continue
    for source_row in source_occurrences:
        occurrences += 1
        entry = name_to_entry[source_row["file"]]
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry))
        bmd = bmd_cache[entry]
        span = bmd.records[source_row["idx"]][1]
        candidate_sizes = []
        chosen = None
        for candidate in review_builder.candidate_texts(builder, ko, jp):
            raw = builder.encode(candidate, mapping)
            size = None if raw is None else len(raw) + 1
            candidate_sizes.append([candidate, size])
            if size is not None and size <= span:
                chosen = candidate
                break
        if chosen is None:
            failures.append({
                "uid": uid,
                "file": source_row["file"],
                "idx": source_row["idx"],
                "span": span,
                "jp": jp,
                "ko": ko,
                "candidate_sizes": candidate_sizes,
            })

print(json.dumps({
    "uid_count": len(reviews),
    "occurrences": occurrences,
    "override_count": len(overrides),
    "failure_count": len(failures),
    "failed_uid_count": len({row["uid"] for row in failures}),
}, ensure_ascii=False))
grouped_failures = defaultdict(list)
for failure in failures:
    grouped_failures[failure["uid"]].append(failure)
for uid in sorted(grouped_failures):
    items = grouped_failures[uid]
    spans = [item.get("span", 0) for item in items]
    first = items[0]
    sizes = [
        size
        for _, size in first.get("candidate_sizes", [])
        if size is not None
    ]
    print("\t".join([
        str(uid), str(min(spans)), str(min(sizes) if sizes else "NA"),
        first["jp"], first["ko"],
    ]))
