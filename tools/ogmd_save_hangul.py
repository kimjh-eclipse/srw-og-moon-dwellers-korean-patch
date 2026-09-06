#!/usr/bin/env python3
"""세이브 목록 한글화: PARAM.SFO 의 SUB_TITLE·DETAIL 에 든 대체 코드(프록시)를 실제 한글 UTF-8 로 되돌린다.

배경
  한글 패치는 게임 폰트가 한글을 그릴 수 있게 한글 음절을 한자·이(Yi) 영역 코드에 대체 인코딩한다.
  게임은 저장 시 시나리오 제목·루트·톱 에이스 등 게임 폰트용 문자열을 그대로 PARAM.SFO 에 복사하므로,
  시스템 폰트로 그리는 세이브 목록(XMB/세이브 데이터 유틸리티, 게임 내 목록)에서는 그 부분이 한자처럼 깨져 보인다.
  이 도구는 SFO 문자열만 실제 한글로 바꾼다. 게임 본체 세이브(.SAV)는 건드리지 않는다.

주의
  - 저장할 때마다 게임이 다시 대체 코드로 쓰므로, 새 세이브가 생기면 다시 실행해야 한다.
  - 백업은 세이브 폴더 밖(savedata 상위)에 만든다. 세이브 폴더 안에 파일을 추가하면 게임의 파일 목록과 어긋난다.

사용
  python ogmd_save_hangul.py <RPCS3 루트 | dev_hdd0 | savedata 폴더> [--apply]
  기본은 미리보기(dry-run). --apply 를 붙이면 실제로 쓴다.
"""
from __future__ import annotations

import argparse
import csv
import io
import shutil
import struct
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
MAP = ROOT / "korean_build_v3" / "save_proxy_reverse_map.tsv"
TARGET_KEYS = ("SUB_TITLE", "DETAIL")
PREFIX = "BLJS10335_OMI-"


def load_reverse_map(path: Path = MAP) -> dict[str, str]:
    table: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            table[chr(int(row["proxy_cp"][2:], 16))] = row["hangul"]
    return table


def decode(text: str, table: dict[str, str]) -> str:
    return "".join(table.get(ch, ch) for ch in text)


def parse_sfo(blob: bytes) -> list[dict]:
    magic, version, key_off, data_off, count = struct.unpack_from("<4sIIII", blob, 0)
    if magic != b"\0PSF":
        raise ValueError("PARAM.SFO 아님")
    entries = []
    for i in range(count):
        k_off, fmt, length, maximum, d_off = struct.unpack_from("<HHIII", blob, 0x14 + 16 * i)
        key_end = blob.index(b"\0", key_off + k_off)
        entries.append({
            "key": blob[key_off + k_off:key_end].decode("utf-8"),
            "fmt": fmt, "len": length, "max": maximum,
            "data": blob[data_off + d_off:data_off + d_off + maximum],
        })
    return entries


def build_sfo(entries: list[dict]) -> bytes:
    # 키 표: NUL 종결, 4바이트 정렬. 데이터 표: 각 엔트리 max 크기(원본과 동일하게 4바이트 정렬 유지).
    keys = b""
    key_offsets = []
    for e in entries:
        key_offsets.append(len(keys))
        keys += e["key"].encode("utf-8") + b"\0"
    while len(keys) % 4:
        keys += b"\0"
    data = b""
    data_offsets = []
    for e in entries:
        data_offsets.append(len(data))
        chunk = e["data"][:e["max"]].ljust(e["max"], b"\0")
        data += chunk
    header_size = 0x14 + 16 * len(entries)
    key_off = header_size
    data_off = key_off + len(keys)
    out = bytearray(struct.pack("<4sIIII", b"\0PSF", 0x101, key_off, data_off, len(entries)))
    for e, ko, do in zip(entries, key_offsets, data_offsets):
        out += struct.pack("<HHIII", ko, e["fmt"], e["len"], e["max"], do)
    out += keys + data
    return bytes(out)


def find_savedata_dirs(anchor: Path) -> list[Path]:
    anchor = anchor.resolve()
    if anchor.name.lower() == "savedata":
        return [anchor]
    hits = sorted(anchor.glob("dev_hdd0/home/*/savedata")) or sorted(anchor.glob("home/*/savedata"))
    return hits


def convert_one(sfo_path: Path, table: dict[str, str]) -> tuple[bytes, bytes, list[tuple[str, str, str]]] | None:
    blob = sfo_path.read_bytes()
    entries = parse_sfo(blob)
    if build_sfo(entries) != blob:
        # 원본 배치를 정확히 재현하지 못하면 손대지 않는다.
        raise ValueError("SFO 재조립 불일치 — 이 파일은 건너뜀")
    changes = []
    for e in entries:
        if e["key"] not in TARGET_KEYS or e["fmt"] != 0x0204:
            continue
        before = e["data"][:e["len"]].rstrip(b"\0").decode("utf-8")
        after = decode(before, table)
        if after == before:
            continue
        encoded = after.encode("utf-8") + b"\0"
        if len(encoded) > e["max"]:
            raise ValueError(f"{e['key']}: {len(encoded)}B 가 최대 {e['max']}B 를 넘음")
        e["data"] = encoded.ljust(e["max"], b"\0")
        e["len"] = len(encoded)
        changes.append((e["key"], before, after))
    if not changes:
        return None
    return blob, build_sfo(entries), changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("anchor", help="RPCS3 루트, dev_hdd0, 또는 savedata 폴더")
    parser.add_argument("--apply", action="store_true", help="실제로 기록 (기본은 미리보기)")
    args = parser.parse_args()
    table = load_reverse_map()
    dirs = find_savedata_dirs(Path(args.anchor))
    if not dirs:
        raise SystemExit("savedata 폴더를 찾지 못함")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    total = 0
    for sd in dirs:
        backup_root = sd.parent / f"ogmd_sfo_backup_{stamp}"
        for save in sorted(p for p in sd.iterdir() if p.is_dir() and p.name.startswith(PREFIX)):
            sfo = save / "PARAM.SFO"
            if not sfo.is_file():
                continue
            try:
                result = convert_one(sfo, table)
            except ValueError as exc:
                print(f"[건너뜀] {save.name}: {exc}")
                continue
            if result is None:
                print(f"[변경 없음] {save.name}")
                continue
            original, rebuilt, changes = result
            total += 1
            print(f"[{'적용' if args.apply else '미리보기'}] {save.name}")
            for key, before, after in changes:
                print(f"    {key}: {after.replace(chr(10), ' | ')}")
            if args.apply:
                dest = backup_root / save.name
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sfo, dest / "PARAM.SFO")
                stat = sfo.stat()
                sfo.write_bytes(rebuilt)
                import os
                os.utime(sfo, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        if args.apply and total:
            print(f"백업: {backup_root}")
    print(f"대상 {total}개 {'기록함' if args.apply else '(미리보기, 기록하지 않음. --apply 로 실행)'}")


if __name__ == "__main__":
    main()
