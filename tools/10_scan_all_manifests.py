#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5개 PSARC.SDAT 매니페스트를 온더플라이로 스캔하여 텍스트 담긴 파일 위치 파악."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import Counter
from sdat import SDATReader
from psarc import PSARC

ISO=r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
LBA={"COMMON":735289,"GENERAL2D":436663,"GENERAL3D":None,"BATTLE":None,"LOGIC":982276}
# GENERAL3D/BATTLE LBA는 01_iso_list에서 재확인 필요 → ISO 재파싱으로 자동 획득
import struct
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
    base=full.split('/')[-1]
    if base.endswith('_PSARC.SDAT'):
        sdats[base.replace('_PSARC.SDAT','')]=l

print("발견된 SDAT:", {k:v for k,v in sdats.items()})
fin=open(ISO,'rb')
for name,lba in sdats.items():
    try:
        r=SDATReader(fin, lba*SECTOR)
        p=PSARC(r)
        names=p.manifest()
        exts=Counter(os.path.splitext(n)[1].lower() for n in names)
        # 텍스트 유력 파일(.dat, .bin 중 FIXH 등) 추정: 확장자 통계
        print(f"\n===== {name}_PSARC : 엔트리 {p.n}개 =====")
        print("  확장자:", dict(exts.most_common(12)))
        # 상위 디렉토리 분포
        dirs=Counter('/'.join(n.split('/')[:3]) for n in names)
        print("  주요 경로:", dict(dirs.most_common(8)))
    except Exception as e:
        print(f"\n[{name}] 실패: {e}")
