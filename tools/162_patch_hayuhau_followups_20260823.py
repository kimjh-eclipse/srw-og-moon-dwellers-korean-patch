#!/usr/bin/env python3
"""하유하우님 2026-08-23 제보 후속 패치 (안전 범위: 길이 내 교체만).

포함:
  Logic   - 슌파티아→심파티아, 바스카→버스커, 공순→복종 (동일 길이)
            슈운→슌 (축소, 꼬리 이동 + NUL 패딩)
            ls008 「탈래？」→「설교야？」 (원문 슬롯 19B 안)
            ls009 「왜 저를 아십니까?」→「어떻게 저를 알고있죠?」 (슬롯 55B 안)
            ls009 「뭐?」→「네?」 (해당 엔트리 1건만)
            PilotDictionaryData 잔존 일본어 <シュンパ|ティア> → <심파티|아>
  Battle  - 슌파티아→심파티아, 바스카→버스커 (동일 길이)
  General2d - windowdataFreeBattle.wtd 不参加→미참가, 援防→원방

제외(별도 검증 필요):
  - LDBI 가변 길이 재빌더 (잘린 대사 1,866건 복구)
  - windowdataFreeBattle.wtd 나머지 일본어 460건
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import itertools
import json
import os
import struct
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

SOURCE_LOGIC = BUILD / "Logic_character_names_ko_20260822.psarc.sdat"
SOURCE_BATTLE = BUILD / "Battle_character_names_ko_20260822.psarc.sdat"
SOURCE_GENERAL = BUILD / "General2d_name_followups_ko_20260822.psarc.sdat"
OUTPUT_LOGIC = BUILD / "Logic_hayuhau_followups_ko_20260823.psarc.sdat"
OUTPUT_BATTLE = BUILD / "Battle_hayuhau_followups_ko_20260823.psarc.sdat"
OUTPUT_GENERAL = BUILD / "General2d_hayuhau_followups_ko_20260823.psarc.sdat"
REPORT = BUILD / "hayuhau_followups_20260823_report.json"

FREEBATTLE_ENTRY = 3749
FREEBATTLE_PATH = "/Dat/Window/WindowToolData/windowdataFreeBattle.wtd"
LS008_ENTRY, LS009_ENTRY, PILOTDICT_ENTRY = 331, 332, 20


def load_base():
    path = ROOT / "147_patch_screenshot_followups.py"
    spec = importlib.util.spec_from_file_location("ogmd_147_hayuhau", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BASE = load_base()
CUM = BASE.CUMULATIVE


def proxy(text: str) -> bytes:
    """출력용 인코딩. 이주된 글리프 코드를 사용한다."""
    return CUM.proxy(text)


def load_variants() -> dict[str, set[str]]:
    """탐색용: 같은 한글이 저장될 수 있는 모든 프록시 코드."""
    variants: dict[str, set[str]] = defaultdict(set)
    for name in (
        "korean_font_map.tsv", "compact_aliases.tsv", "general2d_compact_aliases.tsv",
        "logic_suffix_aliases.tsv", "plain_label_aliases.tsv",
        "final_review_aliases.tsv", "raio_aliases.tsv",
    ):
        path = BUILD / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                hangul, code = row["hangul"], row["proxy"]
                if len(hangul) == 1 and len(code) == 1:
                    variants[hangul].add(code)
    # 이주된 글리프의 새 코드와 검색 제목 별칭까지 포함
    for char, move in CUM.RELOCATED_PROXY_CPS.items():
        variants[char].add(chr(move["new_cp"]))
    for char, cp in CUM.SHORT_ALIAS_CPS.items():
        variants[char].add(chr(cp))
        variants[char].add(chr(CUM.SHORT_ALIAS_NORMAL_CPS[char]))
    return variants


VARIANTS = load_variants()


def encodings(word: str) -> set[bytes]:
    pools = [sorted(VARIANTS[ch]) if VARIANTS[ch] else [ch] for ch in word]
    return {
        "".join(combo).encode("utf-8") for combo in itertools.product(*pools)
    }


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def restore_retail_time(path: Path, retail_name: str) -> None:
    stat = (ORIGINALS / retail_name).stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def replace_in_place(data: bytearray, old: bytes, new: bytes) -> int:
    """같은 길이 교체. 구조를 전혀 건드리지 않는다."""
    if len(old) != len(new):
        raise AssertionError("replace_in_place requires equal length")
    hits = 0
    cursor = 0
    while True:
        position = data.find(old, cursor)
        if position < 0:
            return hits
        data[position:position + len(new)] = new
        hits += 1
        cursor = position + len(new)


def shrink_in_record(data: bytearray, old: bytes, new: bytes) -> int:
    """축소 교체. 레코드 꼬리를 왼쪽으로 당기고 끝에 NUL 을 채운다.

    레코드 시작 오프셋이 변하지 않으므로 오프셋 테이블·DOFS 는 그대로 유효하다.
    """
    delta = len(old) - len(new)
    if delta <= 0:
        raise AssertionError("shrink_in_record requires shorter replacement")
    hits = 0
    cursor = 0
    while True:
        position = data.find(old, cursor)
        if position < 0:
            return hits
        end = data.find(b"\0", position + len(old))
        if end < 0:
            raise AssertionError(f"unterminated record at {position}")
        tail = bytes(data[position + len(old):end])
        data[position:end] = new + tail + b"\0" * delta
        hits += 1
        cursor = position + len(new)


def replace_within_slot(data: bytearray, old: bytes, new: bytes, label: str) -> dict:
    """레코드 슬롯(내용+NUL 패딩) 안에서만 늘리거나 줄인다. 1건만 허용."""
    position = data.find(old)
    if position < 0 or data.find(old, position + 1) >= 0:
        raise AssertionError(f"{label}: expected exactly one occurrence")
    end = data.index(b"\0", position)
    pad = 0
    while data[end + pad] == 0:
        pad += 1
    slot = (end - position) + pad
    if len(new) + 1 > slot:
        raise AssertionError(f"{label}: needs {len(new)+1}B but slot is {slot}B")
    data[position:position + slot] = new + b"\0" * (slot - len(new))
    return {"label": label, "offset": position, "slot": slot,
            "before_bytes": end - position, "after_bytes": len(new)}


def build_reverse() -> dict[str, str]:
    """모든 프록시 코드 -> 한글 역매핑 (저장 코드가 여러 가지일 수 있음)."""
    reverse: dict[str, str] = {}
    for hangul, codes in VARIANTS.items():
        for code in codes:
            reverse[code] = hangul
    return reverse


REVERSE = build_reverse()


def decode_proxy(raw: bytes) -> str:
    return "".join(REVERSE.get(ch, ch) for ch in raw.decode("utf-8"))


def replace_record_by_anchor(data: bytearray, anchor: str, expected: str,
                             new_text: str, label: str) -> dict:
    """앵커로 레코드를 찾아 내용 전체를 교체한다.

    저장된 프록시 코드가 출력 코드와 다를 수 있으므로 앵커의 모든 변형을 시도하고,
    레코드 내용을 역매핑해 기대 문자열과 일치하는지 확인한 뒤에만 바꾼다.
    """
    positions: list[int] = []
    for candidate in encodings(anchor):
        cursor = 0
        while True:
            position = data.find(candidate, cursor)
            if position < 0:
                break
            positions.append(position)
            cursor = position + 1
    if len(set(positions)) != 1:
        raise AssertionError(f"{label}: anchor matched {len(set(positions))} places")
    hit = positions[0]
    start = data.rfind(b"\x00", 0, hit) + 1
    end = data.index(b"\x00", hit)
    actual = decode_proxy(bytes(data[start:end]))
    if actual != expected:
        raise AssertionError(f"{label}: record text is {actual!r}, expected {expected!r}")
    pad = 0
    while data[end + pad] == 0:
        pad += 1
    slot = (end - start) + pad
    replacement = proxy(new_text)
    if len(replacement) + 1 > slot:
        raise AssertionError(f"{label}: needs {len(replacement)+1}B but slot is {slot}B")
    data[start:start + slot] = replacement + b"\x00" * (slot - len(replacement))
    return {"label": label, "offset": start, "slot": slot,
            "before": actual, "after": new_text,
            "before_bytes": end - start, "after_bytes": len(replacement)}


def open_plain(source: Path, tag: str):
    plain = BUILD / f"_hayuhau_{tag}_source.psarc"
    with source.open("rb") as stream, plain.open("wb") as target:
        logical_size, _ = decrypt_stream(stream, 0, target)
    return plain, logical_size


def finish(source: Path, output: Path, plain: Path, modified: dict,
           logical_size: int, retail: str, fixed_spans: bool) -> dict:
    out_plain = BUILD / (plain.stem + "_output.psarc")
    rebuild = rebuild_fixed_entry_spans if fixed_spans else rebuild_fixed_blocks
    pack = rebuild(plain, modified, out_plain)
    if out_plain.stat().st_size != logical_size:
        raise AssertionError(f"{output.name}: logical size changed")
    encode(str(out_plain), source.read_bytes()[:0x100], str(output))
    BASE.pad_file(output, source.stat().st_size)
    with output.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, expected in modified.items():
            if archive.read_entry(entry) != expected:
                raise AssertionError(f"{output.name}: entry {entry} readback mismatch")
    restore_retail_time(output, retail)
    for temporary in (plain, out_plain):
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            pass
    return {"pack": pack, "sha256": digest(output)}


# 동일 길이 이름 교체 (전 엔트리)
EQUAL_NAMES = (("슌파티아", "심파티아"), ("바스카", "버스커"), ("공순", "복종"))
# 축소 이름 교체
SHRINK_NAMES = (("슈운", "슌"),)
TEXT_ENTRY_SUFFIX = (".dat", ".bin", ".bmd")


def patch_names(archive: PSARC, counts: dict) -> dict[int, bytes]:
    modified: dict[int, bytes] = {}
    manifest = archive.manifest()
    for entry in range(1, archive.n):
        name = manifest[entry - 1] if entry - 1 < len(manifest) else ""
        if not name.lower().endswith(TEXT_ENTRY_SUFFIX):
            continue
        raw = archive.read_entry(entry)
        touched = False
        data = bytearray(raw)
        for before, after in EQUAL_NAMES:
            target = proxy(after)
            for old in encodings(before):
                if old == target or len(old) != len(target) or old not in data:
                    continue
                hits = replace_in_place(data, old, target)
                if hits:
                    counts[f"{before}->{after}"] += hits
                    touched = True
        for before, after in SHRINK_NAMES:
            target = proxy(after)
            for old in encodings(before):
                if len(old) <= len(target) or old not in data:
                    continue
                hits = shrink_in_record(data, old, target)
                if hits:
                    counts[f"{before}->{after}"] += hits
                    touched = True
        if touched:
            modified[entry] = bytes(data)
    return modified


def build_logic() -> dict:
    plain, logical_size = open_plain(SOURCE_LOGIC, "logic")
    archive = PSARC(str(plain))
    try:
        manifest = archive.manifest()
        if manifest[PILOTDICT_ENTRY - 1] != "/Dat/FixedData/PilotDictionaryData.dat":
            raise AssertionError("PilotDictionaryData identity changed")
        if manifest[LS008_ENTRY - 1] != "/Dat/logic/talk/ls008.bin":
            raise AssertionError("ls008 identity changed")
        if manifest[LS009_ENTRY - 1] != "/Dat/logic/talk/ls009.bin":
            raise AssertionError("ls009 identity changed")

        counts: dict[str, int] = defaultdict(int)
        modified = patch_names(archive, counts)
        slots = []

        def edit(entry: int, changes) -> None:
            data = bytearray(modified.get(entry, archive.read_entry(entry)))
            for anchor, expected, new_text, label in changes:
                slots.append(
                    replace_record_by_anchor(data, anchor, expected, new_text, label)
                )
            modified[entry] = bytes(data)

        edit(LS008_ENTRY, [
            ("탈래", "「탈래？」", "「설교야？」",
             "ls008 諭す気 -> 설교야"),
        ])
        edit(LS009_ENTRY, [
            ("저를 아", "「왜 저를 아십니까?」",
             "「어떻게 저를 알고있죠?」",
             "ls009 왜 저를 아십니까 -> 어떻게 저를 알고있죠"),
            ("「뭐?」", "「뭐?」", "「네?」",
             "ls009 뭐 -> 네"),
        ])
        # 사전에 남은 일본어 <シュンパ|ティア> (줄바꿈으로 분할된 레코드)
        dict_data = bytearray(modified.get(PILOTDICT_ENTRY,
                                           archive.read_entry(PILOTDICT_ENTRY)))
        jp_a, jp_b = "シュンパ".encode("utf-8"), "ティア>".encode("utf-8")
        if dict_data.count(jp_a) != 1 or dict_data.count(jp_b) != 1:
            raise AssertionError("PilotDictionary Japanese remnant count changed")
        counts["<シュンパティア> -> <심파티아>"] = 1
        shrink_in_record(dict_data, jp_a, proxy("심파티"))
        shrink_in_record(dict_data, jp_b, proxy("아") + b">")
        modified[PILOTDICT_ENTRY] = bytes(dict_data)

        result = finish(SOURCE_LOGIC, OUTPUT_LOGIC, plain, modified, logical_size,
                        "Logic.psarc.sdat.orig", fixed_spans=True)
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
        modified = patch_names(archive, counts)
        result = finish(SOURCE_BATTLE, OUTPUT_BATTLE, plain, modified, logical_size,
                        "Battle.psarc.sdat.orig", fixed_spans=True)
        result.update({"counts": dict(counts), "entries": sorted(modified)})
        return result
    finally:
        archive.f.close()


def build_general() -> dict:
    plain, logical_size = open_plain(SOURCE_GENERAL, "general")
    archive = PSARC(str(plain))
    try:
        if archive.manifest()[FREEBATTLE_ENTRY - 1] != FREEBATTLE_PATH:
            raise AssertionError("FreeBattle WTD identity changed")
        data = bytearray(archive.read_entry(FREEBATTLE_ENTRY))
        counts: dict[str, int] = {}
        counts["不参加 -> 미참가"] = replace_in_place(
            data, "不参加".encode("utf-8"), proxy("미참가")
        )
        # 援防(6B) -> 원방(5B): span 안에서만 줄이고 NUL 로 채운다
        japanese = "援防".encode("utf-8")
        korean = proxy("원방")
        hits = 0
        cursor = 0
        while True:
            position = data.find(japanese, cursor)
            if position < 0:
                break
            record = position - 4
            span = struct.unpack_from(">I", data, record)[0]
            if not 2 <= span <= 1024 or data[position + span - 1] != 0:
                raise AssertionError(f"援防 record not span-prefixed at {record}")
            if len(korean) + 1 > span:
                raise AssertionError(f"援防 overflow at {record}")
            data[position:position + span] = korean + b"\0" * (span - len(korean))
            hits += 1
            cursor = position + span
        counts["援防 -> 원방"] = hits
        if counts["不参加 -> 미참가"] != 3 or hits != 2:
            raise AssertionError(f"FreeBattle unexpected counts: {counts}")
        result = finish(SOURCE_GENERAL, OUTPUT_GENERAL, plain,
                        {FREEBATTLE_ENTRY: bytes(data)}, logical_size,
                        "General2d.psarc.sdat.orig", fixed_spans=False)
        result.update({"counts": counts})
        return result
    finally:
        archive.f.close()


def main() -> None:
    report = {
        "logic": build_logic(),
        "battle": build_battle(),
        "general2d": build_general(),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
