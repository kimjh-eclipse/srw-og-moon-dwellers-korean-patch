#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BATTLE PSARC의 .bmd 배틀 메시지 전체 추출 → 번역용.
산출: extract_bmd/{master.jsonl(재삽입 좌표: psarc/file/idx/jp), unique_jp.jsonl, batches/}."""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sdat import SDATReader
from psarc import PSARC
from bmd_rebuild import BmdFile

BAT = r'C:/Emul/PS3/rpcs3-v0.0.27-14986-db7f84f9_win64/dev_hdd0/game/BLJS10335/USRDIR/PSARC/Battle.psarc.sdat'
OUT = 'extract_bmd'; os.makedirs(OUT + '/batches', exist_ok=True)

def is_jp(t):
    return any(0x3040 <= ord(c) <= 0x30ff or 0x3400 <= ord(c) <= 0x9fff or 0xff66 <= ord(c) <= 0xff9f for c in t)

p = PSARC(SDATReader(open(BAT, 'rb'), 0))
names = p.manifest()
bmd = [(i, n) for i, n in enumerate(names) if n.lower().endswith('.bmd')]
print(f'.bmd {len(bmd)}개 추출...', flush=True)

master = open(os.path.join(OUT, 'master.jsonl'), 'w', encoding='utf-8')
unique = {}; total = 0; jp_total = 0
for k, (i, nm) in enumerate(bmd):
    if k % 50 == 0 and k:
        print(f'  {k}/{len(bmd)} (누적 JP {jp_total:,})', flush=True)
    try:
        data = p.read_entry(i + 1); bf = BmdFile(data)
    except Exception:
        continue
    for idx, t in enumerate(bf.texts()):
        total += 1
        if not is_jp(t):
            continue                       # 구조성/기호 문자열 제외
        master.write(json.dumps({'psarc': 'BATTLE', 'file': nm, 'idx': idx, 'jp': t}, ensure_ascii=False) + '\n')
        if t not in unique:
            unique[t] = len(unique)
        jp_total += 1
master.close()

uni = list(unique.keys())
with open(os.path.join(OUT, 'unique_jp.jsonl'), 'w', encoding='utf-8') as f:
    for u in uni:
        f.write(json.dumps({'jp': u}, ensure_ascii=False) + '\n')

PER = 400
nb = (len(uni) + PER - 1) // PER
for b in range(nb):
    with open(os.path.join(OUT, 'batches', f'batch_{b+1:04d}.tsv'), 'w', encoding='utf-8') as f:
        for j, u in enumerate(uni[b*PER:(b+1)*PER]):
            esc = u.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')
            f.write(f'{b*PER+j}\t{esc}\n')

print(f'\n=== BATTLE .bmd: 전체 {total:,}줄, JP {jp_total:,}줄, 고유 JP {len(uni):,}개, 배치 {nb}개 → {OUT}/ ===')
