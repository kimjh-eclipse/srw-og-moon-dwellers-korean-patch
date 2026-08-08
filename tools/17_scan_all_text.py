#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan every entry in local PSARC files for UTF-8 Japanese text.

Unlike 11_extract_all.py, this deliberately does not filter by extension.
The output is intended for font-slot protection and coverage auditing, not
translation batching.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from textextract import extract

# Definite texture/shader payloads cannot contain runtime font text.  Skipping
# these avoids inflating 1.7 GiB of compressed GPU data while keeping every
# structured/unknown extension (.csb, .bn2, .ami, etc.) eligible.
NON_TEXT_PAYLOADS = {".dds", ".png", ".fpo", ".vpo"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "archives",
        nargs="*",
        default=["work_ogmd/COMMON.psarc", "work_ogmd/LOGIC.psarc"],
    )
    parser.add_argument("--out-dir", default="work_ogmd/extract_all")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    master_path = out_dir / "master_all.jsonl"

    unique_texts: dict[str, int] = {}
    used_chars: set[str] = set()
    path_stats: Counter[str] = Counter()
    archive_stats: dict[str, dict[str, int]] = {}
    total_rows = 0

    with master_path.open("w", encoding="utf-8", newline="\n") as master:
        for archive_arg in args.archives:
            archive_path = Path(archive_arg)
            archive_name = archive_path.stem.upper()
            psarc = PSARC(str(archive_path))
            names = psarc.manifest()
            matched_files = 0
            matched_rows = 0

            print(f"[{archive_name}] scanning all {len(names):,} entries", flush=True)
            for entry, internal_path in enumerate(names, start=1):
                if entry == 1 or entry % 100 == 0:
                    print(
                        f"  {entry:,}/{len(names):,} entries, "
                        f"{matched_rows:,} strings",
                        flush=True,
                    )
                suffix = Path(internal_path).suffix.lower() or "<none>"
                if suffix in NON_TEXT_PAYLOADS:
                    continue
                try:
                    data = psarc.read_entry(entry)
                except Exception as exc:
                    print(f"  read failed: #{entry} {internal_path}: {exc}", flush=True)
                    continue

                rows = extract(data)
                if not rows:
                    continue

                matched_files += 1
                path_stats[suffix] += len(rows)
                for row in rows:
                    text = row["text"]
                    uid = unique_texts.setdefault(text, len(unique_texts))
                    used_chars.update(text)
                    total_rows += 1
                    matched_rows += 1
                    master.write(
                        json.dumps(
                            {
                                "id": total_rows,
                                "psarc": archive_name,
                                "file": internal_path,
                                "entry": entry,
                                "off": row["off"],
                                "blen": row["blen"],
                                "uid": uid,
                                "text": text,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

            archive_stats[archive_name] = {
                "entries": len(names),
                "matched_files": matched_files,
                "strings": matched_rows,
            }

    ordered_unique = sorted(unique_texts, key=unique_texts.get)
    (out_dir / "unique_all.jsonl").write_text(
        "".join(
            json.dumps({"uid": uid, "jp": text}, ensure_ascii=False) + "\n"
            for uid, text in enumerate(ordered_unique)
        ),
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "used_chars.txt").write_text(
        "".join(sorted(used_chars)), encoding="utf-8", newline="\n"
    )

    report = {
        "archives": archive_stats,
        "strings": total_rows,
        "unique_strings": len(unique_texts),
        "unique_characters": len(used_chars),
        "strings_by_extension": dict(path_stats.most_common()),
    }
    (out_dir / "scan_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
