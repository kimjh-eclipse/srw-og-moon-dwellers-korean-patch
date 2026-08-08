#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전 PSARC 텍스트 추출 → 재삽입용 master.jsonl + 번역용 unique 목록."""
import sys, io, os, json, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sdat import SDATReader
from psarc import PSARC
from textextract import extract

ISO=r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
OUTDIR="extract"; os.makedirs(OUTDIR, exist_ok=True)
SECTOR=2048
CAND_EXT={'.dat','.bin','.csv','.ebd','.tbd'}

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
master=open(os.path.join(OUTDIR,"master.jsonl"),"w",encoding="utf-8")
gid=0; per_psarc={}; unique={}   # text -> uid
uid_order=[]

def get_psarc(name, lba):
    local=f"{name}.psarc"
    if os.path.exists(local): return PSARC(local)      # LOGIC 등 이미 푼 것
    return PSARC(SDATReader(fin, lba*SECTOR))

PSARC_LIST=sys.argv[1].split(",") if len(sys.argv)>1 else ["LOGIC","COMMON","GENERAL2D","GENERAL3D"]
for name in PSARC_LIST:
    if name not in sdats: continue
    try:
        p=get_psarc(name, sdats[name])
    except Exception as e:
        print(f"[{name}] 열기 실패: {e}", flush=True); continue
    names=p.manifest(); cnt=0; strc=0
    cand=[(i,path) for i,path in enumerate(names,start=1)
          if os.path.splitext(path)[1].lower() in CAND_EXT]
    print(f"[{name}] 후보 파일 {len(cand)}개 처리 시작", flush=True)
    for k,(i,path) in enumerate(cand):
        if k % 50 == 0:
            print(f"  {name} {k}/{len(cand)} ... 누적 문자열 {strc:,}", flush=True)
        try: data=p.read_entry(i)
        except Exception: continue
        rows=extract(data)
        if not rows: continue
        cnt+=1
        for r in rows:
            gid+=1; strc+=1
            t=r['text']
            if t not in unique:
                unique[t]=len(uid_order); uid_order.append(t)
            master.write(json.dumps({
                'id':gid,'psarc':name,'file':path,'entry':i,
                'off':r['off'],'blen':r['blen'],'uid':unique[t],'text':t
            }, ensure_ascii=False)+"\n")
    per_psarc[name]=(cnt,strc)
    print(f"[{name}] 텍스트 파일 {cnt}개, 문자열 {strc:,}개")

master.close()
# 번역용 unique 목록 (uid \t 원문) + JSONL
with open(os.path.join(OUTDIR,"unique_jp.jsonl"),"w",encoding="utf-8") as u:
    for uid,t in enumerate(uid_order):
        u.write(json.dumps({'uid':uid,'jp':t}, ensure_ascii=False)+"\n")

total=sum(v[1] for v in per_psarc.values())
print(f"\n총 문자열 {total:,}개 (고유 {len(uid_order):,}개)")
print(f"산출: {OUTDIR}/master.jsonl (재삽입용), {OUTDIR}/unique_jp.jsonl (번역용)")
