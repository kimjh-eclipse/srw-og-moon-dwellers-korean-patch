#!/usr/bin/env python3
"""Inventory raster assets stored in the final OGMD PSARC/SDAT archives."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader


IMAGE_EXTENSIONS = {".dds", ".png", ".jpg", ".jpeg", ".tga", ".bmp", ".gtf"}


def inventory_archive(path: Path) -> list[dict[str, object]]:
    with path.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        names = archive.manifest()
        rows = []
        for entry, name in enumerate(names, 1):
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGE_EXTENSIONS:
                continue
            metadata = archive.entries[entry]
            rows.append(
                {
                    "archive": path.name,
                    "entry": entry,
                    "path": name,
                    "extension": suffix,
                    "size": metadata["orig_size"],
                }
            )
        return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    rows = []
    for archive in args.archives:
        current = inventory_archive(archive)
        rows.extend(current)
        extensions = collections.Counter(row["extension"] for row in current)
        print(f"{archive.name}: {len(current)} images {dict(extensions)}")

    for row in rows:
        print(
            f"{row['archive']}\t{row['entry']:5}\t{row['size']:10}\t{row['path']}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
