import importlib.util,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def load(p,n):s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load(ROOT/'32_build_battle_safe_full.py','b');rv=load(ROOT/'47_build_battle_c117_review4000_test.py','rv')
from bmd_rebuild import BmdFile
from psarc import PSARC
jobs=[json.loads(x) for x in (ROOT/'battle_review_legacy_fit'/'legacy_fit_10.jsonl').read_text(encoding='utf-8').splitlines()]
p=ROOT/'battle_review_next'/'legacy_fit_10.tsv';rows=[x.split('\t',1) for x in p.read_text(encoding='utf-8').splitlines()];tr={int(u):t for u,t in rows}
mp=b.load_map(ROOT/'korean_build_v5');arc=PSARC(str(ROOT/'korean_build_v5'/'Battle_C117_android0137_v5.psarc'));names={n:i+1 for i,n in enumerate(arc.manifest())};cache={}
def fits(x,t):
 for o in x['occurrences']:
  e=names[o['file']]
  if e not in cache:cache[e]=BmdFile(arc.read_entry(e))
  span=cache[e].records[o['idx']][1]
  if not any((raw:=b.encode(c,mp)) is not None and len(raw)+1<=span for c in rv.candidate_texts(b,t,x['jp'])):return False
 return True
changed=0
for x in jobs:
 t=tr[x['uid']]
 if fits(x,t):continue
 vs=[]
 def add(s):
  if s not in vs:vs.append(s)
 add(t.replace('……','…'))
 add(re.sub(r'([,!?.…]) +',r'\1',t))
 add(re.sub(r'[!?.…]+$','',t))
 add(re.sub(r'([,!?.…]) +',r'\1',t.replace('……','…')))
 add(re.sub(r'[!?.…]+$','',re.sub(r'([,!?.…]) +',r'\1',t.replace('……','…'))))
 for v in vs:
  if v.count('/')==t.count('/') and fits(x,v):tr[x['uid']]=v;changed+=1;break
p.write_text('\n'.join(f'{u}\t{tr[int(u)]}' for u,_ in rows)+'\n',encoding='utf-8')
print({'changed':changed})
