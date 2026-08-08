#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SDAT 첫 블록만 복호화하여 PSAR 매직 나오는 파라미터 조합을 실증 확정."""
import struct
from Crypto.Cipher import AES

ISO = r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
SECTOR = 2048
SDAT_KEY = bytes.fromhex("0D655EF8E674A98AB8505CFA7D012933")

def find_lba(target):
    def walk(f, lba, dlen, path, out, depth=0):
        f.seek(lba*SECTOR); data=f.read(((dlen+SECTOR-1)//SECTOR)*SECTOR); pos=0; ents=[]
        while pos < dlen:
            rl=data[pos]
            if rl==0:
                pos=((pos//SECTOR)+1)*SECTOR
                if pos>=dlen: break
                continue
            el=struct.unpack('<I',data[pos+2:pos+6])[0]; ln=struct.unpack('<I',data[pos+10:pos+14])[0]
            fl=data[pos+25]; nl=data[pos+32]; nm=data[pos+33:pos+33+nl]; pos+=rl
            if nl==1 and nm in (b'\x00',b'\x01'): continue
            n=nm.split(b';')[0].decode('latin-1','replace'); ents.append((n,bool(fl&2),el,ln))
        for n,d,l,ln in ents:
            full=path+'/'+n; out.append((full,d,l,ln))
            if d and depth<8: walk(f,l,ln,full,out,depth+1)
    with open(ISO,'rb') as f:
        pvd=f.seek(16*SECTOR) or f.read(SECTOR);
        f.seek(16*SECTOR); pvd=f.read(SECTOR); root=pvd[156:190]
        rl=struct.unpack('<I',root[2:6])[0]; rn=struct.unpack('<I',root[10:14])[0]
        out=[]; walk(f,rl,rn,'',out)
        for full,d,l,ln in out:
            if full.split('/')[-1]==target: return l,ln
    return None,None

def aes_ecb_enc(key, data):
    return AES.new(key, AES.MODE_ECB).encrypt(data)
def aes_cbc_dec(key, iv, data):
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)

target="LOGIC_PSARC.SDAT"
lba,size=find_lba(target)
print(f"{target}: LBA={lba} size={size:,}")
with open(ISO,'rb') as f:
    base=lba*SECTOR
    f.seek(base); hdr=f.read(0x100)
    magic=hdr[0:4]; version=struct.unpack('>I',hdr[4:8])[0]
    digest=hdr[0x40:0x50]; title_hash=hdr[0x50:0x60]; dev_hash=hdr[0x60:0x70]
    flags=struct.unpack('>I',hdr[0x80:0x84])[0]; block_size=struct.unpack('>I',hdr[0x84:0x88])[0]
    file_size=struct.unpack('>Q',hdr[0x88:0x90])[0]
    print(f"version={version} flags=0x{flags:08X} block_size={block_size} file_size={file_size:,}")
    print(f"digest   ={digest.hex()}")
    print(f"dev_hash ={dev_hash.hex()}")

    crypt_key = bytes(a^b for a,b in zip(dev_hash, SDAT_KEY))
    # block 0 key
    bk = dev_hash[:12] + struct.pack('>I', 0)
    per_block_key = aes_ecb_enc(crypt_key, bk)

    # 데이터 위치 후보: A) 메타 뒤(0x120)  B) 메타 없음(0x100)
    for label, data_off in [("data@0x120(meta선행)", base+0x120), ("data@0x100(meta없음)", base+0x100)]:
        f.seek(data_off); blk=f.read(16)  # 첫 16바이트만
        for ivlabel, iv in [("IV=digest", digest), ("IV=zeros", b"\x00"*16)]:
            dec = aes_cbc_dec(per_block_key, iv, blk)
            tag = "  <<< PSAR!!!" if dec[:4]==b"PSAR" else ""
            print(f"  [{label} / {ivlabel}] 첫16B: {dec.hex(' ')}{tag}")
