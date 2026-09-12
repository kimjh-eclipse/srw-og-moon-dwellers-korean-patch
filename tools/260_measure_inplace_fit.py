#!/usr/bin/env python3
"""소매판 배치를 그대로 두고 현재 한국어 문장을 제자리로 넣을 수 있는지 잰다.

참조 테이블을 건드리지 않으려면 문자열이 한 칸도 움직이면 안 된다.
따라서 각 슬롯의 원문 바이트 예산(널 포함) 안에 한국어가 들어가야 한다.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader
from bmd_rebuild import BmdFile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
RETAIL = ROOT / "original_backups" / "Battle.psarc.sdat.orig"
KOREAN = BUILD / "Battle_issue6_ko_20260909.psarc.sdat"
REPORT = BUILD / "battle_inplace_fit_20260912.json"


def main() -> None:
    with RETAIL.open("rb") as r, KOREAN.open("rb") as k:
        R, K = PSARC(SDATReader(r, 0)), PSARC(SDATReader(k, 0))
        names = R.manifest()
        targets = [(i + 1, n) for i, n in enumerate(names)
                   if n.startswith("/Dat/Battle/Message/") and n.endswith(".bmd")]
        total = fits = over = 0
        overflow = []
        for entry, name in targets:
            retail = BmdFile(R.read_entry(entry))
            korean_texts = BmdFile(K.read_entry(entry), pool_start=retail.pool_start).texts()
            if len(korean_texts) != len(retail.records):
                print(f"  ★ e{entry} {name}: 문자열 수 {len(retail.records)} vs {len(korean_texts)}")
                continue
            for index, (_off, span, jp) in enumerate(retail.records):
                text = korean_texts[index]
                need = len(text.encode("utf-8")) + 1
                total += 1
                if need <= span:
                    fits += 1
                else:
                    over += 1
                    overflow.append({"entry": entry, "file": name, "index": index,
                                     "span": span, "need": need, "over": need - span,
                                     "jp": jp[:60], "ko": text[:60]})
        print(f"문자열 {total:,}개")
        print(f"  제자리에 들어감 {fits:,}개 ({fits / total:.2%})")
        print(f"  예산 초과 {over:,}개")
        if overflow:
            worst = sorted(overflow, key=lambda row: -row["over"])
            print("\n가장 많이 넘는 것")
            for row in worst[:12]:
                print(f"  e{row['entry']} idx={row['index']} 예산 {row['span']}B, 필요 {row['need']}B (+{row['over']})")
                print(f"    원문 {row['jp']}")
            sizes = {}
            for row in overflow:
                sizes[row["over"]] = sizes.get(row["over"], 0) + 1
            print("\n초과 바이트 분포:", dict(sorted(sizes.items())[:10]))
        REPORT.write_text(json.dumps({"total": total, "fits": fits, "over": over,
                                      "overflow": overflow[:2000]}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"\n기록: {REPORT.name}")


if __name__ == "__main__":
    main()
