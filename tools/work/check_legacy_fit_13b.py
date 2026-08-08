import importlib.util,json,sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def load(p,n):s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load(ROOT/'32_build_battle_safe_full.py','b');r=load(ROOT/'47_build_battle_c117_review4000_test.py','r')
from bmd_rebuild import BmdFile
from psarc import PSARC
jobs=[json.loads(x) for x in (ROOT/'battle_review_legacy_fit'/'legacy_fit_13.jsonl').read_text(encoding='utf-8').splitlines()][110:220];tr={int(x.split('\t',1)[0]):x.split('\t',1)[1] for x in (ROOT/'battle_review_next'/'legacy_fit_13b.tsv').read_text(encoding='utf-8').splitlines() if x.strip()};mp=b.load_map(ROOT/'korean_build_v5');arc=PSARC(str(ROOT/'korean_build_v5'/'Battle_C117_android0137_v5.psarc'));names={n:i+1 for i,n in enumerate(arc.manifest())};cache={};fails=[];occ=0
for x in jobs:
 for o in x['occurrences']:
  occ+=1;e=names[o['file']]
  if e not in cache:cache[e]=BmdFile(arc.read_entry(e))
  span=cache[e].records[o['idx']][1];sizes=[]
  for c in r.candidate_texts(b,tr.get(x['uid'],''),x['jp']):
   raw=b.encode(c,mp);sz=None if raw is None else len(raw)+1;sizes.append(sz)
   if sz is not None and sz<=span:break
  else:fails.append((x['uid'],span,x['jp'],tr.get(x['uid'],''),sizes))
print(json.dumps({'jobs':len(jobs),'translations':len(tr),'occurrences':occ,'failures':len(fails),'failed_uids':len(set(x[0] for x in fails))},ensure_ascii=False));g=defaultdict(list)
for x in fails:g[x[0]].append(x)
for uid in sorted(g):
 x=g[uid][0];ss=[s for s in x[4] if s is not None];print(uid,min(y[1] for y in g[uid]),min(ss) if ss else 'NA',x[2],x[3],sep='\t')
