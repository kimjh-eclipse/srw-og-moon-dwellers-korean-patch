#!/usr/bin/env python3
"""Merge the directly translated UID 19238..20237 checkpoint."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "battle_review_next"
INPUTS = [
    REVIEW / "manual_19238_20237.partial.tsv",
    REVIEW / "agent_19838_19970.tsv",
    REVIEW / "agent_19971_20103.tsv",
    REVIEW / "agent_20104_20237.tsv",
]
OVERRIDES = [
    REVIEW / "fit_override_19238_19537.tsv",
    REVIEW / "fit_override_19538_19837.tsv",
    REVIEW / "fit_override_19838_20237.tsv",
]
OUTPUT = REVIEW / "review_19238_20237.jsonl"

draft = [
    json.loads(line)
    for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
translations = {}
for path in INPUTS:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        uid_text, ko = line.split("\t", 1)
        uid = int(uid_text)
        if uid in translations:
            raise AssertionError(f"duplicate UID {uid} in {path.name}:{number}")
        translations[uid] = ko

for path in OVERRIDES:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        uid_text, ko = line.split("\t", 1)
        uid = int(uid_text)
        if uid not in translations:
            raise AssertionError(f"unknown override UID {uid} in {path.name}:{number}")
        translations[uid] = ko

expected = list(range(19238, 20238))
if sorted(translations) != expected:
    raise AssertionError("UID range is incomplete or non-contiguous")

rows = []
for uid in expected:
    source = draft[uid]["jp"]
    ko = translations[uid]
    if not ko.strip() or source.count("/") != ko.count("/"):
        raise AssertionError(f"invalid translation at UID {uid}")
    rows.append({"uid": uid, "source": source, "new_ko": ko})

OUTPUT.write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
    encoding="utf-8",
)
print(json.dumps({"output": str(OUTPUT), "rows": len(rows)}, ensure_ascii=False))
