#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISO에서 특정 파일의 LBA를 찾아 NPD(SDAT/EDAT) 헤더를 분석."""
import struct

ISO = r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
SECTOR = 2048
TARGETS = ["COMMON_PSARC.SDAT", "GENERAL2D_PSARC.SDAT", "LOGIC_PSARC.SDAT",
           "MOVIE.PSARC", "EBOOT.BIN"]

def read_sector(f, lba, count=1):
    f.seek(lba * SECTOR); return f.read(SECTOR * count)

def walk(f, lba, dlen, path, out, depth=0):
    data = read_sector(f, lba, (dlen + SECTOR - 1)//SECTOR); pos=0
    ents=[]
    while pos < dlen:
        rl = data[pos]
        if rl==0:
            pos=((pos//SECTOR)+1)*SECTOR
            if pos>=dlen: break
            continue
        el=struct.unpack('<I',data[pos+2:pos+6])[0]
        ln=struct.unpack('<I',data[pos+10:pos+14])[0]
        fl=data[pos+25]; nl=data[pos+32]; nm=data[pos+33:pos+33+nl]; pos+=rl
        if nl==1 and nm in (b'\x00',b'\x01'): continue
        n=nm.split(b';')[0].decode('latin-1','replace'); ents.append((n,bool(fl&2),el,ln))
    for n,d,l,ln in ents:
        full=path+'/'+n; out.append((full,d,l,ln))
        if d and depth<8: walk(f,l,ln,full,out,depth+1)

def npd_info(hdr):
    magic = hdr[0:4]
    if magic != b'NPD\x00':
        return f"NPD 매직 아님: {magic!r} (첫16B: {hdr[:16].hex()})"
    version = struct.unpack('>I', hdr[0x04:0x08])[0]
    license = struct.unpack('>I', hdr[0x08:0x0c])[0]
    app_type= struct.unpack('>I', hdr[0x0c:0x10])[0]
    cid = hdr[0x10:0x40].split(b'\x00')[0].decode('latin-1','replace')
    # EDAT flags at 0x80 (after NPD's 0x80-byte header, EDAT header follows)
    flags = struct.unpack('>I', hdr[0x80:0x84])[0]
    block = struct.unpack('>I', hdr[0x84:0x88])[0]
    fsize = struct.unpack('>Q', hdr[0x88:0x90])[0]
    SDAT_FLAG = 0x01000000
    lines=[]
    lines.append(f"  NPD version = {version}")
    lines.append(f"  license type= {license}  (0/1/2=EDAT klicensee필요, 3=free)")
    lines.append(f"  app type    = {app_type}")
    lines.append(f"  content ID  = {cid}")
    lines.append(f"  EDAT flags  = 0x{flags:08X}")
    lines.append(f"  block size  = {block:,}  data size = {fsize:,}")
    lines.append(f"  >> SDAT여부 (flags & 0x01000000): {'YES (SDAT, 고정키 복호화 가능)' if flags & SDAT_FLAG else 'NO (EDAT, klicensee 필요할 수 있음)'}")
    return "\n".join(lines)

with open(ISO,'rb') as f:
    pvd=read_sector(f,16); root=pvd[156:190]
    rl=struct.unpack('<I',root[2:6])[0]; rn=struct.unpack('<I',root[10:14])[0]
    out=[]; walk(f,rl,rn,'',out)
    idx={e[0].split('/')[-1]:e for e in out}
    for t in TARGETS:
        if t not in idx:
            print(f"[{t}] ISO에서 못 찾음"); continue
        full,isd,lba,ln = idx[t]
        f.seek(lba*SECTOR); hdr=f.read(256)
        print(f"\n===== {t}  (LBA={lba}, size={ln:,}) =====")
        print(f"  첫 16바이트: {hdr[:16].hex(' ')}")
        if t.endswith('.SDAT'):
            print(npd_info(hdr))
        elif t=='EBOOT.BIN':
            print(f"  매직: {hdr[:4]!r}  (SCE=암호화SELF / 7f454c46=평문ELF)")
        else:
            print(f"  매직: {hdr[:4]!r}  (PSAR=평문 PSARC)")
