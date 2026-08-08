#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append only missing Battle Korean glyphs to the verified V3/V4 font map.

The existing proxy assignments and glyph cells are immutable.  This writes a
new V5 font/map beside them and never touches an installed package.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path("work_ogmd")
V3 = ROOT / "korean_build_v3"
V4 = ROOT / "korean_build_v4"
OUT = ROOT / "korean_build_v5"


def load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main() -> None:
    font = load_module("16_build_korean_font.py", "font_builder")
    battle = load_module("32_build_battle_safe_full.py", "battle_builder")
    original = (ROOT / "font_dump" / "font.bin").read_bytes()
    current = bytearray((V4 / "font_ko.bin").read_bytes())
    main_rows = rows(V3 / "korean_font_map.tsv")
    alias_rows = rows(V3 / "compact_aliases.tsv")
    char_map = {r["hangul"]: r["proxy"] for r in main_rows + alias_rows}
    translations = {
        row["jp"]: row["ko"]
        for row in map(
            json.loads,
            (ROOT / "battle_translation" / "battle_unique_draft.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    missing: set[str] = set()
    for row in map(json.loads, (ROOT / "extract_bmd" / "master.jsonl").read_text(encoding="utf-8").splitlines()):
        text = battle.normalize_battle_text(
            battle.BATTLE_REVIEW_OVERRIDES.get(
                row["jp"], battle.BATTLE_OVERRIDES.get(row["jp"], translations[row["jp"]])
            )
        )
        text = text.strip()
        for ch in text:
            if font.is_korean(ch) and ch not in char_map:
                missing.add(ch)
    used_slots = {int(r["slot"]) for r in main_rows + alias_rows}
    used_proxies = {int(r["proxy_cp"][2:], 16) for r in main_rows + alias_rows}
    source_chars = set((ROOT / "extract_all" / "used_chars.txt").read_text(encoding="utf-8"))
    protected = font.protect_codepoints(source_chars, set())
    protected_slots = {
        slot for cp in protected if (slot := font.metric_slot(original, cp)) not in (None, 0)
    }
    slots = [s for s in range(1, font.FONT_SLOTS) if s not in used_slots | protected_slots]
    occupied = {ord(ch) for ch in source_chars} | used_proxies
    proxies = [
        cp for cp in range(0x4E00, 0xA000)
        if cp not in occupied and font.metric_offset(original, cp) is not None
    ]
    chars = sorted(missing)
    if len(chars) > min(len(slots), len(proxies)):
        raise RuntimeError(f"font capacity {min(len(slots), len(proxies))} < {len(chars)}")
    from PIL import ImageFont
    face = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 28)
    added = []
    for ch, slot, proxy_cp in zip(chars, slots, proxies):
        metric = font.metric_offset(original, proxy_cp)
        assert metric is not None
        font.inject_cell(current, slot, font.render_glyph(ch, face))
        x, y = slot % font.METRIC_CELLS_X, slot // font.METRIC_CELLS_X
        current[metric : metric + 4] = bytes((0, font.CELL_SIZE, x, y))
        added.append({
            "hangul": ch, "hangul_cp": f"U+{ord(ch):04X}",
            "proxy": chr(proxy_cp), "proxy_cp": f"U+{proxy_cp:04X}",
            "slot": slot, "metric": original[metric : metric + 4].hex(),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "font_ko.bin").write_bytes(current)
    shutil.copy2(V3 / "compact_aliases.tsv", OUT / "compact_aliases.tsv")
    header = "hangul\thangul_cp\tproxy\tproxy_cp\tslot\tmetric\n"
    lines = [header]
    for r in main_rows + added:
        lines.append("\t".join(str(r[key]) for key in ("hangul", "hangul_cp", "proxy", "proxy_cp", "slot", "metric")) + "\n")
    (OUT / "korean_font_map.tsv").write_text("".join(lines), encoding="utf-8", newline="\n")
    (OUT / "battle_font_extension.json").write_text(
        json.dumps({"added_glyphs": len(added), "chars": "".join(chars), "safe_slots": len(slots)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"added_glyphs": len(added), "safe_slots": len(slots), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
