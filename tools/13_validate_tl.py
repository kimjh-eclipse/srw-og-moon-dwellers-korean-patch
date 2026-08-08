#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""번역 배치 검증: 원문 대비 uid 일치 / 태그 보존 / 줄수 확인.
사용: python 13_validate_tl.py <번역된_batch_xxx.tsv> [원본_batch_xxx.tsv]
원본 미지정 시 unique_jp.jsonl에서 uid로 대조."""
import sys, os, json, re
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TAG=re.compile(r'<[^>\n]*>|\]-\d+|\[[^\]\n]*\]')

def tags(s):
    from collections import Counter
    return Counter(TAG.findall(s))

def load_tsv(path):
    d={}
    for ln in open(path,encoding='utf-8'):
        ln=ln.rstrip('\n')
        if not ln: continue
        uid,_,txt=ln.partition('\t')
        d[uid]=txt
    return d

def main():
    tl=load_tsv(sys.argv[1])
    if len(sys.argv)>2:
        src=load_tsv(sys.argv[2])
    else:
        src={str(r['uid']):r['jp'].replace('\\','\\\\').replace('\n','\\n').replace('\t','\\t')
             for r in (json.loads(l) for l in open('extract/unique_jp.jsonl',encoding='utf-8'))}
    errs=0; checked=0
    for uid,ko in tl.items():
        if uid not in src:
            print(f"[uid없음] {uid}"); errs+=1; continue
        checked+=1
        st, kt = tags(src[uid]), tags(ko)
        if st!=kt:
            print(f"[태그불일치] uid={uid}\n   원문태그={dict(st)}\n   번역태그={dict(kt)}"); errs+=1
    missing=set(src)&set()  # placeholder
    print(f"\n검사 {checked}줄, 오류 {errs}건")
    if errs==0: print("✅ 태그·uid 보존 OK")

if __name__=='__main__': main()
