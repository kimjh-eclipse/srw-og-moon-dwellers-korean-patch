#!/usr/bin/env python3
"""Align the two EN-shortage warning rows with the other bullet rows."""
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
OUTPUT=BUILD/'General2d_en_alignment_20260814.psarc.sdat'
REPORT=BUILD/'general2d_en_alignment_20260814_report.json'; ENTRY=3751
PATCHES=((524080,'EN 부족','·EN 부족'),(524124,'EN 부족','·EN 부족'))

def table():
 d={}
 for n in ('korean_font_map.tsv','compact_aliases.tsv','general2d_compact_aliases.tsv'):
  with (BUILD/n).open(encoding='utf-8',newline='') as f:
   for r in csv.DictReader(f,delimiter='\t'): d[r['hangul']]=r['proxy']
 return d
def enc(s,m): return ''.join(m.get(c,c) for c in s).encode('utf-8')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
 return h.hexdigest()
def main():
 sp=BUILD/'_g2_en_source.psarc'; op=BUILD/'_g2_en_output.psarc'; a=c=None
 try:
  with SOURCE.open('rb') as s,sp.open('wb') as t: logical,_=decrypt_stream(s,0,t)
  a=PSARC(str(sp)); data=bytearray(a.read_entry(ENTRY)); m=table(); changes=[]
  for off,before,after in PATCHES:
   n=struct.unpack('>I',data[off:off+4])[0]; st=off+4; en=st+n
   actual=bytes(data[st:en]).rstrip(b'\0'); expected=enc(before,m); repl=enc(after,m)
   if actual!=expected: raise AssertionError(f'{off}: {actual.hex()} != {expected.hex()}')
   if len(repl)>n-1: raise AssertionError(f'{off}: overflow {len(repl)} > {n-1}')
   data[st:en]=repl+b'\0'*(n-len(repl)); changes.append({'offset':off,'before':before,'after':after,'record_length':n})
  fixed=rebuild_fixed_blocks(sp,{ENTRY:bytes(data)},op)
  if op.stat().st_size!=logical: raise AssertionError('logical size changed')
  encode(str(op),SOURCE.read_bytes()[:0x100],str(OUTPUT))
  if OUTPUT.stat().st_size>SOURCE.stat().st_size: raise AssertionError('SDAT grew')
  with OUTPUT.open('ab') as f:f.write(b'\0'*(SOURCE.stat().st_size-OUTPUT.stat().st_size))
  with OUTPUT.open('rb') as f:
   c=PSARC(SDATReader(f,0)); bad=[i for i in range(a.n) if c.read_entry(i)!=(bytes(data) if i==ENTRY else a.read_entry(i))]
  if bad: raise AssertionError(bad[:10])
  st=RETAIL.stat(); os.utime(OUTPUT,ns=(st.st_atime_ns,st.st_mtime_ns))
  rep={'source_sha256':sha(SOURCE),'output_sha256':sha(OUTPUT),'changes':changes,'semantic_mismatches':0,'size':OUTPUT.stat().st_size,**fixed}
  REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2))
 finally:
  for x in (a,c):
   if x is not None and hasattr(x.f,'close'): x.f.close()
  sp.unlink(missing_ok=True); op.unlink(missing_ok=True)
if __name__=='__main__': main()
