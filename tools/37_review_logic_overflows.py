#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit a complete, reproducible review queue for LOGIC fixed-field overflows."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path("work_ogmd")
OUT = ROOT / "review_v1"


def load_builder():
    path = ROOT / "27_build_logic_translation.py"
    spec = importlib.util.spec_from_file_location("logic_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def kind(path: str) -> str:
    if "/Dat/FixedData/" in path:
        return "fixed_data"
    if "/talk/" in path:
        return "dialogue"
    if path.endswith(".csb"):
        return "caption"
    return "other"


def main() -> None:
    builder = load_builder()
    translations = builder.load_translations(ROOT / "translated")
    manual_fits = builder.load_manual_fits(ROOT / "review_v1")
    mapping = builder.load_proxy_map(ROOT / "korean_build_v3" / "korean_font_map.tsv")
    aliases = ROOT / "korean_build_v3" / "compact_aliases.tsv"
    if aliases.exists():
        mapping.update(builder.load_proxy_map(aliases))

    rows = [
        json.loads(line)
        for line in (ROOT / "extract" / "master.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    queue = []
    by_kind: Counter[str] = Counter()
    by_file: Counter[str] = Counter()
    for row in rows:
        if row["psarc"] != "LOGIC":
            continue
        target = builder.normalize_translation(
            builder.translated_text(row, translations, manual_fits)
        )
        fitted = builder.fit_translation(target, row["blen"], mapping, row.get("file", ""))
        encoded_size = len(builder.proxy_encode(fitted, mapping))
        if encoded_size <= row["blen"]:
            continue
        entry = {
            "uid": row["uid"],
            "file": row.get("file", ""),
            "kind": kind(row.get("file", "")),
            "capacity": row["blen"],
            "encoded_size": encoded_size,
            "overflow_bytes": encoded_size - row["blen"],
            "source": row["text"],
            "target": fitted,
        }
        queue.append(entry)
        by_kind[entry["kind"]] += 1
        by_file[entry["file"]] += 1

    queue.sort(key=lambda item: (item["kind"], -item["overflow_bytes"], item["file"], item["uid"]))
    OUT.mkdir(exist_ok=True)
    (OUT / "logic_overflow_queue.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in queue),
        encoding="utf-8",
        newline="\n",
    )
    report = {
        "total": len(queue),
        "by_kind": dict(sorted(by_kind.items())),
        "top_files": by_file.most_common(30),
    }
    (OUT / "logic_overflow_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
