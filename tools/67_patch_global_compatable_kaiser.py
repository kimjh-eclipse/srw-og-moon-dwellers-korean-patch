#!/usr/bin/env python3
"""Normalize all installed Compatable Kaiser Korean spelling variants."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
GAME = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
)
BUILD = ROOT / "korean_build_v3"
PACKAGES = ("Common", "General2d", "Logic", "Battle")
VARIANTS = ("콤파치블", "컴파치블", "콤패티블", "컴패티블")
TARGET = "컴패터블"


def load_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        with (BUILD / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    encoded = "".join(mapping.get(char, char) for char in text).encode("utf-8")
    if len(encoded) != 12:
        raise AssertionError(f"unexpected encoded length for {text!r}: {len(encoded)}")
    return encoded


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process(package: str, scan_only: bool) -> dict:
    source = GAME / f"{package}.psarc.sdat"
    output = BUILD / f"{package}_compatable_kaiser_20260812.psarc.sdat"
    report_path = BUILD / f"{package.lower()}_compatable_kaiser_20260812_report.json"
    mapping = load_map()
    target = proxy_encode(TARGET, mapping)
    needles = {variant: proxy_encode(variant, mapping) for variant in VARIANTS}

    modified: dict[int, bytes] = {}
    counts = {variant: 0 for variant in VARIANTS}
    changed_entries: list[int] = []
    with source.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        manifest = archive.manifest()
        for entry in range(archive.n):
            original = archive.read_entry(entry)
            patched = original
            for variant, needle in needles.items():
                count = patched.count(needle)
                if count:
                    counts[variant] += count
                    patched = patched.replace(needle, target)
            if patched != original:
                if len(patched) != len(original):
                    raise AssertionError(f"entry size changed: {package} {entry}")
                modified[entry] = patched
                changed_entries.append(entry)

    result = {
        "package": package,
        "source": str(source),
        "source_sha256": sha(source),
        "counts": counts,
        "total_replacements": sum(counts.values()),
        "changed_entries": changed_entries,
    }
    if scan_only or not modified:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    source_plain = BUILD / f"{package}_compatable_source.psarc"
    output_plain = BUILD / f"{package}_compatable.psarc"
    header = source.read_bytes()[:0x100]
    try:
        with source.open("rb") as encrypted, source_plain.open("wb") as plain:
            logical_size, _ = decrypt_stream(encrypted, 0, plain)
        rebuild(str(source_plain), modified, str(output_plain))
        encode(str(output_plain), header, str(output))
        if output.stat().st_size > source.stat().st_size:
            raise AssertionError(
                f"{package} SDAT grew: {output.stat().st_size} > {source.stat().st_size}"
            )
        if output.stat().st_size < source.stat().st_size:
            with output.open("ab") as stream:
                stream.write(b"\0" * (source.stat().st_size - output.stat().st_size))

        mismatches: list[int] = []
        remaining = {variant: 0 for variant in VARIANTS}
        with source.open("rb") as base_stream, output.open("rb") as candidate_stream:
            base = PSARC(SDATReader(base_stream, 0))
            candidate = PSARC(SDATReader(candidate_stream, 0))
            if candidate.manifest() != manifest:
                raise AssertionError(f"{package} manifest mismatch")
            for entry in range(candidate.n):
                actual = candidate.read_entry(entry)
                expected = modified.get(entry, base.read_entry(entry))
                if actual != expected:
                    mismatches.append(entry)
                for variant, needle in needles.items():
                    remaining[variant] += actual.count(needle)
        if mismatches:
            raise AssertionError(f"{package} semantic mismatches: {mismatches[:20]}")
        if any(remaining.values()):
            raise AssertionError(f"{package} variants remain: {remaining}")

        result.update(
            {
                "output": str(output),
                "output_sha256": sha(output),
                "size": output.stat().st_size,
                "source_psarc_size": logical_size,
                "output_psarc_size": output_plain.stat().st_size,
                "semantic_mismatches": 0,
                "remaining_variants": remaining,
            }
        )
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        for temporary in (source_plain, output_plain):
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument(
        "--packages",
        default=",".join(PACKAGES),
        help="Comma-separated package basenames",
    )
    args = parser.parse_args()
    packages = tuple(name.strip() for name in args.packages.split(",") if name.strip())
    unknown = sorted(set(packages) - set(PACKAGES))
    if unknown:
        raise ValueError(f"unknown packages: {unknown}")
    results = [process(package, args.scan_only) for package in packages]
    summary = {
        "target": TARGET,
        "packages": results,
        "total_replacements": sum(row["total_replacements"] for row in results),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
