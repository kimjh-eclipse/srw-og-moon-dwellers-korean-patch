#!/usr/bin/env python3
"""Issue #6 Battle BMD 교체 후 엔트리 크기 증감을 계산한다."""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC
from sdat import SDATReader

ROOT = Path(__file__).resolve().parent


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PATCH = load("ogmd_issue6_patch", "188_patch_issue6_20260909.py")


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "issue6_battle_audit.jsonl").read_text(encoding="utf-8").splitlines()]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["entry"]].append(row)
    results = []
    with PATCH.SOURCE_BATTLE.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, entry_rows in grouped.items():
            data = archive.read_entry(entry)
            bmd = BmdFile(data)
            texts = bmd.texts()
            replacements = {}
            for row in entry_rows:
                before = PATCH.decode_proxy(texts[row["idx"]].encode("utf-8"))
                after = PATCH.RAIO_LINES.get(row["jp"], PATCH.normalize_names(before))
                if after != before:
                    replacements[row["idx"]] = PATCH.proxy(after).decode("utf-8")
            if replacements:
                rebuilt = bmd.replace_variable(replacements)
                results.append({"entry": entry, "file": entry_rows[0]["file"],
                                "changes": len(replacements), "old": len(data),
                                "new": len(rebuilt), "delta": len(rebuilt) - len(data)})
    for row in sorted(results, key=lambda r: r["delta"], reverse=True):
        print(json.dumps(row, ensure_ascii=False))
    print("positive", sum(r["delta"] > 0 for r in results),
          "max", max(r["delta"] for r in results),
          "total", sum(r["delta"] for r in results))


if __name__ == "__main__":
    main()
