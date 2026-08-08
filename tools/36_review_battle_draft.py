#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only QA queue for the effective Battle dialogue draft."""

from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path("work_ogmd")
JP = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
DOUBLE_SPACE = re.compile(r" {2,}")
# Raw NLLB failures must remain visible in the report even when the builder
# suppresses their broken glyph at runtime.  Otherwise a clean display could
# be mistaken for a fully reviewed translation.
NLLB_UNKNOWN = "⁇"
FOREIGN_ARTIFACT = re.compile(r"[\u0900-\u1fff]|oci_Latn")
OUT = ROOT / "review_v1"


def load_builder():
    path = ROOT / "32_build_battle_safe_full.py"
    spec = importlib.util.spec_from_file_location("battle_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builder = load_builder()
    rows = [
        json.loads(line)
        for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    findings = []
    counts: Counter[str] = Counter()
    for row in rows:
        raw = row["ko"]
        manually_repaired = row["jp"] in builder.BATTLE_REVIEW_OVERRIDES or row["jp"] in builder.BATTLE_OVERRIDES
        if NLLB_UNKNOWN in raw and not manually_repaired:
            findings.append({"kind": "raw_unknown_placeholder", "jp": row["jp"], "ko": raw})
            counts["raw_unknown_placeholder"] += 1
        if FOREIGN_ARTIFACT.search(raw) and not manually_repaired:
            findings.append({"kind": "raw_foreign_artifact", "jp": row["jp"], "ko": raw})
            counts["raw_foreign_artifact"] += 1
        target = builder.BATTLE_REVIEW_OVERRIDES.get(
            row["jp"], builder.BATTLE_OVERRIDES.get(row["jp"], row["ko"])
        )
        target = builder.normalize_battle_text(target)
        if JP.search(target):
            findings.append({"kind": "japanese_remaining", "jp": row["jp"], "ko": target})
            counts["japanese_remaining"] += 1
        if "「" in target or "」" in target or "『" in target or "』" in target:
            findings.append({"kind": "quote_review", "jp": row["jp"], "ko": target})
            counts["quote_review"] += 1
        if DOUBLE_SPACE.search(target):
            findings.append({"kind": "double_space", "jp": row["jp"], "ko": target})
            counts["double_space"] += 1
    OUT.mkdir(exist_ok=True)
    (OUT / "battle_findings.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in findings),
        encoding="utf-8",
        newline="\n",
    )
    report = {
        "battle_unique_rows": len(rows),
        "manual_overrides": len(builder.BATTLE_OVERRIDES) + len(builder.BATTLE_REVIEW_OVERRIDES),
        "findings": dict(sorted(counts.items())),
        "total_findings": len(findings),
    }
    (OUT / "battle_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
