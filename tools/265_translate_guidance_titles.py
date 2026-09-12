#!/usr/bin/env python3
"""가이던스 15쪽의 제목 줄을 번역한다.

`/Dat/logic/Resource/summary/2og_GuidanceSummary.csb` (Logic entry 307) 은
지금까지 손대지 않은 파일이라 제목이 일본어 그대로다. 그 일본어가 한글 프록시
폰트로 그려지면서 「ＳＲ빵패호트흡」처럼 깨져 보였다.

제자리 교체만 쓴다(원문 바이트 예산 128~149B, 한글은 훨씬 짧다).
태그(<X=..><W=..><I=..> 등)와 좌표값은 건드리지 않는다.
오른쪽 안내는 「：戻る」가 두 글자이므로 폭이 늘지 않게 「：뒤로」로 맞춘다.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader, decrypt_stream

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_archive_ko_20260910.psarc.sdat"
OUTPUT = BUILD / "Logic_guidance_ko_20260912.psarc.sdat"
REPORT = BUILD / "guidance_titles_20260912_report.json"
ENTRY = 307

# 기존 번역에서 쓰던 용어를 따른다: 정신기 / 중간 저장 / 맵병기 / 일반공격
TITLES = {
    "１．「ＳＲポイント」について": "１．「ＳＲ 포인트」에 대해",
    "２．「精神コマンド」について": "２．「정신기」에 대해",
    "３．「途中セーブ」について": "３．「중간 저장」에 대해",
    "４．「アビリティ」について": "４．「어빌리티」에 대해",
    "５．「ツイン精神コマンド」について": "５．「트윈 정신기」에 대해",
    "６．「ツインユニット」について": "６．「트윈 유닛」에 대해",
    "７．「武器の種別」について": "７．「무기 종류」에 대해",
    "８．「気力」について": "８．「기력」에 대해",
    "９．「全体攻撃」について": "９．「전체공격」에 대해",
    "１０．「マップ兵器」について": "１０．「맵병기」에 대해",
    "１１．「通常攻撃」について": "１１．「일반공격」에 대해",
    "１２．「攻撃方法のまとめ」について": "１２．「공격 방법 정리」에 대해",
    "１４．「リトライ」について": "１４．「재시도」에 대해",
    "１５．「攻略Ｑ＆Ａ」について": "１５．「공략 Ｑ＆Ａ」에 대해",
}
# 13번은 제목 자리에 아이콘 태그가 들어간다. 태그는 그대로 두고 뒷부분만 옮긴다.
TITLE_WITH_ICON = ("１３．「<I=236>」について", "１３．「<I=236>」에 대해")
BACK = ("：戻る", "：뒤로")


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("p163_265", "163_patch_reports_20260824.py")
PROXY = load("p162_265", "162_patch_hayuhau_followups_20260823.py")
finish = PREV.finish


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def main() -> None:
    with SOURCE.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        data = bytearray(archive.read_entry(ENTRY))

    rows = []
    position = 0
    while position < len(data):
        end = data.find(b"\0", position)
        if end < 0:
            break
        raw = bytes(data[position:end])
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            position = end + 1
            continue
        if "について" in text and "<X=" in text:
            head, _, tail = text.partition("<X=")
            tail = "<X=" + tail
            if head == TITLE_WITH_ICON[0]:
                new_head = TITLE_WITH_ICON[1]
            elif head in TITLES:
                new_head = TITLES[head]
            else:
                raise AssertionError(f"번역표에 없는 제목: {head}")
            new_tail = tail.replace(*BACK)
            if new_tail == tail:
                raise AssertionError(f"「：戻る」를 찾지 못함: {head}")
            encoded = PROXY.proxy(new_head + new_tail)
            budget = end - position + 1
            if len(encoded) + 1 > budget:
                raise AssertionError(f"{head}: 예산 초과 {len(encoded) + 1} > {budget}")
            data[position:position + budget] = encoded + b"\0" * (budget - len(encoded))
            rows.append({"offset": position, "budget": budget, "used": len(encoded) + 1,
                         "jp": head, "ko": new_head})
        position = end + 1

    if len(rows) != 15:
        raise AssertionError(f"제목 15개를 기대했으나 {len(rows)}개")
    for row in rows:
        print(f"  0x{row['offset']:X} {row['used']:3d}/{row['budget']:3d}B  {row['jp']}  →  {row['ko']}")

    plain = BUILD / "_guidance_logic.psarc"
    try:
        with SOURCE.open("rb") as stream, plain.open("wb") as target:
            logical_size, _ = decrypt_stream(stream, 0, target)
        result = finish(SOURCE, OUTPUT, plain, {ENTRY: bytes(data)}, logical_size,
                        "Logic.psarc.sdat.orig", fixed_spans=True)
    finally:
        for temporary in (plain, BUILD / (plain.stem + "_out.psarc")):
            temporary.unlink(missing_ok=True)

    with SOURCE.open("rb") as a, OUTPUT.open("rb") as b:
        A, B = PSARC(SDATReader(a, 0)), PSARC(SDATReader(b, 0))
        changed = [e for e in range(1, A.n) if A.read_entry(e) != B.read_entry(e)]
        if changed != [ENTRY]:
            raise AssertionError(f"예상 밖 엔트리 변경: {changed}")
        if len(B.read_entry(ENTRY)) != len(data):
            raise AssertionError("엔트리 크기 변화")
    print(f"\n대조: entry {ENTRY} 하나만 변경, 크기 동일")

    REPORT.write_text(json.dumps({"entry": ENTRY, "titles": rows, **result},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"출력 {OUTPUT.name}  {digest(OUTPUT)}")


if __name__ == "__main__":
    main()
