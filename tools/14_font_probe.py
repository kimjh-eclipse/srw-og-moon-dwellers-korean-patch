#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMMON PSARC의 폰트 파일 식별/헤더 덤프."""
import sys, io, os, struct
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다
sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sdat import SDATReader
from psarc import PSARC

ISO=rconfig.require('ISO')
SECTOR=2048

def all_files():
    def walk(f,lba,dlen,path,out,depth=0):
        f.seek(lba*SECTOR); data=f.read(((dlen+SECTOR-1)//SECTOR)*SECTOR); pos=0; ents=[]
        while pos<dlen:
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
        f.seek(16*SECTOR); pvd=f.read(SECTOR); root=pvd[156:190]
        rl=struct.unpack('<I',root[2:6])[0]; rn=struct.unpack('<I',root[10:14])[0]
        out=[]; walk(f,rl,rn,'',out); return out

files=all_files()
sdats={}
for full,d,l,ln in files:
    b=full.split('/')[-1]
    if b.endswith('_PSARC.SDAT'): sdats[b.replace('_PSARC.SDAT','')]=l

fin=open(ISO,'rb')
p=PSARC(SDATReader(fin, sdats['COMMON']*SECTOR))
names=p.manifest()
os.makedirs('font_dump', exist_ok=True)
fonts=[(i+1,n) for i,n in enumerate(names) if '/font' in n.lower() or n.lower().endswith(('.nftr','.gxt','.fnt','.bcfnt'))]
print(f"COMMON 총 {len(names)}개 엔트리 중 폰트 후보 {len(fonts)}개:\n")
for i,n in fonts:
    d=p.read_entry(i)
    magic=d[:4]; magic_ascii=''.join(chr(b) if 32<=b<127 else '.' for b in d[:16])
    print(f"  [{i}] {n}")
    print(f"       크기={len(d):,}B  magic={magic!r}  head16={magic_ascii!r}")
    print(f"       hex0-32: {d[:32].hex()}")
    open(f"font_dump/{os.path.basename(n)}","wb").write(d)
print("\n원본 폰트 → font_dump/ 에 저장 완료")
