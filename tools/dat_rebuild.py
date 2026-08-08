#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIXH/DOFS .dat 텍스트 재삽입기.
레코드 = [00 01][글자수 u16 BE][00 00][UTF-8 문자열][00]
문자열은 오름차순 '상대 오프셋 배열'(base 상대)로 참조됨.
delta 매칭으로 오프셋배열 위치와 base를 자동 확정 → 번역문 재삽입 시 배열/글자수/풀 재계산.
무수정 재빌드는 원본과 바이트 동일해야 한다(왕복 검증)."""
import struct

def _find_records(d):
    """풀 시작을 찾아 모든 레코드 파싱. 반환: (records, pool_start, footer_start)
    records = list of dict{rec_off, str_off, cc, text_bytes}"""
    def try_parse(o):
        recs=[]; p=o
        while p+6<=len(d) and d[p:p+2]==b'\x00\x01' and d[p+4:p+6]==b'\x00\x00':
            cc=struct.unpack('>H',d[p+2:p+4])[0]
            s=p+6; end=d.find(b'\x00',s)
            if end<0: break
            sb=d[s:end]
            try: n=len(sb.decode('utf-8'))
            except UnicodeDecodeError: break
            if n!=cc: break
            recs.append({'rec_off':p,'str_off':s,'cc':cc,'text':sb})
            p=end+1
        return recs,p
    # 풀 시작 후보: 00 01 .. 00 00 패턴을 스캔, 3개 이상 연속 파싱되면 채택
    best=None
    o=0
    while True:
        i=d.find(b'\x00\x01',o)
        if i<0: break
        if d[i+4:i+6]==b'\x00\x00':
            recs,footer=try_parse(i)
            if len(recs)>=3:
                best=(i,recs,footer); break
        o=i+1
    if not best: raise ValueError('레코드 풀 없음')
    pool_start,recs,footer=best
    return recs,pool_start,footer

def _find_offset_array(d, recs, pool_start):
    """delta 매칭으로 오프셋배열 시작·base 확정. 배열은 각 레코드 str_off(또는 rec_off)를 base상대로 저장."""
    if len(recs)<3: raise ValueError('레코드 부족')
    # 후보 타깃: str_off 또는 rec_off
    for key in ('str_off','rec_off'):
        targets=[r[key] for r in recs]
        deltas=[targets[i+1]-targets[i] for i in range(len(targets)-1)]
        # prefix(0..pool_start)에서 연속 u32-BE의 delta가 일치하는 위치 탐색
        for arr in range(0, pool_start-4*len(recs), 4):
            v0=struct.unpack('>I',d[arr:arr+4])[0]
            ok=True
            for k,dl in enumerate(deltas):
                a=struct.unpack('>I',d[arr+4*k:arr+4*k+4])[0]
                b=struct.unpack('>I',d[arr+4*k+4:arr+4*k+8])[0]
                if b-a!=dl: ok=False; break
            if ok:
                base=targets[0]-v0
                return arr, base, key
    raise ValueError('오프셋배열 매칭 실패')

class DatFile:
    def __init__(self, data):
        self.d=bytearray(data)
        self.recs,self.pool_start,self.footer_start=_find_records(bytes(self.d))
        self.arr_off,self.base,self.key=_find_offset_array(bytes(self.d),self.recs,self.pool_start)
        self.footer=bytes(self.d[self.footer_start:])
    def texts(self):
        return [r['text'].decode('utf-8') for r in self.recs]
    def rebuild(self, new_texts=None):
        """new_texts: dict{index:str} 또는 None(무수정). 반환: bytes"""
        new_texts=new_texts or {}
        out=bytearray(self.d[:self.pool_start])   # prefix(오프셋배열 포함) 복사 후 배열만 패치
        pool=bytearray(); newoffs=[]
        for i,r in enumerate(self.recs):
            txt = new_texts.get(i, r['text'].decode('utf-8'))
            sb=txt.encode('utf-8'); cc=len(txt)
            rec_off=self.pool_start+len(pool)
            str_off=rec_off+6
            newoffs.append(str_off if self.key=='str_off' else rec_off)
            pool+=b'\x00\x01'+struct.pack('>H',cc)+b'\x00\x00'+sb+b'\x00'
        # 오프셋 배열 패치 (base 상대)
        for k,ab in enumerate(newoffs):
            struct.pack_into('>I', out, self.arr_off+4*k, ab-self.base)
        return bytes(out)+bytes(pool)+self.footer

if __name__=='__main__':
    import sys,io
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
    from psarc import PSARC
    p=PSARC('LOGIC.psarc'); names=p.manifest(); idx={n:i+1 for i,n in enumerate(names)}
    d=p.read_entry(idx['/Dat/FixedData/ProgStrData.dat'])
    df=DatFile(d)
    print(f'레코드 {len(df.recs)}개, pool@{df.pool_start:#x}, 오프셋배열@{df.arr_off:#x}, base={df.base:#x}, key={df.key}')
    print('앞5 문자열:', df.texts()[:5])
    # 왕복: 무수정 재빌드 == 원본?
    rt=df.rebuild()
    print('왕복 바이트동일:', rt==bytes(d), f'({len(rt)} vs {len(d)})')
    if rt!=bytes(d):
        for i in range(min(len(rt),len(d))):
            if rt[i]!=d[i]: print(f'  첫 불일치 @{i:#x}'); break
