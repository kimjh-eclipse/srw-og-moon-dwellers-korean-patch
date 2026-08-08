#!/usr/bin/env python3
"""Merge the directly translated, fixed-span UID 20238..21237 checkpoint."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "battle_review_next"
INPUTS = [
    REVIEW / "agent_20238_20570.tsv",
    REVIEW / "agent_20571_20903.tsv",
    REVIEW / "agent_20904_21237.tsv",
]
OUTPUT = REVIEW / "review_20238_21237.jsonl"

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

expected = list(range(20238, 21238))
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
