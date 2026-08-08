#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LOGIC.psarc 내 텍스트 유력 .dat 추출 후 인코딩 판별(SJIS/UTF8/UTF16)."""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from psarc import PSARC

p=PSARC("LOGIC.psarc")
names=p.manifest()
idx={n:i+1 for i,n in enumerate(names)}   # entry index (1-based)

targets=["/Dat/FixedData/ProgStrData.dat",
         "/Dat/FixedData/PlayEndMessageData.dat",
         "/Dat/FixedData/HelpData.dat",
         "/Dat/FixedData/KeyWordData.dat"]

def try_decode(data, enc):
    try:
        s=data.decode(enc)
        # 제어문자 제외한 '읽을 수 있는' 비율
        printable=sum(1 for c in s if c.isprintable() or c in '\n\r\t')
        return printable/max(1,len(s)), s
    except Exception:
        return 0,None

for t in targets:
    if t not in idx:
        print(f"[{t}] 없음"); continue
    data=p.read_entry(idx[t])
    print(f"\n===== {t}  ({len(data):,}B) =====")
    print("  첫 64B:", data[:64].hex(' '))
    # 인코딩별 판독률
    for enc in ("shift_jis","cp932","utf-8","utf-16-le","utf-16-be"):
        r,s=try_decode(data,enc)
        print(f"  {enc:10} 판독률 {r:.2%}")
    # cp932로 일본어 문자열 샘플 추출
    jp=re.findall(rb'(?:[\x81-\x9f\xe0-\xfc][\x40-\x7e\x80-\xfc]){2,}', data)
    print(f"  일본어(2byte SJIS) 후보 문자열 {len(jp)}개")
    for frag in jp[:5]:
        try: print("     ·", frag.decode('cp932'))
        except: pass
