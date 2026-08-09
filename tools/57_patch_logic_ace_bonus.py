#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correct every Ace/Full Tune bonus record on a known-good Logic SDAT.

The three bonus tables use fixed byte spans.  This patch edits those spans in
place, preserves all entry/container sizes, and also carries forward the BGM
ideographic-space fix so the two Logic corrections can be installed together.
"""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


BONUS_FILES = {
    "ACEBonusData.dat": 3,
    "AceFullTuneBonusData.dat": 4,
    "Temp_AceFullTuneBonusData.dat": 28,
}
BGM_ENTRY = 6


# Entries whose existing translation loses a condition, changes the target of
# the effect, or contains a known project terminology error.  UID 198 occurs in
# two tables and intentionally receives one identical translation.
UID_TARGETS = load_table('UID_TARGETS')


def load_maps(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    forward: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        path = root / "korean_build_v3" / name
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                forward[row["hangul"]] = row["proxy"]
                reverse[row["proxy"]] = row["hangul"]
    return forward, reverse


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    proxied = "".join(mapping.get(char, char) for char in text)
    missing = sorted(
        {
            char
            for char in proxied
            if 0xAC00 <= ord(char) <= 0xD7A3 or 0x3130 <= ord(char) <= 0x318F
        }
    )
    if missing:
        raise ValueError(f"missing Korean proxies: {missing}")
    return proxied.encode("utf-8")


def proxy_decode(raw: bytes, reverse: dict[str, str]) -> str:
    text = raw.split(b"\0", 1)[0].decode("utf-8")
    return "".join(reverse.get(char, char) for char in text)


def replace_first(text: str, old: str, new: str) -> str:
    pos = text.find(old)
    if pos < 0:
        return text
    return text[:pos] + new + text[pos + len(old) :]


def correct_text(uid: int, jp: str, current: str) -> str:
    # Compact full-width Latin characters, digits and symbols.  Besides making
    # Korean UI typography consistent, this recovers enough compressed space
    # to keep every PSARC block at its original physical size.
    text = unicodedata.normalize("NFKC", current)

    replacements = load_table('replacements')
    for old, new in replacements.items():
        text = text.replace(old, new)

    if load_table("_INLINE")[0] in jp:
        text = re.sub(load_table("_INLINE")[4], load_table("_INLINE")[5], text)

    if load_table("_INLINE")[1] in jp:
        text = text.replace(load_table("_INLINE")[6], load_table("_INLINE")[7])
        # In an Ace-bonus description, unqualified "부대" means the Ace's
        # own twin unit and does not broaden the effect to every ally.
        text = text.replace(load_table("_INLINE")[7], load_table("_INLINE")[8])

    if load_table("_INLINE")[9] in jp and load_table("_INLINE")[10] not in text:
        text = replace_first(text, load_table("_INLINE")[11], load_table("_INLINE")[10])
    if load_table("_INLINE")[12] in jp and load_table("_INLINE")[13] not in text:
        text = replace_first(text, load_table("_INLINE")[14], load_table("_INLINE")[13])
    if load_table("_INLINE")[2] in jp:
        text = text.replace(load_table("_INLINE")[15], load_table("_INLINE")[16])
    if load_table("_INLINE")[3] in jp:
        text = text.replace(load_table("_INLINE")[17], load_table("_INLINE")[18])

    if uid in UID_TARGETS:
        marker = jp[0] if jp and jp[0] in "UaC[^Rd" else ""
        target = UID_TARGETS[uid]
        # Fragment records have a leading byte that is part of their table
        # layout.  Preserve it unless the explicit target already contains it.
        return marker + target if marker and not target.startswith(marker) else target
    return text


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"rebuilt Logic exceeds source size: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sdat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("korean_build_v3"))
    parser.add_argument("--tag", default="ace_bonus_bgm_fix_20260807")
    parser.add_argument(
        "--include-bgm",
        action="store_true",
        help="also replace ideographic spaces in BGMData (disabled for isolated testing)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    source_plain = output_dir / f"Logic_{args.tag}_source.psarc"
    out_plain = output_dir / f"Logic_{args.tag}.psarc"
    out_sdat = output_dir / f"Logic_{args.tag}.psarc.sdat"

    with args.source_sdat.open("rb") as source, source_plain.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)

    archive = PSARC(str(source_plain))
    manifest = archive.manifest()
    for basename, entry in BONUS_FILES.items():
        if Path(manifest[entry - 1]).name != basename:
            raise AssertionError(f"unexpected entry {entry}: {manifest[entry - 1]}")
    if args.include_bgm and manifest[BGM_ENTRY - 1] != "/Dat/FixedData/BGMData.dat":
        raise AssertionError(f"unexpected BGM entry: {manifest[BGM_ENTRY - 1]}")

    forward, reverse = load_maps(root)
    entry_data = {entry: bytearray(archive.read_entry(entry)) for entry in BONUS_FILES.values()}
    rows = []
    for line in (root / "extract" / "master.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        basename = Path(row.get("file", "")).name
        if basename in BONUS_FILES and int(row["entry"]) == BONUS_FILES[basename]:
            rows.append(row)

    changes = []
    seen_spans: set[tuple[int, int, int]] = set()
    overflow = []
    for row in rows:
        entry = int(row["entry"])
        offset = int(row["off"])
        capacity = int(row["blen"])
        span = (entry, offset, capacity)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        current = proxy_decode(entry_data[entry][offset : offset + capacity], reverse)
        target = correct_text(int(row["uid"]), row["text"], current)
        encoded = proxy_encode(target, forward)
        if len(encoded) > capacity:
            overflow.append(
                {
                    "entry": entry,
                    "uid": int(row["uid"]),
                    "capacity": capacity,
                    "encoded": len(encoded),
                    "jp": row["text"],
                    "current": current,
                    "target": target,
                }
            )
            continue
        entry_data[entry][offset : offset + capacity] = encoded + b"\0" * (capacity - len(encoded))
        if target != current:
            changes.append(
                {
                    "entry": entry,
                    "file": Path(row["file"]).name,
                    "uid": int(row["uid"]),
                    "capacity": capacity,
                    "encoded": len(encoded),
                    "jp": row["text"],
                    "before": current,
                    "after": target,
                }
            )

    if overflow:
        overflow_path = output_dir / f"logic_{args.tag}_overflow.json"
        overflow_path.write_text(
            json.dumps(overflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        raise ValueError(f"{len(overflow)} Ace translations exceed fixed spans: {overflow_path}")

    replacements = {entry: bytes(data) for entry, data in entry_data.items()}
    bgm_replacements = 0
    if args.include_bgm:
        bgm = archive.read_entry(BGM_ENTRY)
        ideographic_space = "\u3000".encode("utf-8")
        bgm_replacements = bgm.count(ideographic_space)
        patched_bgm = bgm.replace(ideographic_space, b"   ")
        if len(patched_bgm) != len(bgm):
            raise AssertionError("BGMData size changed")
        replacements[BGM_ENTRY] = patched_bgm
    fixed_report = rebuild_fixed_blocks(source_plain, replacements, out_plain)
    compressed_psarc_size = out_plain.stat().st_size
    encode(str(out_plain), args.source_sdat.read_bytes()[:0x100], str(out_sdat))
    pad_file(out_sdat, args.source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        check = PSARC(SDATReader(stream, 0))
        if check.manifest() != manifest:
            raise AssertionError("Logic manifest changed")
        for entry, data in replacements.items():
            if check.read_entry(entry) != data:
                raise AssertionError(f"entry {entry} SDAT readback mismatch")

    report = {
        "source_sdat": str(args.source_sdat.resolve()),
        "source_sha256": hashlib.sha256(args.source_sdat.read_bytes()).hexdigest(),
        "records_audited": len(rows),
        "unique_spans_audited": len(seen_spans),
        "records_changed": len(changes),
        "fixed_span_overflows": 0,
        "bgm_ideographic_spaces_replaced": bgm_replacements,
        "compression_backend": "zopfli-fixed-block",
        "compressed_psarc_size_before_padding": compressed_psarc_size,
        **fixed_report,
        "logical_psarc_size": logical_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
        "changes": changes,
    }
    report_path = output_dir / f"logic_{args.tag}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "changes"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
