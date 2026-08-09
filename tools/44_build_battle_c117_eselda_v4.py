#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manual E-Selda Granteed battle-message group, layered on C117 safety rules."""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import importlib.util
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET_FILE = "/Dat/Battle/Message/@Ja/0118_ja.bmd"

# One coherent speaker/attack group.  Every line was translated directly from
# the Japanese source; no model output or draft translation is used here.
GROUP = load_table('GROUP')


def load_base():
    path = ROOT / "42_build_battle_c117_manual_v2.py"
    spec = importlib.util.spec_from_file_location("battle_manual_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in text
    )


def split_lines(text: str) -> list[str]:
    text = text.removeprefix("「").removesuffix("」")
    return [part.lstrip("\u3000") for part in text.replace("@", "/").split("/")]


def main() -> None:
    width_checks = []
    for index, (jp, ko) in GROUP.items():
        source_widths = [line_width(line) for line in split_lines(jp)]
        target_widths = [line_width(line) for line in split_lines(ko)]
        # Korean and Japanese both occupy full-width cells in this font.  Each
        # reviewed line must be no wider than its corresponding retail line.
        if len(source_widths) != len(target_widths) or any(
            target > source
            for target, source in zip(target_widths, source_widths)
        ):
            raise AssertionError(
                f"screen-width budget exceeded at {TARGET_FILE}#{index}: "
                f"{target_widths} > {source_widths}"
            )
        width_checks.append(
            {
                "file": TARGET_FILE,
                "index": index,
                "source_line_widths": source_widths,
                "target_line_widths": target_widths,
                "within_retail_width": True,
            }
        )

    base = load_base()
    base.SPECIFIC_PATCHES = {
        (TARGET_FILE, index): pair for index, pair in GROUP.items()
    }
    base.OUTPUT_STEM = "Battle_C117_eselda_v4"
    base.REPORT_NAME = "battle_c117_eselda_v4_report.json"
    base.REVIEW_GROUP = (
        "/Dat/Battle/Message/@Ja/0118_ja.bmd records 0-8, "
        "E-Selda / Granteed"
    )
    base.main()

    report_path = ROOT / "korean_build_v5" / base.REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["group_record_count"] = len(GROUP)
    report["group_screen_width_checks"] = width_checks
    report["checks"]["group_source_manually_reviewed"] = True
    report["checks"]["group_within_retail_screen_width"] = True
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
