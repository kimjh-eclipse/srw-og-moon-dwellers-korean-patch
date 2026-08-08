#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply all translated main-WTD strings and pack a size-preserving GENERAL2D."""
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader
from sdat_encode import encode


ENTRY = 3751
TOKEN = re.compile(
    r"(<[^>]*>|%[-+0-9.]*[A-Za-z]|\\[nrt]|@[A-Za-z0-9_]*|"
    r"\[[^\]]*\]|\{[^}]*\})"
)

OVERRIDES = load_table('OVERRIDES')

POST_REPLACE = load_table('POST_REPLACE')

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


def polish(jp: str, ko: str) -> str:
    if jp in OVERRIDES:
        return OVERRIDES[jp]
    for source, target in POST_REPLACE.items():
        ko = ko.replace(source, target)
    ko = re.sub(load_table("_INLINE")[0], "", ko)
    # Japanese personal names use an equals sign as a separator.  Korean UI
    # should use a normal space, while control tags such as <C=...> remain
    # untouched.
    ko = re.sub(load_table("_INLINE")[1], " ", ko)
    ko = re.sub(r"\s{2,}", " ", ko)
    return ko.strip()


def truncate_utf8(text: str, budget: int) -> str:
    output = []
    used = 0
    for ch in text:
        size = len(ch.encode("utf-8"))
        if used + size > budget:
            break
        output.append(ch)
        used += size
    return "".join(output)


def fit_preserving_tokens(text: str, capacity: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= capacity:
        return text, False
    parts = TOKEN.split(text)
    fixed = sum(
        len(part.encode("utf-8"))
        for part in parts
        if part and TOKEN.fullmatch(part)
    )
    capacity = max(capacity, fixed)
    visible_budget = max(0, capacity - fixed)
    result = []
    remaining = visible_budget
    for part in parts:
        if not part:
            continue
        if TOKEN.fullmatch(part):
            result.append(part)
            continue
        fitted = truncate_utf8(part, remaining)
        result.append(fitted)
        remaining -= len(fitted.encode("utf-8"))
    fitted_text = "".join(result)
    if len(fitted_text.encode("utf-8")) > capacity:
        raise AssertionError("token-preserving fit exceeded capacity")
    return fitted_text, True


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    output = "".join(mapping.get(ch, ch) for ch in text)
    missing = {
        ch
        for ch in output
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F
    }
    if missing:
        raise ValueError(f"missing Korean proxies: {sorted(missing)}")
    encoded = output.encode("utf-8")
    if len(encoded) > len(text.encode("utf-8")):
        raise AssertionError("proxy encoding increased byte length")
    return encoded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--blocks",
        default="",
        help="Comma-separated logical WTD block ids or ranges, e.g. 0-5,8",
    )
    parser.add_argument("--tag", default="full_v3")
    parser.add_argument(
        "--nllb-reserve",
        type=int,
        default=3,
        help="Extra UTF-8 bytes reserved in machine-translated fields",
    )
    parser.add_argument("--offset-min", type=int, default=0)
    parser.add_argument("--offset-max", type=int, default=-1)
    parser.add_argument(
        "--menu1-test",
        action="store_true",
        help="Override only the unit/weapon upgrade header for a boot test.",
    )
    parser.add_argument(
        "--menu-fixes",
        action="store_true",
        help="Apply the reviewed General2D menu and pilot-training fixes.",
    )
    args = parser.parse_args()

    menu_icon_overrides: dict[str, str] = {}
    if args.menu_fixes:
        spec = importlib.util.spec_from_file_location(
            "general2d_menu_fixes",
            Path(__file__).with_name("55_patch_general2d_pilot_training.py"),
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load General2D menu overrides")
        menu_fixes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(menu_fixes)
        OVERRIDES.update(menu_fixes.TEXT_OVERRIDES)
        menu_icon_overrides = dict(menu_fixes.ICON_OVERRIDES)
        # User-reviewed wording for the unit/weapon upgrade header.
        OVERRIDES[load_table("_INLINE")[4]] = load_table("_INLINE")[2]
        OVERRIDES[load_table("_INLINE")[5]] = load_table("_INLINE")[3]
        # Ability submenu and its connected selection/help screens.
        OVERRIDES.update(
            load_table('OVERRIDES_update')
        )
    elif args.menu1_test:
        # Keep the test inside the proven clean-base full-build pipeline.
        OVERRIDES[load_table("_INLINE")[4]] = load_table("_INLINE")[2]
        OVERRIDES[load_table("_INLINE")[5]] = load_table("_INLINE")[3]

    selected_blocks = None
    if args.blocks:
        selected_blocks = set()
        for item in args.blocks.split(","):
            if "-" in item:
                lo, hi = (int(value) for value in item.split("-", 1))
                selected_blocks.update(range(lo, hi + 1))
            else:
                selected_blocks.add(int(item))

    root = Path("work_ogmd")
    build = root / "korean_build_v3"
    source_psarc = root / "GENERAL2D.psarc"
    source_sdat = root / "original_backups" / "General2d.psarc.sdat.orig"
    out_psarc = build / f"GENERAL2D_{args.tag}.psarc"
    out_sdat = build / f"General2d_{args.tag}.psarc.sdat"

    rows = [
        json.loads(line)
        for line in (root / "general2d_translation" / "wtd_strings.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if selected_blocks is not None:
        rows = [
            row for row in rows if row["offset"] // 65536 in selected_blocks
        ]
    rows = [
        row
        for row in rows
        if row["offset"] >= args.offset_min
        and (args.offset_max < 0 or row["offset"] <= args.offset_max)
    ]
    proxy_map = load_proxy_map(build / "korean_font_map.tsv")
    compact_map = build / "compact_aliases.tsv"
    if compact_map.exists():
        proxy_map.update(load_proxy_map(compact_map))
    psarc = PSARC(str(source_psarc))
    original_entry = psarc.read_entry(ENTRY)
    patched = bytearray(original_entry)
    shortened = 0
    menu_icon_records = 0

    for row in rows:
        offset = row["offset"]
        length = row["length"]
        capacity = row["capacity"]
        source_bytes = row["jp"].encode("utf-8")
        declared = struct.unpack(">I", patched[offset : offset + 4])[0]
        actual = bytes(patched[offset + 4 : offset + 4 + length])
        if declared != length or actual != source_bytes + b"\0":
            raise AssertionError(f"WTD source mismatch at {offset}")

        polished = polish(row["jp"], row["ko"])
        manual_override = row["jp"] in OVERRIDES
        fit_capacity = (
            capacity - args.nllb_reserve
            if row["source"] == "nllb" and not manual_override
            else capacity
        )
        if len(proxy_encode(polished, proxy_map)) <= fit_capacity:
            fitted, was_shortened = polished, False
        else:
            fitted, was_shortened = fit_preserving_tokens(
                polished, max(0, fit_capacity)
            )
        shortened += int(was_shortened)
        encoded = proxy_encode(fitted, proxy_map)
        payload = encoded + b"\0" * (length - len(encoded))
        patched[offset + 4 : offset + 4 + length] = payload

    for source, target in menu_icon_overrides.items():
        needle = source.encode("utf-8") + b"\0"
        cursor = 0
        while True:
            payload_offset = patched.find(needle, cursor)
            if payload_offset < 0:
                break
            record_offset = payload_offset - 4
            if (
                record_offset >= 0
                and struct.unpack(">I", patched[record_offset:payload_offset])[0]
                == len(needle)
            ):
                encoded = proxy_encode(target, proxy_map)
                if len(encoded) > len(needle) - 1:
                    raise ValueError(f"menu icon replacement does not fit: {source}")
                patched[payload_offset : payload_offset + len(needle)] = (
                    encoded + b"\0" * (len(needle) - len(encoded))
                )
                menu_icon_records += 1
            cursor = payload_offset + len(needle)

    if args.menu_fixes and menu_icon_records == 0:
        raise AssertionError("no terrain icon records were patched")

    rebuild(str(source_psarc), {ENTRY: bytes(patched)}, str(out_psarc))
    pad_file(out_psarc, source_psarc.stat().st_size)
    encode(str(out_psarc), source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback = PSARC(SDATReader(stream, 0)).read_entry(ENTRY)
    if readback != bytes(patched):
        raise AssertionError("SDAT -> PSARC -> WTD readback mismatch")

    report = {
        "patched_occurrences": len(rows),
        "selected_blocks": sorted(selected_blocks) if selected_blocks else "all",
        "offset_range": [args.offset_min, args.offset_max],
        "shortened_occurrences": shortened,
        "menu_icon_records": menu_icon_records,
        "psarc_size": out_psarc.stat().st_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
    }
    (build / f"general2d_{args.tag}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
