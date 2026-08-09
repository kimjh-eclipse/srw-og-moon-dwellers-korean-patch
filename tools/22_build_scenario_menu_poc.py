#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch the scenario/mode selection strings in GENERAL2D's main WTD."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import csv
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader
from sdat_encode import encode


ENTRY = 3751
ENTRY_PATH = "/Dat/Window/WindowToolData/windowdataMain.wtd"

REPLACEMENTS = load_table('REPLACEMENTS')


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"{path} is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def load_proxy_map(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            row["hangul"]: row["proxy"]
            for row in csv.DictReader(stream, delimiter="\t")
        }


def proxy_encode(text: str, mapping: dict[str, str]) -> str:
    encoded = "".join(mapping.get(ch, ch) for ch in text)
    remaining = [ch for ch in encoded if 0xAC00 <= ord(ch) <= 0xD7A3]
    if remaining:
        raise ValueError(f"missing Korean proxies: {sorted(set(remaining))}")
    if len(encoded.encode("utf-8")) != len(text.encode("utf-8")):
        raise AssertionError("proxy encoding changed UTF-8 byte length")
    return encoded


def replace_length_prefixed(
    data: bytearray, source: str, translated: str, mapping: dict[str, str]
) -> tuple[int, int, int]:
    source_bytes = source.encode("utf-8")
    translated_bytes = proxy_encode(translated, mapping).encode("utf-8")
    if len(translated_bytes) > len(source_bytes):
        raise ValueError(
            f"translation too long ({len(translated_bytes)} > {len(source_bytes)}): "
            f"{source} -> {translated}"
        )

    count = 0
    start = 0
    while True:
        pos = data.find(source_bytes + b"\0", start)
        if pos < 0:
            break
        if pos < 4:
            raise ValueError(f"missing length prefix at {pos}: {source}")
        declared = struct.unpack(">I", data[pos - 4 : pos])[0]
        if declared != len(source_bytes) + 1:
            raise ValueError(
                f"unexpected length at {pos}: {declared} != {len(source_bytes) + 1}"
            )
        # Preserve the serialized field width while ending the C string at the
        # translated text.  The remaining declared payload is zero-filled.
        payload = translated_bytes + b"\0" * (declared - len(translated_bytes))
        data[pos : pos + declared] = payload
        count += 1
        start = pos + declared
    if not count:
        raise ValueError(f"source text not found: {source}")
    return count, len(source_bytes), len(translated_bytes)


def main() -> None:
    root = Path("work_ogmd")
    build = root / "korean_build_v3"
    source_psarc = root / "GENERAL2D.psarc"
    source_sdat = root / "original_backups" / "General2d.psarc.sdat.orig"
    out_psarc = build / "GENERAL2D_menu_poc.psarc"
    out_sdat = build / "General2d_menu_poc.psarc.sdat"

    proxy_map = load_proxy_map(build / "korean_font_map.tsv")
    psarc = PSARC(str(source_psarc))
    names = psarc.manifest()
    if names[ENTRY - 1] != ENTRY_PATH:
        raise AssertionError(f"entry mismatch: {names[ENTRY - 1]}")
    original_entry = psarc.read_entry(ENTRY)
    patched_entry = bytearray(original_entry)

    report = []
    for source, translated in REPLACEMENTS.items():
        count, source_len, translated_len = replace_length_prefixed(
            patched_entry, source, translated, proxy_map
        )
        report.append((source, translated, count, source_len, translated_len))
    if len(patched_entry) != len(original_entry):
        raise AssertionError("WTD entry size changed")

    rebuild(str(source_psarc), {ENTRY: bytes(patched_entry)}, str(out_psarc))
    pad_file(out_psarc, source_psarc.stat().st_size)
    encode(str(out_psarc), source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        check_psarc = PSARC(SDATReader(stream, 0))
        check_entry = check_psarc.read_entry(ENTRY)
    if check_entry != bytes(patched_entry):
        raise AssertionError("SDAT -> PSARC -> WTD readback mismatch")

    for source, translated, count, source_len, translated_len in report:
        print(
            f"{count}x {source} -> {translated} "
            f"({translated_len}/{source_len} bytes)"
        )
    print(f"PSARC size: {out_psarc.stat().st_size}")
    print(f"SDAT size: {out_sdat.stat().st_size}")
    print(f"SDAT sha256: {hashlib.sha256(out_sdat.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
