#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append WTD-only Korean glyphs without changing the proven V3 mappings."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import ImageFont


def load_builder():
    path = Path(__file__).with_name("16_build_korean_font.py")
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def is_korean(ch: str) -> bool:
    return 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F


def main() -> None:
    root = Path("work_ogmd")
    source_dir = root / "korean_build_v3"
    out_dir = root / "korean_build_v4a"
    out_dir.mkdir(parents=True, exist_ok=True)
    builder = load_builder()

    original = (root / "font_dump" / "font.bin").read_bytes()
    font = bytearray((source_dir / "font_ko.bin").read_bytes())
    with (source_dir / "korean_font_map.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        old_rows = list(csv.DictReader(stream, delimiter="\t"))
    old_chars = {row["hangul"] for row in old_rows}
    used_slots = {int(row["slot"]) for row in old_rows}
    used_proxy_cps = {int(row["proxy_cp"][2:], 16) for row in old_rows}

    extra_chars = set()
    for line in (
        root / "general2d_translation" / "wtd_strings.jsonl"
    ).read_text(encoding="utf-8").splitlines():
        extra_chars.update(ch for ch in json.loads(line)["ko"] if is_korean(ch))
    new_chars = sorted(extra_chars - old_chars)

    _, old_translated_chars = builder.read_tsv_texts(root / "translated")
    source_chars = set(
        (root / "extract_all" / "used_chars.txt").read_text(encoding="utf-8")
    )
    protected_cps = builder.protect_codepoints(
        source_chars, old_translated_chars
    )
    protected_slots = {
        slot
        for cp in protected_cps
        if (slot := builder.metric_slot(original, cp)) not in (None, 0)
    }
    occupied_cps = {ord(ch) for ch in source_chars | old_translated_chars}

    candidates = []
    seen_slots = set()
    raw = []
    for cp in range(0x800, 0x10000):
        if 0xD800 <= cp <= 0xDFFF or cp in occupied_cps:
            continue
        slot = builder.metric_slot(original, cp)
        if slot in (None, 0) or slot in protected_slots:
            continue
        raw.append((0 if 0x4E00 <= cp <= 0x9FFF else 1, cp, slot))
    for _priority, cp, slot in sorted(raw):
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        if slot in used_slots or cp in used_proxy_cps:
            continue
        candidates.append((cp, slot))

    if len(candidates) < len(new_chars):
        raise ValueError(
            f"append capacity {len(candidates)} < new glyphs {len(new_chars)}"
        )

    face = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 28)
    appended = []
    for ch, (proxy_cp, slot) in zip(new_chars, candidates):
        builder.inject_cell(font, slot, builder.render_glyph(ch, face))
        appended.append(
            {
                "hangul": ch,
                "hangul_cp": f"U+{ord(ch):04X}",
                "proxy": chr(proxy_cp),
                "proxy_cp": f"U+{proxy_cp:04X}",
                "slot": str(slot),
                "metric": original[
                    builder.metric_offset(original, proxy_cp) :
                    builder.metric_offset(original, proxy_cp) + 4
                ].hex(),
            }
        )

    if font[: builder.TEXTURE_OFFSET] != original[: builder.TEXTURE_OFFSET]:
        raise AssertionError("metric/header region changed")

    (out_dir / "font_ko.bin").write_bytes(font)
    fields = ["hangul", "hangul_cp", "proxy", "proxy_cp", "slot", "metric"]
    with (out_dir / "korean_font_map.tsv").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in old_rows:
            writer.writerow({field: row[field] for field in fields})
        writer.writerows(appended)

    report = {
        "base": "V3",
        "existing_glyphs_unchanged": len(old_rows),
        "appended_glyphs": len(appended),
        "appended": appended,
        "remaining_candidates": len(candidates) - len(appended),
        "font_sha256": hashlib.sha256(font).hexdigest(),
    }
    (out_dir / "build_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
