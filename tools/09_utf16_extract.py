from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
load_table("_INLINE")[0]
import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from psarc import PSARC

p=PSARC("LOGIC.psarc"); names=p.manifest(); idx={n:i+1 for i,n in enumerate(names)}
data=p.read_entry(idx["/Dat/FixedData/ProgStrData.dat"])

# 헤더 구조 덤프
print(load_table("_INLINE")[1], data[:32].hex(' '))
print(f"magic={data[0:4]} sec2@0x10={data[0x10:0x14]}")

# UTF-16BE 널종료 문자열 스캐너
def utf16be_strings(buf, min_len=2):
    res=[]; i=0; n=len(buf)
    while i+1 < n:
        # 문자열 시작 후보: 유효 BMP 문자
        j=i; chars=[]
        while j+1 < n:
            cp=(buf[j]<<8)|buf[j+1]
            if cp==0x0000: break
            if cp < 0x20 and cp not in (0x0a,): break
            chars.append(cp); j+=2
        if len(chars)>=min_len and (j+1<n and ((buf[j]<<8)|buf[j+1])==0):
            try:
                s=bytes().join(struct.pack('>H',c) for c in chars).decode('utf-16-be')
                if any(load_table("_INLINE")[2]<=ch<=load_table("_INLINE")[3] or load_table("_INLINE")[4]<=ch<=load_table("_INLINE")[5] or ch.isascii() for ch in s):
                    res.append((i,s))
            except: pass
            i=j+2
        else:
            i+=2
    return res

strs=utf16be_strings(data)
print(f"\nUTF-16BE 문자열 {len(strs)}개 추출\n--- 앞 25개 (offset, 내용) ---")
for off,s in strs[:25]:
    disp=s if len(s)<=40 else s[:40]+'…'
    print(f"  0x{off:06X}: {disp!r}")
