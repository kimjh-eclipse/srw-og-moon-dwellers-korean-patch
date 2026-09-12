#!/usr/bin/env python3
"""ISO 안의 지정 슬롯을 같은 크기의 파일로 교체한다. 멀티 extent 대응.

기존 패치 ISO 를 최종 결과물로 갱신할 때 쓴다. 원본 보관용 ISO 는 대상으로 삼지 않는다.

  python 262_write_iso_slots.py "<iso>" BATTLE=<경로> [COMMON=<경로> ...] [--dry-run]

슬롯 이름은 SLOTS 의 키다. 크기가 1바이트라도 다르면 거부한다(ISO 레이아웃 이동 금지).
쓰기 전에 대상 슬롯의 현재 해시를 기록하고, 쓴 뒤 다시 읽어 대조한다.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SECTOR = 2048
SLOTS = {
    "PARAM.SFO": "PS3_GAME/PARAM.SFO",
    "ICON0.PNG": "PS3_GAME/ICON0.PNG",
    "COMMON": "PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT",
    "GENERAL2D": "PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT",
    "LOGIC": "PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT",
    "BATTLE": "PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT",
}
# 보관용 원본. 실수로 덮어쓰지 않도록 이름으로 거부한다.
PROTECTED = ("Super Robot Taisen OG - The Moon Dwellers (Japan).iso",)


def walk(handle, lba: int, length: int, prefix: str, out: dict) -> None:
    handle.seek(lba * SECTOR)
    data = handle.read(((length + SECTOR - 1) // SECTOR) * SECTOR)
    pos = 0
    while pos < length:
        rec = data[pos]
        if rec == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            continue
        ext_lba = struct.unpack("<I", data[pos + 2:pos + 6])[0]
        ext_len = struct.unpack("<I", data[pos + 10:pos + 14])[0]
        flags = data[pos + 25]
        name_len = data[pos + 32]
        name = data[pos + 33:pos + 33 + name_len]
        pos += rec
        if name in (b"\x00", b"\x01"):
            continue
        label = name.decode("ascii", "replace").split(";")[0]
        full = f"{prefix}/{label}".lstrip("/")
        if flags & 0x02:
            walk(handle, ext_lba, ext_len, full, out)
        else:
            out.setdefault(full, []).append((ext_lba, ext_len))


def slot_digest(handle, extents) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for lba, size in extents:
        handle.seek(lba * SECTOR)
        left = size
        while left:
            chunk = handle.read(min(8 * 1024 * 1024, left))
            if not chunk:
                raise IOError("짧은 읽기")
            digest.update(chunk)
            left -= len(chunk)
        total += size
    return digest.hexdigest().upper(), total


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    argv = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv
    if len(argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    iso = Path(argv[0])
    if iso.name in PROTECTED:
        raise SystemExit(f"거부: {iso.name} 은 보관용 원본이다. 기존 패치 ISO 를 대상으로 지정할 것.")
    assignments = {}
    for token in argv[1:]:
        key, _, value = token.partition("=")
        if key not in SLOTS:
            raise SystemExit(f"알 수 없는 슬롯 {key!r}. 가능: {', '.join(SLOTS)}")
        source = Path(value)
        if not source.is_file():
            raise SystemExit(f"입력 없음: {source}")
        assignments[key] = source

    print(f"대상 ISO: {iso}  {iso.stat().st_size:,}B")
    with iso.open("rb") as handle:
        handle.seek(16 * SECTOR)
        pvd = handle.read(SECTOR)
        root = pvd[156:190]
        files: dict[str, list[tuple[int, int]]] = {}
        walk(handle, struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0], "", files)
        plan = []
        for key, source in assignments.items():
            extents = files.get(SLOTS[key])
            if not extents:
                raise SystemExit(f"{key}: ISO 안에 {SLOTS[key]} 없음")
            before, total = slot_digest(handle, extents)
            want = file_digest(source)
            size = source.stat().st_size
            if size != total:
                raise SystemExit(f"{key}: 크기 불일치 ISO {total:,}B vs 입력 {size:,}B — 레이아웃을 움직일 수 없다")
            plan.append((key, source, extents, before, want, total))
            print(f"  {key}: extent {len(extents)}개 {total:,}B")
            print(f"    현재 {before[:16]} → 적용 {want[:16]}"
                  + ("  (이미 동일)" if before == want else ""))

    if dry_run:
        print("\n--dry-run: 쓰지 않음")
        return

    todo = [row for row in plan if row[3] != row[4]]
    if not todo:
        print("\n바꿀 슬롯 없음")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = iso.with_name(f"{iso.stem}_slots_{stamp}.txt")
    lines = [f"# {iso.name} 슬롯 교체 {stamp}"]
    with iso.open("r+b") as handle:
        for key, source, extents, before, want, total in todo:
            with source.open("rb") as data:
                for lba, size in extents:
                    handle.seek(lba * SECTOR)
                    left = size
                    while left:
                        chunk = data.read(min(8 * 1024 * 1024, left))
                        if len(chunk) != min(8 * 1024 * 1024, left):
                            raise IOError(f"{key}: 입력이 짧다")
                        handle.write(chunk)
                        left -= len(chunk)
                if data.read(1):
                    raise IOError(f"{key}: 입력이 남았다")
            handle.flush()
            lines.append(f"{key}\t{before}\t{want}\t{total}")
            print(f"  {key} 기록 완료")

    with iso.open("rb") as handle:
        for key, _source, extents, _before, want, _total in todo:
            after, _ = slot_digest(handle, extents)
            if after != want:
                raise SystemExit(f"{key}: 쓴 뒤 해시 불일치 {after}")
            print(f"  {key} 검증 OK {after[:16]}")
    record.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n기록: {record.name}")
    print("ISO 전체 해시는 따로 계산할 것(시간이 걸린다).")


if __name__ == "__main__":
    main()
