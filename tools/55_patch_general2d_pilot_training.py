#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch the pilot-training UI on top of a known-good GENERAL2D SDAT.

Only length-prefixed WTD records in entry 3751 are changed.  Record lengths,
the PSARC container size, and the SDAT size are preserved.
"""
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ENTRY = 3751

TEXT_OVERRIDES = load_table('TEXT_OVERRIDES')

# These tags draw Japanese terrain glyph icons.  Replacing the token with a
# one-character Korean label removes the remaining 空/陸/海/宇 on UI screens.
ICON_OVERRIDES = {
    # Keep the original terrain icons.  Attempts to replace them with Korean
    # labels either left the kanji unchanged or made the labels disappear.
    "<I=223>": "<I=223>",
    "<I=224>": "<I=224>",
    "<I=225>": "<I=225>",
    "<I=226>": "<I=226>",
}

# The options page uses six separate value-decoration records.  IDs 117/118
# are also used by unrelated pages, so blank only these verified offsets.
ICON_OFFSET_OVERRIDES = {
    675788: ("<X=00><I=117></X>", ""),
    675952: ("<X=00><I=118></X>", ""),
    1188640: ("<I=117>", ""),
    1188760: ("<I=118>", ""),
    1188880: ("<I=117>", ""),
    1189000: ("<I=118>", ""),
}


def load_proxy_map(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            row["hangul"]: row["proxy"]
            for row in csv.DictReader(stream, delimiter="\t")
        }


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    proxied = "".join(mapping.get(char, char) for char in text)
    missing = sorted({char for char in proxied if load_table("_INLINE")[0] <= char <= load_table("_INLINE")[1]})
    if missing:
        raise ValueError(f"missing Korean proxies: {missing}")
    return proxied.encode("utf-8")


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"rebuilt PSARC is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def patch_record(data: bytearray, offset: int, target: str, mapping: dict[str, str]) -> None:
    length = struct.unpack(">I", data[offset : offset + 4])[0]
    encoded = proxy_encode(target, mapping)
    if len(encoded) > length - 1:
        raise ValueError(
            f"target exceeds fixed field at {offset}: {len(encoded)} > {length - 1}: {target}"
        )
    data[offset + 4 : offset + 4 + length] = encoded + b"\0" * (length - len(encoded))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sdat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("korean_build_v3"))
    parser.add_argument("--tag", default="pilot_training_fix_20260807")
    parser.add_argument(
        "--rebuild-mode", choices=("standard", "fixed"), default="standard"
    )
    parser.add_argument(
        "--text-limit", type=int, default=0,
        help="Patch only the first N matching text records (0 patches all).",
    )
    parser.add_argument(
        "--no-icons", action="store_true",
        help="Do not replace terrain icon tokens.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    rows_path = root / "general2d_translation" / "wtd_strings.jsonl"
    build = root / "korean_build_v3"
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out_psarc = output_dir / f"GENERAL2D_{args.tag}.psarc"
    out_sdat = output_dir / f"General2d_{args.tag}.psarc.sdat"
    source_psarc = output_dir / f"GENERAL2D_{args.tag}_source.psarc"

    with args.source_sdat.open("rb") as source, source_psarc.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)

    mapping = load_proxy_map(build / "korean_font_map.tsv")
    compact = build / "compact_aliases.tsv"
    if compact.exists():
        mapping.update(load_proxy_map(compact))

    with args.source_sdat.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        patched = bytearray(archive.read_entry(ENTRY))

    text_offsets: list[tuple[int, str, str]] = []
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        source = row["jp"]
        if source in TEXT_OVERRIDES:
            text_offsets.append((int(row["offset"]), source, TEXT_OVERRIDES[source]))
    if args.text_limit:
        text_offsets = text_offsets[: args.text_limit]

    applied_text = 0
    for offset, source, target in text_offsets:
        length = struct.unpack(">I", patched[offset : offset + 4])[0]
        if length < 2:
            raise AssertionError(f"invalid WTD length at {offset}")
        patch_record(patched, offset, target, mapping)
        applied_text += 1

    applied_icons = 0
    for source, target in (() if args.no_icons else ICON_OVERRIDES.items()):
        needle = source.encode("utf-8") + b"\0"
        cursor = 0
        while True:
            payload = patched.find(needle, cursor)
            if payload < 0:
                break
            offset = payload - 4
            if offset >= 0 and struct.unpack(">I", patched[offset:payload])[0] == len(needle):
                patch_record(patched, offset, target, mapping)
                applied_icons += 1
            cursor = payload + len(needle)

    for offset, (source, target) in ICON_OFFSET_OVERRIDES.items():
        length = struct.unpack(">I", patched[offset : offset + 4])[0]
        current = patched[offset + 4 : offset + 4 + length].rstrip(b"\0").decode("utf-8")
        if current == target:
            continue
        if current != source:
            raise AssertionError(
                f"unexpected option icon record at {offset}: {current!r} != {source!r}"
            )
        patch_record(patched, offset, target, mapping)
        applied_icons += 1

    if args.rebuild_mode == "fixed":
        rebuild_report = rebuild_fixed_blocks(
            source_psarc, {ENTRY: bytes(patched)}, out_psarc
        )
    else:
        rebuild(source_psarc, {ENTRY: bytes(patched)}, out_psarc)
        compressed_size = out_psarc.stat().st_size
        # SDAT records the encrypted logical file length in its metadata.
        # Match the boot-tested source PSARC before encoding; padding only the
        # finished SDAT leaves that metadata different and the game rejects it.
        pad_file(out_psarc, logical_size)
        rebuild_report = {
            "rebuild_mode": "standard",
            "compressed_psarc_size": compressed_size,
            "psarc_padding_bytes": logical_size - compressed_size,
            "psarc_size_identical": True,
        }
    encode(str(out_psarc), args.source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, args.source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback = PSARC(SDATReader(stream, 0)).read_entry(ENTRY)
    if readback != bytes(patched):
        raise AssertionError("SDAT readback mismatch")

    report = {
        "source_sdat": str(args.source_sdat.resolve()),
        "source_sha256": hashlib.sha256(args.source_sdat.read_bytes()).hexdigest(),
        "text_records_patched": applied_text,
        "terrain_icon_records_patched": applied_icons,
        "logical_psarc_size": logical_size,
        **rebuild_report,
        "psarc_size": out_psarc.stat().st_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
    }
    report_path = output_dir / f"general2d_{args.tag}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
