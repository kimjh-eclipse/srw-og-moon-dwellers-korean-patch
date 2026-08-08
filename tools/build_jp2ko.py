#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""번역 배치(translated/)와 원문(extract/unique_jp.jsonl)을 uid로 짝지어 {일본어:한국어} 사전 생성.
컨테이너별 매칭률 확인."""
import sys, io, json, glob, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

uni = [json.loads(l)['jp'] for l in open('extract/unique_jp.jsonl', encoding='utf-8')]

def unesc(s):
    return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')

ko = {}
for f in sorted(glob.glob('translated/batch_*.tsv')):
    for ln in open(f, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln:
            continue
        uid, _, txt = ln.partition('\t')
        try:
            ko[int(uid)] = unesc(txt)
        except ValueError:
            pass

jp2ko = {uni[u]: ko[u] for u in range(len(uni)) if u in ko and ko[u] != uni[u]}
json.dump(jp2ko, open('jp2ko.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'번역 사전 {len(jp2ko):,}쌍 (총 uid {len(uni):,}, 번역줄 {len(ko):,})')

from psarc import PSARC
from dat_rebuild import DatFile

def cover(texts):
    return sum(1 for t in texts if t in jp2ko), len(texts)

p = PSARC('LOGIC.psarc'); names = p.manifest(); idx = {n: i+1 for i, n in enumerate(names)}
tm = tc = 0
for n in names:
    if n.endswith('.dat'):
        try: t = DatFile(p.read_entry(idx[n])).texts()
        except Exception: continue
        m, c = cover(t); tm += m; tc += c
print(f'LOGIC .dat 매칭: {tm}/{tc}')

if os.path.exists('common_rebuild.py'):
    try:
        from common_rebuild import CsbFile
        pc = PSARC('COMMON.psarc'); cn = pc.manifest(); cd = {n: i+1 for i, n in enumerate(cn)}
        cm = cc = 0
        for n in cn:
            if n.lower().endswith('.csb'):
                try:
                    cf = CsbFile(pc.read_entry(cd[n]))
                    t = [cf.texts()[i] for i in cf.jp_indices()]
                except Exception: continue
                m, c = cover(t); cm += m; cc += c
        print(f'COMMON .csb(JP) 매칭: {cm}/{cc}')
    except Exception as e:
        print('CSB 매칭 확인 실패:', e)
