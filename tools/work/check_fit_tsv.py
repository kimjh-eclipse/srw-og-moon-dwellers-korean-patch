#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
START = int(os.environ["FIT_START"])
END = int(os.environ["FIT_END"])
TSV = ROOT / os.environ["FIT_TSV"]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "32_build_battle_safe_full.py", "tsv_fit_builder")
review_builder = load(ROOT / "47_build_battle_c117_review4000_test.py", "tsv_fit_candidates")
from bmd_rebuild import BmdFile
from psarc import PSARC

draft = {}
for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        uid = int(row["uid"])
        if START <= uid <= END:
            draft[uid] = row["jp"]

translations = {}
for line in TSV.read_text(encoding="utf-8").splitlines():
    if line.strip():
        uid, text = line.split("\t", 1)
        translations[int(uid)] = text

master_by_jp = defaultdict(list)
for line in (ROOT / "extract_bmd" / "master.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        master_by_jp[row["jp"]].append(row)

mapping = builder.load_map(ROOT / "korean_build_v5")
archive = PSARC(str(ROOT / "korean_build_v5" / "Battle_C117_android0137_v5.psarc"))
name_to_entry = {name: index + 1 for index, name in enumerate(archive.manifest())}
bmd_cache = {}
failures = []
occurrences = 0

for uid in range(START, END + 1):
    jp = draft[uid]
    ko = translations.get(uid, "")
    for source_row in master_by_jp.get(jp, []):
        occurrences += 1
        entry = name_to_entry[source_row["file"]]
        if entry not in bmd_cache:
            bmd_cache[entry] = BmdFile(archive.read_entry(entry))
        span = bmd_cache[entry].records[source_row["idx"]][1]
        candidate_sizes = []
        chosen = None
        for candidate in review_builder.candidate_texts(builder, ko, jp):
            raw = builder.encode(candidate, mapping)
            size = None if raw is None else len(raw) + 1
            candidate_sizes.append((candidate, size))
            if size is not None and size <= span:
                chosen = candidate
                break
        if chosen is None:
            failures.append({"uid": uid, "span": span, "jp": jp, "ko": ko, "sizes": candidate_sizes})

print(json.dumps({"uid_count": len(draft), "translation_count": len(translations),
                  "occurrences": occurrences, "failure_count": len(failures),
                  "failed_uid_count": len({row['uid'] for row in failures})}, ensure_ascii=False))
grouped = defaultdict(list)
for row in failures:
    grouped[row["uid"]].append(row)
for uid in sorted(grouped):
    rows = grouped[uid]
    sizes = [size for _, size in rows[0]["sizes"] if size is not None]
    print("\t".join([str(uid), str(min(row["span"] for row in rows)),
                     str(min(sizes) if sizes else "NA"), rows[0]["jp"], rows[0]["ko"]]))
