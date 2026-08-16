#!/usr/bin/env python3
"""Fix ±/획 collision and add compact 부대 편성 ligatures."""
from __future__ import annotations
import hashlib, importlib.util, json, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT=Path(__file__).resolve().parent; BUILD=ROOT/'korean_build_v3'
INST=Path(r'C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC')
ORIG=ROOT/'original_backups'
COMMON=INST/'Common.psarc.sdat'; G2=INST/'General2d.psarc.sdat'
OUT_COMMON=BUILD/'Common_font_followups_20260814.psarc.sdat'
OUT_G2=BUILD/'General2d_en_formation_font_followups_20260814.psarc.sdat'
REPORT=BUILD/'font_followups_20260814_report.json'
CP_SQUAD=0xA0DA; CP_FORM=0xA0DB; CP_HOEK=0x0093
SLOTS={CP_SQUAD:3746,CP_FORM:3747,CP_HOEK:3748}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def builder():
 s=importlib.util.spec_from_file_location('fb',ROOT/'16_build_korean_font.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def copy_cell(fb,src,dst,slot):
 cx=slot%fb.PHYSICAL_CELLS_X;cy=slot//fb.PHYSICAL_CELLS_X
 for y in range(fb.CELL_SIZE//4):
  for x in range(fb.CELL_SIZE//4):
   bi=(cy*(fb.CELL_SIZE//4)+y)*fb.BLOCKS_X+cx*(fb.CELL_SIZE//4)+x;o=fb.TEXTURE_OFFSET+bi*16;dst[o:o+16]=src[o:o+16]
def ligature(text):
 im=Image.new('L',(32,32),0);dr=ImageDraw.Draw(im);face=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',17)
 box=dr.textbbox((0,0),text,font=face,stroke_width=0);w=box[2]-box[0];h=box[3]-box[1]
 dr.text(((32-w)//2-box[0],(32-h)//2-box[1]),text,font=face,fill=255)
 return im
def pad(p,n):
 if p.stat().st_size>n:raise AssertionError('SDAT grew')
 with p.open('ab') as f:f.write(b'\0'*(n-p.stat().st_size))
def main():
 fb=builder(); temps=[]; archives=[]
 try:
  # Common font
  cs=BUILD/'_c_font_src.psarc';co=BUILD/'_c_font_out.psarc';cr=BUILD/'_c_font_retail.psarc';temps += [cs,co,cr]
  with COMMON.open('rb') as s,cs.open('wb') as t:cl,_=decrypt_stream(s,0,t)
  with (ORIG/'Common.psarc.sdat.orig').open('rb') as s,cr.open('wb') as t:decrypt_stream(s,0,t)
  ca=PSARC(str(cs));ra=PSARC(str(cr));archives += [ca,ra]
  font=bytearray(ca.read_entry(3));retail=ra.read_entry(3)
  # Restore retail ± metric and pixels.
  po=fb.metric_offset(font,0xB1);font[po:po+4]=retail[po:po+4];copy_cell(fb,retail,font,fb.metric_slot(retail,0xB1))
  for cp,text,img,advance in ((CP_SQUAD,'부대',ligature('부대'),31),(CP_FORM,'편성',ligature('편성'),31),(CP_HOEK,'획',fb.render_glyph('획',ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',28)),22)):
   o=fb.metric_offset(font,cp)
   retail_slot=fb.metric_slot(retail,cp)
   font[o:o+4]=retail[o:o+4]
   if retail_slot==0:
    font[o+2:o+4]=bytes((SLOTS[cp]%fb.METRIC_CELLS_X,SLOTS[cp]//fb.METRIC_CELLS_X))
   elif retail_slot!=SLOTS[cp]:raise AssertionError(f'slot {cp:x}: {retail_slot}')
   font[o:o+2]=advance.to_bytes(2,'big');fb.inject_cell(font,SLOTS[cp],img)
  fixedc=rebuild_fixed_entry_spans(cs,{3:bytes(font)},co);encode(str(co),COMMON.read_bytes()[:0x100],str(OUT_COMMON));pad(OUT_COMMON,COMMON.stat().st_size)
  with OUT_COMMON.open('rb') as f:
   v=PSARC(SDATReader(f,0));assert v.read_entry(3)==bytes(font)
  # General2d: EN bullets, formation ligatures, translation-introduced 획 proxy relocation.
  gs=BUILD/'_g_font_src.psarc';go=BUILD/'_g_font_out.psarc';gr=BUILD/'_g_font_retail.psarc';temps += [gs,go,gr]
  with G2.open('rb') as s,gs.open('wb') as t:gl,_=decrypt_stream(s,0,t)
  with (ORIG/'General2d.psarc.sdat.orig').open('rb') as s,gr.open('wb') as t:decrypt_stream(s,0,t)
  ga=PSARC(str(gs));gro=PSARC(str(gr));archives += [ga,gro]
  reps={}; relocated=0
  old='±'.encode();new=chr(CP_HOEK).encode()
  for i in range(ga.n):
   cur=ga.read_entry(i);ret=gro.read_entry(i);d=bytearray(cur);start=0;changed=False
   while True:
    p=cur.find(old,start)
    if p<0:break
    if ret[p:p+len(old)]!=old:d[p:p+len(old)]=new;relocated+=1;changed=True
    start=p+len(old)
   if changed:reps[i]=bytes(d)
  d=bytearray(reps.get(3751,ga.read_entry(3751)))
  for off in (524080,524124):
   n=int.from_bytes(d[off:off+4],'big');st=off+4;raw=bytes(d[st:st+n]).rstrip(b'\0');target='·EN 부족'.encode('utf-8')
   # Existing proxy text is preserved except for adding the bullet.
   if raw.startswith('EN'.encode()):target=b'\xc2\xb7'+raw
   else: target=b'\xc2\xb7'+raw
   if len(target)>n-1:raise AssertionError('EN overflow')
   d[st:st+n]=target+b'\0'*(n-len(target))
  off=59376;n=int.from_bytes(d[off:off+4],'big');target=chr(CP_SQUAD).encode()+chr(CP_FORM).encode()
  if len(target)!=n-1:raise AssertionError('formation size')
  d[off+4:off+4+n]=target+b'\0';reps[3751]=bytes(d)
  fixedg=rebuild_fixed_blocks(gs,reps,go);encode(str(go),G2.read_bytes()[:0x100],str(OUT_G2));pad(OUT_G2,G2.stat().st_size)
  with OUT_G2.open('rb') as f:
   v=PSARC(SDATReader(f,0));bad=[i for i in range(ga.n) if v.read_entry(i)!=reps.get(i,ga.read_entry(i))]
  if bad:raise AssertionError(bad[:10])
  for out,orig in ((OUT_COMMON,ORIG/'Common.psarc.sdat.orig'),(OUT_G2,ORIG/'General2d.psarc.sdat.orig')):
   st=orig.stat();os.utime(out,ns=(st.st_atime_ns,st.st_mtime_ns))
  rep={'Common_sha256':sha(OUT_COMMON),'General2d_sha256':sha(OUT_G2),'relocated_hoeg':relocated,'semantic_mismatches':0,'Common':fixedc,'General2d':fixedg}
  REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(rep,ensure_ascii=False,indent=2))
 finally:
  for a in archives:
   if hasattr(a.f,'close'):a.f.close()
  for p in temps:p.unlink(missing_ok=True)
if __name__=='__main__':main()
