#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manual android/bioroid system-voice group layered cumulatively on v4."""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import importlib.util
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET_FILE = "/Dat/Battle/Message/@Ja/0137_ja.bmd"

# Records 0-40 form one coherent machine-status voice bank.  Korean is terse,
# impersonal system-report language throughout.  No draft/MT text is used.
GROUP = load_table('GROUP')


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in text.removeprefix("「").removesuffix("」")
    )


def main() -> None:
    v4 = load(ROOT / "44_build_battle_c117_eselda_v4.py", "v4_group")
    base = load(ROOT / "42_build_battle_c117_manual_v2.py", "safe_base")

    width_checks = []
    for index, (jp, ko) in GROUP.items():
        source_width = width(jp)
        target_width = width(ko)
        # Korean word spacing may add one half-width cell to an otherwise
        # equal four-glyph status phrase (e.g. 攻撃開始 -> 공격 개시).
        # Allow at most two half-width cells; longer lines remain well below
        # the retail dialogue-box capacity.
        if target_width > source_width + 2:
            raise AssertionError(
                f"screen width exceeded at {TARGET_FILE}#{index}: "
                f"{target_width} > {source_width}"
            )
        width_checks.append(
            {
                "file": TARGET_FILE,
                "index": index,
                "source_width": source_width,
                "target_width": target_width,
                "width_delta": target_width - source_width,
                "within_review_budget": True,
            }
        )

    specific = {
        (v4.TARGET_FILE, index): pair for index, pair in v4.GROUP.items()
    }
    specific.update(
        {(TARGET_FILE, index): pair for index, pair in GROUP.items()}
    )
    base.SPECIFIC_PATCHES = specific
    base.OUTPUT_STEM = "Battle_C117_android0137_v5"
    base.REPORT_NAME = "battle_c117_android0137_v5_report.json"
    base.REVIEW_GROUP = (
        "cumulative v4 + /Dat/Battle/Message/@Ja/0137_ja.bmd "
        "records 0-40 android/bioroid system voice"
    )
    base.main()

    # This post-build sidecar is intentionally separate from the cryptographic
    # report so the core report remains exactly what the safety builder emitted.
    sidecar = {
        "group_file": TARGET_FILE,
        "group_record_count": len(GROUP),
        "translation_method": "manual Japanese-to-Korean; no machine translation",
        "tone": "terse impersonal machine-status report",
        "screen_width_checks": width_checks,
    }
    (ROOT / "korean_build_v5" / "battle_android0137_v5_review.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
