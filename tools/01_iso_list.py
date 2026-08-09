#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PS3 ISO9660 directory tree lister (read-only, no full extraction)."""
import struct, sys
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다

ISO = rconfig.require('ISO')
SECTOR = 2048

def read_sector(f, lba, count=1):
    f.seek(lba * SECTOR)
    return f.read(SECTOR * count)

def parse_dir(f, extent_lba, data_len, path, out, depth=0):
    data = read_sector(f, extent_lba, (data_len + SECTOR - 1) // SECTOR)
    pos = 0
    entries = []
    while pos < data_len:
        rec_len = data[pos]
        if rec_len == 0:
            # move to next sector boundary
            pos = ((pos // SECTOR) + 1) * SECTOR
            if pos >= data_len:
                break
            continue
        ext_lba = struct.unpack('<I', data[pos+2:pos+6])[0]
        ext_len = struct.unpack('<I', data[pos+10:pos+14])[0]
        flags = data[pos+25]
        name_len = data[pos+32]
        name = data[pos+33:pos+33+name_len]
        pos += rec_len
        if name_len == 1 and name in (b'\x00', b'\x01'):
            continue
        nm = name.split(b';')[0].decode('latin-1', 'replace')
        is_dir = bool(flags & 0x02)
        entries.append((nm, is_dir, ext_lba, ext_len))
    for nm, is_dir, lba, length in entries:
        full = path + '/' + nm
        out.append((full, is_dir, lba, length))
        if is_dir and depth < 8:
            parse_dir(f, lba, length, full, out, depth+1)

def main():
    with open(ISO, 'rb') as f:
        pvd = read_sector(f, 16)
        assert pvd[1:6] == b'CD001', "not ISO9660"
        root_rec = pvd[156:156+34]
        root_lba = struct.unpack('<I', root_rec[2:6])[0]
        root_len = struct.unpack('<I', root_rec[10:14])[0]
        out = []
        parse_dir(f, root_lba, root_len, '', out)
    # print tree
    files = [e for e in out if not e[1]]
    dirs  = [e for e in out if e[1]]
    print(f"총 디렉터리 {len(dirs)}개, 파일 {len(files)}개\n")
    for full, is_dir, lba, length in out:
        kind = 'DIR ' if is_dir else '    '
        sz = '' if is_dir else f"{length:>12,} B"
        print(f"{kind}{full}  {sz}")

if __name__ == '__main__':
    main()
