#!/usr/bin/env python3
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / os.environ.get("LEGACY_SOURCE", "battle_review_legacy_fit/legacy_fit_01.jsonl")
TSV = ROOT / os.environ.get("LEGACY_TSV", "battle_review_next/legacy_fit_01.tsv")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "32_build_battle_safe_full.py", "legacy_fit_builder")
review_builder = load(ROOT / "47_build_battle_c117_review4000_test.py", "legacy_fit_candidates")
from bmd_rebuild import BmdFile
from psarc import PSARC

source_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
source = {int(row["uid"]): row for row in source_rows}
translations = {}
format_errors = []
for no, line in enumerate(TSV.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip() or "\t" not in line:
        format_errors.append(no)
        continue
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

for row in source_rows:
    uid = int(row["uid"])
    jp = row["jp"]
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

uids = [int(row["uid"]) for row in source_rows]
empty = [uid for uid in uids if not translations.get(uid, "").strip()]
slash = [uid for uid in uids if source[uid]["jp"].count("/") != translations.get(uid, "").count("/")]
japanese = [uid for uid in uids if re.search(load_table("_INLINE")[0], translations.get(uid, ""))]
missing = [uid for uid in uids if uid not in translations]
extra = sorted(set(translations) - set(uids))
print(json.dumps({
    "uid_count": len(uids), "translation_count": len(translations), "occurrences": occurrences,
    "failure_count": len(failures), "failed_uid_count": len({row["uid"] for row in failures}),
    "format_errors": format_errors, "empty": empty, "slash": slash, "japanese": japanese,
    "missing": missing, "extra": extra
}, ensure_ascii=False))
grouped = defaultdict(list)
for row in failures:
    grouped[row["uid"]].append(row)
for uid in sorted(grouped):
    rows = grouped[uid]
    sizes = [size for _, size in rows[0]["sizes"] if size is not None]
    print("\t".join([str(uid), str(min(row["span"] for row in rows)),
                     str(min(sizes) if sizes else "NA"), rows[0]["jp"], rows[0]["ko"]]))
