#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISO에서 누락된 PSARC 파일을 추출한다. ISO9660 다중 익스텐트를 이어붙여 처리.

usage: python iso_extract_missing.py <출력폴더> <ISO내이름> [<ISO내이름> ...]
  예: python iso_extract_missing.py D:/out PSARCLIST.BIN SOUND.PSARC MOVIE.PSARC
"""
import os
import struct
import sys

ISO = r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
SECTOR = 2048

# ISO9660 디렉터리 레코드 플래그
FLAG_DIR = 0x02
FLAG_MULTI_EXTENT = 0x80


def read_sector(f, lba, count=1):
    f.seek(lba * SECTOR)
    return f.read(SECTOR * count)


def list_dir(f, extent_lba, data_len):
    """디렉터리 레코드를 ISO 상의 순서대로 반환. 다중 익스텐트 판별용으로 flags 포함."""
    data = read_sector(f, extent_lba, (data_len + SECTOR - 1) // SECTOR)
    pos = 0
    entries = []
    while pos < data_len:
        rec_len = data[pos]
        if rec_len == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            if pos >= data_len:
                break
            continue
        ext_lba = struct.unpack('<I', data[pos + 2:pos + 6])[0]
        ext_len = struct.unpack('<I', data[pos + 10:pos + 14])[0]
        flags = data[pos + 25]
        name_len = data[pos + 32]
        name = data[pos + 33:pos + 33 + name_len]
        pos += rec_len
        if name_len == 1 and name in (b'\x00', b'\x01'):
            continue
        nm = name.split(b';')[0].decode('latin-1', 'replace')
        entries.append({
            'name': nm,
            'is_dir': bool(flags & FLAG_DIR),
            'lba': ext_lba,
            'len': ext_len,
            'multi': bool(flags & FLAG_MULTI_EXTENT),
        })
    return entries


def find_dir(f, path_parts):
    """루트에서 path_parts 를 따라 내려가 디렉터리의 (lba, len) 반환."""
    pvd = read_sector(f, 16)
    root = pvd[156:190]
    lba = struct.unpack('<I', root[2:6])[0]
    ln = struct.unpack('<I', root[10:14])[0]
    for part in path_parts:
        for e in list_dir(f, lba, ln):
            if e['is_dir'] and e['name'].upper() == part.upper():
                lba, ln = e['lba'], e['len']
                break
        else:
            raise SystemExit(f"디렉터리를 찾을 수 없음: {part}")
    return lba, ln


def collect_extents(entries, name):
    """같은 이름의 연속 레코드를 순서대로 모아 익스텐트 목록을 만든다.

    ISO9660 다중 익스텐트는 마지막을 제외한 모든 레코드에 0x80 플래그가 서 있고,
    같은 이름의 레코드가 파일 순서대로 연속 배치된다.
    """
    up = name.upper()
    exts = [e for e in entries if not e['is_dir'] and e['name'].upper() == up]
    if not exts:
        return None
    # 마지막 레코드는 multi 플래그가 없어야 정상
    if len(exts) > 1 and exts[-1]['multi']:
        print(f"  [경고] {name}: 마지막 익스텐트에도 multi 플래그가 있음. 목록이 잘렸을 수 있음.")
    return exts


def extract(f, exts, out_path):
    total = sum(e['len'] for e in exts)
    print(f"  익스텐트 {len(exts)}개, 합계 {total:,} bytes -> {out_path}")
    written = 0
    with open(out_path, 'wb') as out:
        for e in exts:
            f.seek(e['lba'] * SECTOR)
            remain = e['len']
            while remain > 0:
                chunk = f.read(min(1 << 22, remain))
                if not chunk:
                    raise SystemExit(f"  ISO 읽기 실패 (남은 {remain:,})")
                out.write(chunk)
                remain -= len(chunk)
                written += len(chunk)
            print(f"    LBA {e['lba']} len {e['len']:,} 누적 {written:,}")
    got = os.path.getsize(out_path)
    if got != total:
        raise SystemExit(f"  크기 불일치: 기대 {total:,} 실제 {got:,}")
    print(f"  완료 {got:,} bytes")
    return got


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    outdir = sys.argv[1]
    names = sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)

    with open(ISO, 'rb') as f:
        lba, ln = find_dir(f, ['PS3_GAME', 'USRDIR', 'PSARC'])
        entries = list_dir(f, lba, ln)
        print(f"PSARC 디렉터리 레코드 {len(entries)}개")
        for name in names:
            print(f"[*] {name}")
            exts = collect_extents(entries, name)
            if exts is None:
                print(f"  ISO에 없음: {name}")
                continue
            extract(f, exts, os.path.join(outdir, name))


if __name__ == '__main__':
    main()
