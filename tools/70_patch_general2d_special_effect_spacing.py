#!/usr/bin/env python3
"""Add visual spacing before the weapon special-effect suffix digits."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
SOURCE = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC\General2d.psarc.sdat"
)
BUILD = ROOT / "korean_build_v3"
OUTPUT = BUILD / "General2d_special_effect_spacing_fixed_20260812.psarc.sdat"
REPORT = BUILD / "general2d_special_effect_spacing_fixed_20260812_report.json"
ENTRY = 3751
REPLACEMENTS = (
    (165620, "특수효과2", "특수효과 2"),
    (165864, "특수효과1", "특수효과 1"),
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in (
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
    ):
        path = BUILD / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                mapping[row["hangul"]] = row["proxy"]
    return mapping


def encode_text(text: str, mapping: dict[str, str]) -> bytes:
    missing = [char for char in text if "가" <= char <= "힣" and char not in mapping]
    if missing:
        raise AssertionError(f"unmapped Hangul: {missing}")
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    source_plain = BUILD / "GENERAL2D_special_effect_source.psarc"
    output_plain = BUILD / "GENERAL2D_special_effect_fixed.psarc"
    source_archive = None
    candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        mapping = load_map()
        changes = []
        for offset, current_text, target_text in REPLACEMENTS:
            record_length = struct.unpack(">I", entry[offset : offset + 4])[0]
            current = encode_text(current_text, mapping)
            target = encode_text(target_text, mapping)
            if len(target) > record_length - 1:
                raise AssertionError(f"replacement does not fit at {offset}")
            start = offset + 4
            end = start + record_length
            actual = bytes(entry[start:end]).rstrip(b"\0")
            if actual != current:
                raise AssertionError(
                    f"unexpected text at {offset}: {actual.hex()} != {current.hex()}"
                )
            entry[start:end] = target + b"\0" * (record_length - len(target))
            changes.append(
                {
                    "offset": offset,
                    "record_length": record_length,
                    "current": current_text,
                    "target": target_text,
                    "encoded_bytes": len(target),
                }
            )

        fixed = rebuild_fixed_blocks(source_plain, {ENTRY: bytes(entry)}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            if candidate.manifest() != source_archive.manifest():
                raise AssertionError("manifest mismatch")
            mismatches = []
            for index in range(candidate.n):
                expected = bytes(entry) if index == ENTRY else source_archive.read_entry(index)
                if candidate.read_entry(index) != expected:
                    mismatches.append(index)
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE),
            "output": str(OUTPUT),
            "source_sha256": sha(SOURCE),
            "output_sha256": sha(OUTPUT),
            "entry": ENTRY,
            "changes": changes,
            "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if source_archive is not None:
            source_archive.f.close()
        if candidate is not None and hasattr(candidate.f, "close"):
            candidate.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
