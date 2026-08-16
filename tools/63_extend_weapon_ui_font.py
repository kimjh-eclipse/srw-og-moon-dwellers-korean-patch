#!/usr/bin/env python3
"""Add General2D-only compact Hangul aliases to the matched V3 font.

The weapon table gives ``射程`` only six data bytes.  Three ordinary Hangul
syllables need nine UTF-8 bytes, so the full label ``사거리`` cannot fit.  The
aliases below reuse verified, otherwise-unused two-byte font codepoints.
They are deliberately kept in a separate map so Logic and Battle encoding is
unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import ImageFont


ROOT = Path(__file__).resolve().parent
BASE_FONT = ROOT / "korean_build_v3_matched" / "font_ko.bin"
ORIGINAL_FONT = ROOT / "font_dump" / "font.bin"
OUT_FONT = ROOT / "korean_build_v3_matched" / "font_ko_weapon_ui.bin"
OUT_MAP = ROOT / "korean_build_v3" / "general2d_compact_aliases.tsv"
OUT_LOGIC_MAP = ROOT / "korean_build_v3" / "logic_suffix_aliases.tsv"
REPORT = ROOT / "korean_build_v3_matched" / "weapon_ui_font_report.json"
FACE = Path("C:/Windows/Fonts/malgunbd.ttf")
FONT_SIZE = 28
ADVANCE = 22
SUFFIX_ADVANCE = 28

# C1 codepoints are encoded as two UTF-8 bytes.  In the retail font they map
# to four distinct, non-zero cells (101..104) and do not occur in game text.
GENERAL_ALIASES = (
    ("사", 0x0085, 101),
    ("거", 0x008C, 102),
    ("리", 0x008F, 103),
    ("개", 0x0097, 104),
    # Situation-report labels exceed their fixed fields by one byte.  These
    # two aliases preserve the requested spaces in "획득 자금", "총 자금",
    # and "총 격추수" without changing any Logic/Battle proxy encoding.
    ("획", 0x00B1, 110),
    # U+00B7 is also a hidden menu prefix in retail UI strings.  Rendering a
    # Hangul glyph there prepended "총" to 결정/무기 변경/방어/회피.
    # Use an otherwise-unused C1 metric instead.
    ("총", 0x0089, 3745),
    # U+0080 has an allocated metric record but no retail glyph.  Assign it
    # to verified free slot 763 so "변함 없음" fits its 12-byte map field.
    ("변", 0x0080, 763),
    # "精神" is a six-byte guide field.  Together with the existing compact
    # alias for 기, these two aliases preserve the complete label "정신기".
    ("정", 0x0081, 3738),
    ("신", 0x0082, 3739),
    # Scenario episode headers have only eight bytes.  A two-byte "제" alias
    # leaves room for the requested space in "제 %d화".
    ("제", 0x0088, 3744),
)

# Logic's skill-name fields have no spare byte before their dynamic level
# suffix (L8, L6, ...).  Keep these out of the General2D encoder so their
# intentionally wide metrics affect only the reviewed skill labels.
LOGIC_SUFFIX_ALIASES = (
    ("력", 0x0083, 3740),
    ("어", 0x0084, 3741),
    ("격", 0x0086, 3742),
    ("터", 0x0087, 3743),
)
ALIASES = GENERAL_ALIASES + LOGIC_SUFFIX_ALIASES

# These aliases occur only as the final syllable of the reviewed Logic skill
# labels.  A slightly wider advance creates the requested visual gap before
# the separately drawn dynamic suffix without consuming another data byte.
WIDE_SUFFIXES = {"력", "어", "격", "터"}


def load_builder():
    path = ROOT / "16_build_korean_font.py"
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    builder = load_builder()
    original = ORIGINAL_FONT.read_bytes()
    font = bytearray(BASE_FONT.read_bytes())
    face = ImageFont.truetype(str(FACE), FONT_SIZE)

    rows = []
    for hangul, proxy_cp, expected_slot in ALIASES:
        metric_off = builder.metric_offset(original, proxy_cp)
        if metric_off is None:
            raise AssertionError(f"missing metric U+{proxy_cp:04X}")
        actual_slot = builder.metric_slot(original, proxy_cp)
        if actual_slot == 0:
            x = expected_slot % builder.METRIC_CELLS_X
            y = expected_slot // builder.METRIC_CELLS_X
            font[metric_off + 2 : metric_off + 4] = bytes((x, y))
        elif actual_slot != expected_slot:
            raise AssertionError(
                f"slot mismatch U+{proxy_cp:04X}: {actual_slot} != {expected_slot}"
            )
        builder.inject_cell(font, expected_slot, builder.render_glyph(hangul, face))
        advance = SUFFIX_ADVANCE if hangul in WIDE_SUFFIXES else ADVANCE
        font[metric_off : metric_off + 2] = advance.to_bytes(2, "big")
        rows.append(
            {
                "hangul": hangul,
                "proxy": chr(proxy_cp),
                "proxy_cp": f"U+{proxy_cp:04X}",
                "slot": str(expected_slot),
                "metric": original[metric_off : metric_off + 4].hex(),
            }
        )

    OUT_FONT.write_bytes(font)
    fields = ("hangul", "proxy", "proxy_cp", "slot", "metric")
    general_count = len(GENERAL_ALIASES)
    for path, selected in (
        (OUT_MAP, rows[:general_count]),
        (OUT_LOGIC_MAP, rows[general_count:]),
    ):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=fields,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(selected)

    report = {
        "base_font": str(BASE_FONT),
        "output_font": str(OUT_FONT),
        "map": str(OUT_MAP),
        "logic_map": str(OUT_LOGIC_MAP),
        "base_sha256": digest(BASE_FONT.read_bytes()),
        "output_sha256": digest(font),
        "aliases": rows,
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # PowerShell's legacy CP949 console cannot print the C1 proxy characters.
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
