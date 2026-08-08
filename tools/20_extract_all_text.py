#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전 PSARC의 모든 텍스트 컨테이너(.dat FIXH/DOFS + .bmd 배틀메시지) 통합 추출.
정확한 파서(DatFile/BmdFile) 사용. 산출: extract2/{master.jsonl, unique_jp.jsonl, batches/}."""
import sys, io, os, json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
from sdat import SDATReader
from psarc import PSARC
from dat_rebuild import DatFile
from bmd_rebuild import BmdFile

HDD=r'C:/Emul/PS3/rpcs3-v0.0.27-14986-db7f84f9_win64/dev_hdd0/game/BLJS10335/USRDIR/PSARC'
SDATS={'LOGIC':'Logic.psarc.sdat','COMMON':'Common.psarc.sdat.orig','BATTLE':'Battle.psarc.sdat',
       'GENERAL2D':'General2d.psarc.sdat','GENERAL3D':'General3d.psarc.sdat'}
OUT='extract2'; os.makedirs(OUT+'/batches', exist_ok=True)

def open_psarc(sdat_name):
    path=os.path.join(HDD, sdat_name)
    if not os.path.exists(path):
        path=os.path.join(HDD, sdat_name.replace('.orig',''))
    return PSARC(SDATReader(open(path,'rb'),0))

master=open(os.path.join(OUT,'master.jsonl'),'w',encoding='utf-8')
unique={}; total=0
for name,sdat in SDATS.items():
    try: p=open_psarc(sdat)
    except Exception as e: print(f'[{name}] 열기 실패 {e}'); continue
    names=p.manifest()
    cand=[(i,n) for i,n in enumerate(names) if n.lower().endswith(('.dat','.bmd'))]
    print(f'[{name}] 텍스트후보 {len(cand)}개 처리...', flush=True)
    cnt=0
    for k,(i,nm) in enumerate(cand):
        if k%1000==0 and k: print(f'   {name} {k}/{len(cand)} (누적 {total:,})',flush=True)
        try: data=p.read_entry(i+1)
        except Exception: continue
        typ=None; texts=None
        try: texts=DatFile(data).texts(); typ='dat'
        except Exception:
            if nm.lower().endswith('.bmd'):
                try: texts=BmdFile(data).texts(); typ='bmd'
                except Exception: pass
        if not texts: continue
        for idx,t in enumerate(texts):
            master.write(json.dumps({'psarc':name,'file':nm,'type':typ,'idx':idx,'jp':t},ensure_ascii=False)+'\n')
            unique.setdefault(t,total); total+=1; cnt+=1
    print(f'[{name}] 문자열 {cnt:,}개')
master.close()
uni=list(unique.keys())
with open(os.path.join(OUT,'unique_jp.jsonl'),'w',encoding='utf-8') as f:
    for u in uni: f.write(json.dumps({'jp':u},ensure_ascii=False)+'\n')
# 배치(400줄)
PER=400
for b in range((len(uni)+PER-1)//PER):
    with open(os.path.join(OUT,'batches',f'batch_{b+1:04d}.tsv'),'w',encoding='utf-8') as f:
        for j,u in enumerate(uni[b*PER:(b+1)*PER]):
            f.write(f'{b*PER+j}\t'+u.replace('\\','\\\\').replace('\n','\\n').replace('\t','\\t')+'\n')
print(f'\n=== 총 {total:,}개 / 고유 {len(uni):,}개, 배치 {(len(uni)+PER-1)//PER}개 → {OUT}/ ===')
