#!/usr/bin/env python3
"""소매판 Battle BMD와 최신 패치 BMD를 직접 대조해 issue #6 대상 좌표를 찾는다."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC
from sdat import SDATReader

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
RETAIL = ROOT / "original_backups" / "Battle.psarc.sdat.orig"
KOREAN = BUILD / "Battle_issue6_ko_20260909.psarc.sdat"
OUTPUT = ROOT / "issue6_battle_verify.jsonl"
TOKENS = (
    "ヘルルーガ", "グ＝ランドン", "フー＝ルー", "ゴモウドッカ",
    "ゴライクンル", "雷鳳", "ダイライオー", "イング",
)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


decode_proxy = load("ogmd_issue6_prev", "163_patch_reports_20260824.py").decode_proxy


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    found = []
    with RETAIL.open("rb") as rs, KOREAN.open("rb") as ks:
        retail, korean = PSARC(SDATReader(rs, 0)), PSARC(SDATReader(ks, 0))
        manifest = retail.manifest()
        assert manifest == korean.manifest()
        targets = [(entry, name) for entry, name in enumerate(manifest, 1)
                   if name.lower().endswith(".bmd")]
        for serial, (entry, name) in enumerate(targets, 1):
            try:
                rbmd = BmdFile(retail.read_entry(entry))
                kbmd = BmdFile(korean.read_entry(entry))
            except Exception:
                continue
            rtexts, ktexts = rbmd.texts(), kbmd.texts()
            if len(rtexts) != len(ktexts):
                raise AssertionError(f"레코드 수 불일치: {name}")
            for idx, jp in enumerate(rtexts):
                hits = [token for token in TOKENS if token in jp]
                if not hits:
                    continue
                raw = ktexts[idx].encode("utf-8")
                ko = decode_proxy(raw)
                if ko is None:
                    ko = ktexts[idx]
                found.append({"entry": entry, "file": name, "idx": idx,
                              "tokens": hits, "jp": jp, "ko": ko})
            if serial % 100 == 0:
                print(f"{serial}/{len(targets)} BMD, 발견 {len(found)}", file=sys.stderr, flush=True)
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in found),
                      encoding="utf-8")
    print(f"완료: {len(found)}건 -> {OUTPUT}")


if __name__ == "__main__":
    main()
