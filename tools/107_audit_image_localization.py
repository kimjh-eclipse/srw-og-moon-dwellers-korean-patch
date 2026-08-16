#!/usr/bin/env python3
"""Audit OGMD raster paths for locale-specific and text-bearing candidates."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "image_localization" / "inventory.json"
OUTPUT = ROOT / "image_localization" / "audit_candidates.json"
KEYWORDS = re.compile(
    r"(title|help|guide|lesson|option|manual|tutorial|caption|message|logo|"
    r"name|explain|summary|system|text|word|console|command|q&a|staff|credit)",
    re.I,
)
LOCALE = re.compile(r"(^|[/@_])(ja|jp|jpn)([/@_.]|$)", re.I)


def main() -> None:
    rows = json.loads(INVENTORY.read_text(encoding="utf-8"))
    locale_rows = [row for row in rows if LOCALE.search(row["path"])]
    keyword_rows = [row for row in rows if KEYWORDS.search(row["path"])]
    merged = {(row["archive"], row["entry"]): row for row in locale_rows + keyword_rows}
    localized_manifest = json.loads(
        (ROOT / "image_localization" / "localized_manifest.json").read_text(encoding="utf-8")
    )
    localized = {(row["archive"], row["path"]) for row in localized_manifest}
    for row in merged.values():
        archive = row["archive"].split("_")[0]
        row["localized"] = (archive, row["path"]) in localized
    candidates = sorted(merged.values(), key=lambda row: (row["archive"], row["path"]))
    OUTPUT.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"all_images={len(rows)}")
    print(f"locale_path_images={len(locale_rows)}")
    print(f"keyword_path_images={len(keyword_rows)}")
    print(f"merged_candidates={len(candidates)}")
    print(f"already_localized={sum(bool(row['localized']) for row in candidates)}")
    print(f"remaining_candidates={sum(not row['localized'] for row in candidates)}")
    directory_counts = collections.Counter(
        (row["archive"].split("_")[0], str(Path(row["path"]).parent))
        for row in candidates
        if not row["localized"]
    )
    for (archive, directory), count in directory_counts.most_common():
        print(f"{count:4}  {archive:9} {directory}")


if __name__ == "__main__":
    main()
