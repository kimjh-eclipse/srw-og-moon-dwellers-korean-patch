#!/usr/bin/env python3
"""2026-08-24 제보 반영 패치.

General2d windowdataMain.wtd (패킹 문자열 풀)
  - 반격 설정 키가이드 '전체 마' -> '모두 마크'
  - SELECT-TYPE 라벨 3개와 설명문 7개 교정
  - 각 필드의 선행 제어 바이트와 전체 필드 폭을 그대로 유지한다

Logic ls010.bin
  - 이종족 언어 대사 4건을 한글 발음 표기로
  - '전 물리 법칙이 통불가 / 전 운동과 일이' 오역 교정

Logic + Battle
  - 기체명 '엑스엑스바인' -> '이그젝스바인' (16곳, 1바이트 축소)

보류: ProgStrData.dat 의 '적극적'(슬롯 14B)·'효율적'(14B) 은 제안 문구가
자리를 넘어 현행 유지. 같은 파일의 '균형 있게'·'신중히' 도 화면과 별개
경로여서 이번에는 건드리지 않는다.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
ORIGINALS = ROOT / "original_backups"

SOURCE_GENERAL = BUILD / "General2d_hayuhau_followups_ko_20260823.psarc.sdat"
SOURCE_LOGIC = BUILD / "Logic_hayuhau_followups_ko_20260823.psarc.sdat"
SOURCE_BATTLE = BUILD / "Battle_hayuhau_followups_ko_20260823.psarc.sdat"
OUTPUT_GENERAL = BUILD / "General2d_reports_ko_20260824.psarc.sdat"
OUTPUT_LOGIC = BUILD / "Logic_reports_ko_20260824.psarc.sdat"
OUTPUT_BATTLE = BUILD / "Battle_reports_ko_20260824.psarc.sdat"
REPORT = BUILD / "reports_20260824_report.json"

WTD_MAIN = 3751
LS010 = 333
FW = "　"   # 전각 공백


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_162_reports", "162_patch_hayuhau_followups_20260823.py")
BASE = PREV.BASE
proxy = PREV.proxy
encodings = PREV.encodings
shrink_in_record = PREV.shrink_in_record


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def restore_retail_time(path: Path, retail_name: str) -> None:
    stat = (ORIGINALS / retail_name).stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


REVERSE = PREV.REVERSE


def decode_proxy(raw):
    try:
        return "".join(REVERSE.get(c, c) for c in raw.decode("utf-8"))
    except UnicodeDecodeError:
        return None


def iter_chunks(data):
    """NUL 로 구분된 조각의 시작 위치, 바이트, 필드 폭(조각+패딩)."""
    pos = 0
    for chunk in data.split(b"\0"):
        if chunk:
            end = pos + len(chunk)
            pad = 0
            while end + pad < len(data) and data[end + pad] == 0:
                pad += 1
            yield pos, chunk, len(chunk) + pad
        pos += len(chunk) + 1


def replace_field(data, old_text, new_text, label, expect=None):
    """조각을 역매핑해 일치하는 필드를 폭을 유지하며 교체한다.

    WTD 는 레코드 앞 4바이트가 span 이라 NUL 로 쪼개면 span 마지막 바이트가
    문자열 앞에 붙어 보인다. 그 1바이트 접두를 자동으로 인식해 보존한다.
    """
    changes = []
    body = proxy(new_text) if isinstance(new_text, str) else new_text
    for pos, chunk, width in list(iter_chunks(bytes(data))):
        decoded = decode_proxy(chunk)
        if decoded is None:
            continue
        if decoded == old_text:
            prefix = b""
        elif len(decoded) == len(old_text) + 1 and decoded[1:] == old_text:
            prefix = chunk[:1]
        else:
            continue
        new = prefix + body
        if len(new) + 1 > width:
            raise AssertionError(
                f"{label}: 필드 {width}B 에 {len(new)+1}B 가 들어가지 않음")
        data[pos:pos + width] = new + b"\0" * (width - len(new))
        changes.append({"label": label, "offset": pos, "field": width,
                        "prefix": prefix.hex(), "before_bytes": len(chunk),
                        "after_bytes": len(new)})
    if expect is not None and len(changes) != expect:
        raise AssertionError(f"{label}: {expect}건 기대, {len(changes)}건 교체")
    if not changes:
        raise AssertionError(f"{label}: 대상을 찾지 못함 ({old_text!r})")
    return changes


def replace_inside(data, needle_text, new_text, label, expect=None):
    """레코드 안의 부분 문자열만 바꾼다. 필드 폭 안에서 길이 변화를 허용한다.

    저장된 프록시 코드가 출력 코드와 다를 수 있으므로 변형 전수로 탐색한다.
    """
    changes = []
    new_bytes = proxy(new_text)
    candidates = sorted(encodings(needle_text), key=len, reverse=True)
    for pos, chunk, width in list(iter_chunks(bytes(data))):
        for old_bytes in candidates:
            if old_bytes not in chunk:
                continue
            replaced = chunk.replace(old_bytes, new_bytes)
            if len(replaced) + 1 > width:
                raise AssertionError(
                    f"{label}: 필드 {width}B 에 {len(replaced)+1}B 가 들어가지 않음")
            data[pos:pos + width] = replaced + b"\0" * (width - len(replaced))
            changes.append({"label": label, "offset": pos, "field": width,
                            "before_bytes": len(chunk),
                            "after_bytes": len(replaced)})
            break
    if expect is not None and len(changes) != expect:
        raise AssertionError(f"{label}: {expect}건 기대, {len(changes)}건")
    if not changes:
        raise AssertionError(f"{label}: 대상을 찾지 못함 ({needle_text!r})")
    return changes


def wide_proxy(word: str) -> bytes:
    """모든 글자를 3바이트 프록시 코드로 인코딩한다(길이 보존용)."""
    out = []
    for ch in word:
        picks = [c for c in sorted(PREV.VARIANTS.get(ch, set()))
                 if len(c.encode("utf-8")) == 3]
        if not picks:
            raise AssertionError(f"3바이트 변형 없음: {ch}")
        out.append(picks[0])
    return "".join(out).encode("utf-8")


def open_plain(source: Path, tag: str):
    plain = BUILD / f"_reports_{tag}_source.psarc"
    with source.open("rb") as stream, plain.open("wb") as target:
        logical_size, _ = decrypt_stream(stream, 0, target)
    return plain, logical_size


def finish(source: Path, output: Path, plain: Path, modified: dict,
           logical_size: int, retail: str, fixed_spans: bool,
           recompress_all: bool = False) -> dict:
    out_plain = BUILD / (plain.stem + "_out.psarc")
    if fixed_spans:
        pack = rebuild_fixed_entry_spans(plain, modified, out_plain,
                                         recompress_all=recompress_all)
    else:
        pack = rebuild_fixed_blocks(plain, modified, out_plain)
    if out_plain.stat().st_size != logical_size:
        raise AssertionError(f"{output.name}: 논리 크기 변화")
    encode(str(out_plain), source.read_bytes()[:0x100], str(output))
    BASE.pad_file(output, source.stat().st_size)
    with output.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, expected in modified.items():
            if archive.read_entry(entry) != expected:
                raise AssertionError(f"{output.name}: entry {entry} 재읽기 불일치")
    restore_retail_time(output, retail)
    for temporary in (plain, out_plain):
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            pass
    return {"pack": pack, "sha256": digest(output)}


# ── windowdataMain.wtd 교체 목록 ────────────────────────────────────────────
# (선행 제어 바이트, 현재 문구, 새 문구, 설명)
# 접두가 있는 항목을 먼저 처리해야 접두 없는 항목과 충돌하지 않는다.
WTD_JOBS = [
    ("전체 마", "모두 마크", "키가이드 전체 마 -> 모두 마크"),
    # SELECT-TYPE 항목: 앞머리 기호를 빼고 어미를 다른 항목과 맞춘다
    ("- 적극적", "적극적으로", "라벨 적극적으로"),
    ("- 효율적", "효율적으로", "라벨 효율적으로"),
    # 트윈 배치 안내문: 원본의 ○버튼 아이콘 자리(전각공백 2칸)가 빠져
    # 아이콘이 「이동」을 덮었다. 원본 구조를 그대로 복원한다.
    ("<> 이동할 곳을 선택해 주세요",
     "＜이동 지점을 선택하세요（　　：놓는다）＞", "트윈 배치 안내문"),
    ("균형 잡힌", "밸런스 좋게", "라벨 균형 잡힌"),
    ("조심해", "신중하게", "라벨 조심해"),
    ("EN 탄약을 절약해", "EN・탄약을 절약", "라벨 EN 탄약 절약"),
    # 매뉴얼: 1행 + 2행 레코드가 따로 있다
    ("자율적으로 반격하는 것이 아니라",
     "자동 반격하지 않고 플레이어가", "설명 매뉴얼 1행"),
    ("플레이어는 세밀하게 반격 설정합니다.",
     "세밀하게 반격을 설정합니다.", "설명 매뉴얼 2행"),
    # 적극적: 1행 + 공용 2행("회피・방어합니다.")
    ("이 모든 것들은", "파괴될 가능성이 있을 때만", "설명 적극적 1행"),
    ("균형 잡힌 적대적인 공격", "밸런스 좋게 반격합니다", "설명 균형"),
    ("극심한 힘과 피해를 방지하기 위해",
     "최대한 대미지를 받지 않도록 반격합니다", "설명 신중"),
    ("EN와 탄약을 절약하면서",
     "EN과 탄약을 절약하며 밸런스 좋게 반격", "설명 EN 절약"),
    # 효율적: 1행 + 공용 2행
    ("적을 격추할 수 있을 때",
     "격추 가능하고 상대 레벨이 낮으면", "설명 효율 1행"),
    # 적극적/효율적 공용 2행 (레코드 2개, 둘 다 교체)
    ("피하고 방어합니다.", "회피・방어합니다.", "설명 적극/효율 2행"),
    ("피고, 방어, 반격은 없습니다.",
     "회피・방어하고 반격하지 않습니다", "설명 반격 금지"),
]

# ── ls010.bin 교체 목록 ────────────────────────────────────────────────────
LS010_JOBS = [
    ("「イー・ゾー・アウ・アー……@" + FW + "ロール・ドーグ……」",
     "「이・조・아우・아……@" + FW + "롤・도우그……」", "이종족 1"),
    ("「イー・ドノ・バメン・ミーパス……@" + FW + "ワーヒー・アーズ……」",
     "「이・도노・바멘・미파스……@" + FW + "와히・아즈……」", "이종족 2"),
    ("「! フィーオ……ガグリー……」", "「! 피오……가글리……」", "이종족 3"),
    ("「フィーオ……」", "「피오……」", "이종족 4"),
]

DIALOGUE_FIX = (
    "모든 물리 법칙이 통하지 않고",   # '전 물리 법칙이 통불가'
    "모든 운동이나 현상이",           # '전 운동과 일이'
)

UNIT_NAME = ("엑스엑스바인", "이그젝스바인")
TEXT_SUFFIX = (".dat", ".bin", ".bmd")
# UnitData.dat 는 압축 여유가 0 이라 전체 블록 재압축으로 자리를 확보한다.


def fix_middle_dots(data: bytearray, label: str) -> list[dict]:
    """U+00B7 은 게임 폰트에 글리프가 없어 공백으로 나온다.

    원본이 쓰는 U+30FB 로 바꾼다. 1바이트 늘어나므로 필드 폭이 모자란
    레코드는 건드리지 않고 목록에 남긴다.
    """
    BAD, GOOD = "·", "・"
    changes: list[dict] = []
    skipped = 0
    for pos, chunk, width in list(iter_chunks(bytes(data))):
        decoded = decode_proxy(chunk)
        if decoded is None or BAD not in decoded:
            continue
        new = chunk.replace(BAD.encode("utf-8"), GOOD.encode("utf-8"))
        if len(new) + 1 > width:
            skipped += 1
            continue
        data[pos:pos + width] = new + b"\0" * (width - len(new))
        changes.append({
            "label": f"{label} 가운뎃점",
            "offset": pos,
            "text": decoded.replace(BAD, GOOD),
            "before_bytes": len(chunk),
            "after_bytes": len(new),
        })
    if skipped:
        changes.append({"label": f"{label} 가운뎃점 자리부족", "skipped": skipped})
    return changes


def build_general() -> dict:
    plain, logical_size = open_plain(SOURCE_GENERAL, "general")
    archive = PSARC(str(plain))
    try:
        if archive.manifest()[WTD_MAIN - 1] != \
                "/Dat/Window/WindowToolData/windowdataMain.wtd":
            raise AssertionError("windowdataMain 식별 변화")
        data = bytearray(archive.read_entry(WTD_MAIN))
        changes = []
        for old_text, new_text, label in WTD_JOBS:
            changes.extend(replace_field(data, old_text, new_text, label))
        # 가운뎃점 교체로 1바이트가 넘치는 레코드는 미리 문구를 줄여 자리를 만든다
        changes.extend(replace_inside(
            data, "특수 스킬을 소지한 기체", "특수 스킬을 가진 기체",
            "검색 문구 축약", expect=1))
        changes.extend(fix_middle_dots(data, "windowdataMain"))
        result = finish(SOURCE_GENERAL, OUTPUT_GENERAL, plain,
                        {WTD_MAIN: bytes(data)}, logical_size,
                        "General2d.psarc.sdat.orig", fixed_spans=False)
        result["changes"] = changes
        return result
    finally:
        archive.f.close()


def patch_unit_name(archive: PSARC, counts: dict) -> dict[int, bytes]:
    """엑스엑스바인 -> 이그젝스바인 (동일 18바이트, 구조 무변경)."""
    modified: dict[int, bytes] = {}
    manifest = archive.manifest()
    target = wide_proxy(UNIT_NAME[1])       # 18B, 원문과 동일 길이
    for entry in range(1, archive.n):
        name = manifest[entry - 1] if entry - 1 < len(manifest) else ""
        if not name.lower().endswith(TEXT_SUFFIX):
            continue
        data = bytearray(archive.read_entry(entry))
        touched = False
        for old in encodings(UNIT_NAME[0]):
            if len(old) != len(target) or old not in data:
                continue
            hits = 0
            cursor = 0
            while True:
                pos = data.find(old, cursor)
                if pos < 0:
                    break
                data[pos:pos + len(target)] = target
                hits += 1
                cursor = pos + len(target)
            if hits:
                counts["엑스엑스바인->이그젝스바인"] += hits
                touched = True
        if touched:
            modified[entry] = bytes(data)
    return modified


def build_logic() -> dict:
    plain, logical_size = open_plain(SOURCE_LOGIC, "logic")
    archive = PSARC(str(plain))
    try:
        if archive.manifest()[LS010 - 1] != "/Dat/logic/talk/ls010.bin":
            raise AssertionError("ls010 식별 변화")
        counts: dict[str, int] = defaultdict(int)
        modified = patch_unit_name(archive, counts)

        talk = bytearray(modified.get(LS010, archive.read_entry(LS010)))
        slots = []
        for old_text, new_text, label in LS010_JOBS:
            slots.extend(replace_field(talk, old_text, new_text, label))
        # 오역 두 곳 (같은 레코드 안, 동일 길이 아님 -> 필드 폭 유지 교체)
        for before, after in (
            ("전 물리 법칙이 통불가", DIALOGUE_FIX[0]),
            ("전 운동과 일이", DIALOGUE_FIX[1]),
        ):
            slots.extend(replace_inside(talk, before, after, f"오역 {before}", expect=1))
        modified[LS010] = bytes(talk)

        result = finish(SOURCE_LOGIC, OUTPUT_LOGIC, plain, modified,
                        logical_size, "Logic.psarc.sdat.orig", fixed_spans=True,
                        recompress_all=True)
        result.update({"counts": dict(counts), "slots": slots,
                       "entries": sorted(modified)})
        return result
    finally:
        archive.f.close()


def build_battle() -> dict:
    plain, logical_size = open_plain(SOURCE_BATTLE, "battle")
    archive = PSARC(str(plain))
    try:
        counts: dict[str, int] = defaultdict(int)
        modified = patch_unit_name(archive, counts)
        result = finish(SOURCE_BATTLE, OUTPUT_BATTLE, plain, modified,
                        logical_size, "Battle.psarc.sdat.orig", fixed_spans=True)
        result.update({"counts": dict(counts), "entries": sorted(modified)})
        return result
    finally:
        archive.f.close()


def main() -> None:
    report = {
        "general2d": build_general(),
        "logic": build_logic(),
        "battle": build_battle(),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
