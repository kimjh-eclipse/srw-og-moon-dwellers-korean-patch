#!/usr/bin/env python3
"""ISO 의 EBOOT.BIN 등 PS3_GAME 파일에서 아카이브 QUESTION 팝업 일본어를 찾는다.

Logic·Common·General2d 전 엔트리에 없었으므로 실행 파일 쪽을 본다.
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ISO = Path(r"C:\Emul\Switch\패치유틸.xdeltaUI\Super Robot Taisen OG - The Moon Dwellers (Japan).iso")
SECTOR = 2048
NEEDLES = ("再生を中止", "よろしいですか", "中止します", "アーカイブ")


def read_sectors(handle, lba: int, count: int) -> bytes:
    handle.seek(lba * SECTOR)
    return handle.read(SECTOR * count)


def walk(handle, lba: int, length: int, path: str, out: list):
    data = read_sectors(handle, lba, (length + SECTOR - 1) // SECTOR)
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
        full = f"{path}/{label}"
        if flags & 0x02:
            walk(handle, ext_lba, ext_len, full, out)
        else:
            out.append((full, ext_lba, ext_len))


def main() -> None:
    with ISO.open("rb") as handle:
        pvd = read_sectors(handle, 16, 1)
        root = pvd[156:190]
        root_lba = struct.unpack("<I", root[2:6])[0]
        root_len = struct.unpack("<I", root[10:14])[0]
        files: list[tuple[str, int, int]] = []
        walk(handle, root_lba, root_len, "", files)
        print(f"ISO 파일 {len(files)}개")
        interesting = [f for f in files
                       if f[0].upper().endswith((".BIN", ".SELF", ".SPRX", ".SFO", ".XML"))
                       and "PSARC" not in f[0].upper()]
        for name, lba, size in interesting:
            handle.seek(lba * SECTOR)
            data = handle.read(size)
            hits = {n: data.count(n.encode("utf-8")) for n in NEEDLES}
            mark = " ".join(f"{k}={v}" for k, v in hits.items() if v)
            print(f"  {name:60} {size:>12,}  {mark or '-'}")
            if hits.get("再生を中止") or hits.get("よろしいですか"):
                for needle in ("再生を中止", "よろしいですか"):
                    raw = needle.encode("utf-8")
                    at = data.find(raw)
                    while at >= 0:
                        start = data.rfind(b"\0", 0, at) + 1
                        end = data.find(b"\0", at)
                        field = data[start:end]
                        print(f"    0x{at:X} field=0x{start:X} len={len(field)} text={field.decode('utf-8', 'replace')[:80]}")
                        at = data.find(raw, at + 1)


if __name__ == "__main__":
    main()
