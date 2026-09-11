#!/usr/bin/env python3
"""원본(일본판) ISO 에서 PARAM.SFO·ICON0.PNG 를 뽑고, 한글 대상 파일과 크기·해시를 대조한다.

범위 팩은 ISO 배치를 바꾸지 않으므로 대상 파일이 원본 슬롯 크기를 넘으면 안 된다.
"""
from __future__ import annotations

import hashlib
import io
import struct
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
ISO = ROOT.parent / "Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
OUT = ROOT / "original_backups"
SECTOR = 2048
WANT = {
    "/PS3_GAME/PARAM.SFO": OUT / "PARAM.SFO.orig",
    "/PS3_GAME/ICON0.PNG": OUT / "ICON0.PNG.orig",
    "/PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT": None,
    "/PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT": None,
    "/PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT": None,
    "/PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT": None,
}
TARGETS = {
    "/PS3_GAME/PARAM.SFO": ROOT / "korean_build_v3/game_titles_20260910/BLJS10335_disc/PS3_GAME/PARAM.SFO",
    "/PS3_GAME/ICON0.PNG": ROOT / "korean_build_v3/game_titles_20260910/ICON0.PNG",
    "/PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT": ROOT / "korean_build_v3/archive_all_20260910/Common.psarc.sdat",
    "/PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT": ROOT / "korean_build_v3/archive_trial_20260910/General2d.psarc.sdat",
    "/PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT": ROOT / "korean_build_v3/archive_report_20260910/Logic.psarc.sdat",
    "/PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT": ROOT / "korean_build_v3/Battle_issue6_ko_20260909.psarc.sdat",
}
RETAIL_PSARC = {
    "/PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT": OUT / "Common.psarc.sdat.orig",
    "/PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT": OUT / "General2d.psarc.sdat.orig",
    "/PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT": OUT / "Logic.psarc.sdat.orig",
    "/PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT": OUT / "Battle.psarc.sdat.orig",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def walk(handle, lba: int, length: int, prefix: str, out: dict):
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
        full = f"{prefix}/{label}"
        if flags & 0x02:
            walk(handle, ext_lba, ext_len, full, out)
        else:
            out[full] = (ext_lba, ext_len)


def main() -> None:
    with ISO.open("rb") as handle:
        handle.seek(16 * SECTOR)
        pvd = handle.read(SECTOR)
        root = pvd[156:190]
        files: dict[str, tuple[int, int]] = {}
        walk(handle, struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0], "", files)
        print(f"원본 ISO 파일 {len(files)}개")
        for iso_path, dest in WANT.items():
            if iso_path not in files:
                print(f"  [없음] {iso_path}")
                continue
            lba, size = files[iso_path]
            target = TARGETS[iso_path]
            line = f"  {iso_path}\n    ISO 슬롯 offset={lba * SECTOR:,} size={size:,}"
            if dest is not None:
                handle.seek(lba * SECTOR)
                data = handle.read(size)
                dest.write_bytes(data)
                line += f"\n    원본 추출 -> {dest.name} sha={sha_bytes(data)[:16]}"
            else:
                retail = RETAIL_PSARC[iso_path]
                same = retail.stat().st_size == size
                line += f"\n    소매판 백업 {retail.name} 크기일치={same} sha={sha_file(retail)[:16]}"
            if target.is_file():
                tsize = target.stat().st_size
                line += f"\n    대상 {target.name} size={tsize:,} ({'맞음' if tsize == size else '★크기 불일치'}) sha={sha_file(target)[:16]}"
            else:
                line += f"\n    ★대상 파일 없음: {target}"
            print(line)


if __name__ == "__main__":
    main()
