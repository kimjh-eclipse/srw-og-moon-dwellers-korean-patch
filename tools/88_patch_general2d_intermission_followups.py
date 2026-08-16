#!/usr/bin/env python3
"""Patch reviewed intermission and warning UI labels in current General2d."""
from __future__ import annotations
import csv, hashlib, json, os, struct
from pathlib import Path
from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT=Path(__file__).resolve().parent; BUILD=ROOT/'korean_build_v3'
SOURCE=Path(r'C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC\General2d.psarc.sdat')
RETAIL=ROOT/'original_backups'/'General2d.psarc.sdat.orig'
OUTPUT=BUILD/'General2d_intermission_followups_20260814.psarc.sdat'
REPORT=BUILD/'general2d_intermission_followups_20260814_report.json'; ENTRY=3751

PATCHES=[
 (523296,'그리고, 그 이유는,','다음과 같은 이유로 사용할 수 없습니다'),
 (523708,'·알이 ','·탄수 부족'),(523752,'·알이 ','·탄수 부족'),
 (524432,'공기가 ','·기력 부족'),(524476,'공기가 ','·기력 부족'),
 (524772,'지형적 적응에 의한 ','·지형적응에 따른 제한'),(524828,'지형적 적응에 의한 ','·지형적응에 따른 제한'),
 (525084,'- 거리 밖','·사정범위 밖'),(525128,'- 거리 밖','·사정범위 밖'),
 (525364,'이동 후 사용할 수','·이동 후 사용 불가'),(525416,'이동 후 사용할 수','·이동 후 사용 불가'),
 (50460,'NEXT 공격','NEXT 출격'),
 (1473936,'부대를 구','[부대 편성]'),(1475408,'"사태"','<EVENT>'),(1475996,'지원:','서포트'),
 (18196,'기 무기 변경 기 선택','기체 무기 개조 기체 선택'),
 (18728,'기장치 기장치 선택','확장 무기 무기 선택'),(1033304,'무장 보관','<무기고로>'),
 (527716,'멈춰라','중지하고 종료'),(213132,'경험','경험치'),
 (140224,'최대 공','최대 공격력'),(140312,'최대 공','최대 공격력'),
 (140972,'최대 공','최대 공격력'),(141128,'최대 공','최대 공격력'),
 (140392,'기체 성','기체 성능'),(140428,'기체 성','기체 성능'),
]
for o in (140624,191108,205676,233980,431244,611032,864428,976420,976468,980324,1318652): PATCHES.append((o,'특수기술','특수스킬'))
for o in (400536,400752,401072,401120,401584,401632,985300,986132,986180,1577204,1577420,1577740,1577788,1578252,1578300,1589620,1590452,1590500): PATCHES.append((o,'원호 공','원호공격'))
for o in (401896,402060,402260,402308,402668,402716,987076,988016,988064,1578564,1578728,1578928,1578976,1579336,1579384,1591396,1592336,1592384): PATCHES.append((o,'원호 방','원호방어'))
for o in (989072,990196,990264,1593392,1594516,1594584): PATCHES.append((o,'연속 공','연속공격'))
for o in (400616,401264,401308,988856,989700,989764,1577284,1577932,1577976,1593176,1594020,1594084): PATCHES.append((o,'지도','MAP'))
for o in (400652,401352,401408,986908,987616,987672,1577320,1578020,1578076,1591228,1591936,1591992): PATCHES.append((o,'모든','ALL'))
for o in (990868,991412,991456,1377304,1595188,1595732,1595776): PATCHES.append((o,'바리','배리어'))

def mapping():
 d={}
 for n in ('korean_font_map.tsv','compact_aliases.tsv','general2d_compact_aliases.tsv'):
  with (BUILD/n).open(encoding='utf-8',newline='') as f:
   for r in csv.DictReader(f,delimiter='\t'): d[r['hangul']]=r['proxy']
 return d
def enc(s,m): return ''.join(m.get(c,c) for c in s).encode()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def main():
 sp=BUILD/'_g2_follow_source.psarc';op=BUILD/'_g2_follow_out.psarc';a=c=None
 try:
  with SOURCE.open('rb') as s,sp.open('wb') as t:size,_=decrypt_stream(s,0,t)
  a=PSARC(str(sp));data=bytearray(a.read_entry(ENTRY));m=mapping();changes=[]
  for off,old,new in PATCHES:
   n=struct.unpack('>I',data[off:off+4])[0];st=off+4;en=st+n;actual=bytes(data[st:en]).rstrip(b'\0');expected=enc(old,m);repl=enc(new,m)
   if actual!=expected: raise AssertionError(f'{off}: {actual.hex()} != {expected.hex()} ({old})')
   if len(repl)>n: raise AssertionError(f'{off}: overflow {len(repl)} > {n} ({new})')
   data[st:en]=repl+b'\0'*(n-len(repl));changes.append({'offset':off,'before':old,'after':new,'span':n})
  fixed=rebuild_fixed_blocks(sp,{ENTRY:bytes(data)},op);encode(str(op),SOURCE.read_bytes()[:0x100],str(OUTPUT))
  if OUTPUT.stat().st_size>SOURCE.stat().st_size:raise AssertionError('SDAT grew')
  with OUTPUT.open('ab') as f:f.write(b'\0'*(SOURCE.stat().st_size-OUTPUT.stat().st_size))
  with OUTPUT.open('rb') as f:c=PSARC(SDATReader(f,0));bad=[i for i in range(a.n) if c.read_entry(i)!=(bytes(data) if i==ENTRY else a.read_entry(i))]
  if bad:raise AssertionError(bad[:10])
  st=RETAIL.stat();os.utime(OUTPUT,ns=(st.st_atime_ns,st.st_mtime_ns))
  rep={'source_sha256':sha(SOURCE),'output_sha256':sha(OUTPUT),'changes':changes,'semantic_mismatches':0,'size':OUTPUT.stat().st_size,**fixed};REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(rep,ensure_ascii=False,indent=2))
 finally:
  for x in (a,c):
   if x is not None and hasattr(x.f,'close'):x.f.close()
  sp.unlink(missing_ok=True);op.unlink(missing_ok=True)
if __name__=='__main__':main()
