#!/usr/bin/env python3
"""ISO 를 읽기 전용으로 열어 패치 대상 6개 슬롯의 내용 해시를 확인한다.

멀티 extent(Battle)도 순서대로 이어서 해시한다. ISO 는 절대 쓰지 않는다.
사용: python 243_check_iso_slots.py "<iso 경로>"
"""
from __future__ import annotations

import hashlib
import io
import struct
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SECTOR = 2048
TARGETS = (
    ("PS3_GAME/PARAM.SFO", "0A876ACFABB16CEAA017EDD51A700079678AA8E61C0B7AEFE0B59CB19B59FF22",
     "B7ABDFE7FED52FB9EEEDDE02FBD33475A449C20B4EE6099E59BC025E1F32DE54"),
    ("PS3_GAME/ICON0.PNG", "9B2E67DC606CEF3CD269E13DDA425445820A65F034DE4B3BC000435EA0B9B136",
     "0B038E45343B203DE00D1323247FD5AFFFF3AB61AF35A8206010EA5601948A00"),
    ("PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT", "99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB",
     "52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373"),
    ("PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT", "04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667",
     "6BCB01A3D66FE668ECA2BF5167D9552DBD1D6F6DB1B0A24083FD40DA2D14AD47"),
    ("PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT", "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
     "8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C"),
    ("PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT", "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
     "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E"),
)


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


def main() -> None:
    iso = Path(sys.argv[1])
    print(f"ISO: {iso.name}  {iso.stat().st_size:,}B")
    with iso.open("rb") as handle:
        handle.seek(16 * SECTOR)
        pvd = handle.read(SECTOR)
        root = pvd[156:190]
        files: dict[str, list[tuple[int, int]]] = {}
        walk(handle, struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0], "", files)
        verdicts = []
        for path, retail_hash, korean_hash in TARGETS:
            extents = files.get(path)
            if not extents:
                print(f"  {path}: ★ 없음")
                verdicts.append("없음")
                continue
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
            value = digest.hexdigest().upper()
            state = "일본판 원본" if value == retail_hash else ("한국어판(v20260910)" if value == korean_hash else "알 수 없음")
            verdicts.append(state)
            print(f"  {path}")
            print(f"    extent {len(extents)}개, {total:,}B  {value[:16]}  → {state}")
        print("\n판정:", "전부 일본판 원본" if set(verdicts) == {"일본판 원본"} else f"혼재 {verdicts}")


if __name__ == "__main__":
    main()
