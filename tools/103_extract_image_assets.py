#!/usr/bin/env python3
"""Extract selected OGMD raster assets from an SDAT-wrapped PSARC."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader


def safe_relative_path(name: str) -> Path:
    return Path(*[part for part in name.replace("\\", "/").split("/") if part])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--match", required=True, help="case-insensitive path regex")
    args = parser.parse_args()

    pattern = re.compile(args.match, re.IGNORECASE)
    count = 0
    with args.archive.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, name in enumerate(archive.manifest(), 1):
            if not pattern.search(name):
                continue
            destination = args.output / safe_relative_path(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read_entry(entry))
            print(f"{entry}\t{name}\t{destination}")
            count += 1
    print(f"extracted={count}")


if __name__ == "__main__":
    main()
