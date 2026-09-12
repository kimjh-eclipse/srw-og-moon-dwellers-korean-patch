#!/usr/bin/env python3
"""전투 대사 참조를 전수 대조한다. 화면에서 볼 수 없는 대사까지 덮는다.

원리: 소매판에서 line 레코드 i 의 포인터가 「풀의 몇 번째 문자열」을 가리켰는지 세고,
수정본에서도 같은 번호를 가리키는지 본다. 번호가 같으면 그 대사 자리에 그 대사의 번역이
나온다는 뜻이다. 값이 유효한지만 보는 검사보다 강하다.

함께 보는 것
  - 포인터가 문자열 시작이 아닌 곳을 가리키는가
  - sentinel(FFFFFFFF)이 원본과 같은 자리에 있는가
  - 번역 문자열 집합·순서가 게시본과 같은가
  - 아직 일본어로 남은 대사 수가 게시본과 같은가(회귀 없음)
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
FIXED = ROOT / "korean_build_v3" / "battle_refs_20260912" / "Battle.psarc.sdat"
PUBLISHED = ROOT / "korean_build_v3" / "Battle_issue6_ko_20260909.psarc.sdat"
RETAIL = ROOT / "original_backups" / "Battle.psarc.sdat.orig"


def layout(data: bytes) -> tuple[int, list[int]]:
    groups, events, lines = struct.unpack_from(">HHH", data, 2)
    line_start = 8 + groups * 12 + events * 20
    return line_start + lines * 20, [line_start + i * 20 + 16 for i in range(lines)]


def pool_index(data: bytes, pool: int) -> dict[int, int]:
    """문자열 시작 상대오프셋 → 몇 번째 문자열인가."""
    table: dict[int, int] = {}
    position = pool
    order = 0
    while position < len(data):
        end = data.find(b"\0", position)
        if end < 0:
            break
        raw = data[position:end]
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            break
        if raw:
            table[position - pool] = order
            order += 1
        position = end + 1
    return table


def texts(data: bytes, pool: int) -> list[str]:
    out = []
    position = pool
    while position < len(data):
        end = data.find(b"\0", position)
        if end < 0:
            break
        raw = data[position:end]
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            break
        if raw:
            out.append(decoded)
        position = end + 1
    return out


def main() -> None:
    total_refs = sentinels = 0
    index_ok = index_bad = 0
    invalid = 0
    sentinel_moved = 0
    string_total = 0
    text_diff = 0
    japanese_fixed = japanese_published = 0
    bad_samples: list[str] = []

    with FIXED.open("rb") as f, PUBLISHED.open("rb") as p, RETAIL.open("rb") as r:
        F, P, R = PSARC(SDATReader(f, 0)), PSARC(SDATReader(p, 0)), PSARC(SDATReader(r, 0))
        names = R.manifest()
        if not (F.n == P.n == R.n):
            raise SystemExit("엔트리 수 불일치")
        for entry in range(1, R.n):
            name = names[entry - 1]
            if not (name.startswith("/Dat/Battle/Message/") and name.endswith(".bmd")):
                continue
            retail = R.read_entry(entry)
            fixed = F.read_entry(entry)
            published = P.read_entry(entry)
            pool, pointers = layout(retail)
            if len(fixed) != len(retail):
                raise SystemExit(f"{name}: 크기 변화")

            retail_index = pool_index(retail, pool)
            fixed_index = pool_index(fixed, pool)
            retail_texts = texts(retail, pool)
            fixed_texts = texts(fixed, pool)
            if len(fixed_texts) != len(retail_texts):
                raise SystemExit(f"{name}: 문자열 수 {len(retail_texts)} → {len(fixed_texts)}")
            string_total += len(fixed_texts)
            japanese_fixed += sum(1 for a, b in zip(retail_texts, fixed_texts) if a == b)

            published_texts = texts(published, layout(published)[0])
            if published_texts == fixed_texts:
                japanese_published += sum(1 for a, b in zip(retail_texts, published_texts) if a == b)
            else:
                text_diff += 1

            for slot in pointers:
                retail_value = struct.unpack_from(">I", retail, slot)[0]
                fixed_value = struct.unpack_from(">I", fixed, slot)[0]
                total_refs += 1
                if retail_value == 0xFFFFFFFF:
                    sentinels += 1
                    if fixed_value != 0xFFFFFFFF:
                        sentinel_moved += 1
                    continue
                if fixed_value == 0xFFFFFFFF:
                    sentinel_moved += 1
                    continue
                want = retail_index.get(retail_value)
                got = fixed_index.get(fixed_value)
                if got is None:
                    invalid += 1
                if want is not None and want == got:
                    index_ok += 1
                else:
                    index_bad += 1
                    if len(bad_samples) < 10:
                        bad_samples.append(
                            f"{name} slot 0x{slot:X}: 소매 idx {want} → 수정본 idx {got}")

    print(f"참조 {total_refs:,}개 (sentinel {sentinels:,}개 제외 시 {total_refs - sentinels:,}개)")
    print(f"  소매판과 같은 번호의 대사를 가리킴 : {index_ok:,}개")
    print(f"  번호가 어긋남                     : {index_bad:,}개")
    print(f"  문자열 시작이 아닌 곳을 가리킴    : {invalid:,}개")
    print(f"  sentinel 위치가 바뀜              : {sentinel_moved:,}개")
    print(f"문자열 {string_total:,}개, 게시본과 본문이 다른 BMD {text_diff}개")
    print(f"원문 그대로 남은(미번역) 문자열: 수정본 {japanese_fixed:,}개 / 게시본 {japanese_published:,}개")
    for line in bad_samples:
        print("  ★", line)
    ok = index_bad == 0 and invalid == 0 and sentinel_moved == 0 and text_diff == 0
    print("\n판정:", "전수 통과" if ok else "★ 문제 있음")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
