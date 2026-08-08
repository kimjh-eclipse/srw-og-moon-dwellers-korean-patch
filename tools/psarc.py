#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PSARC 1.4 파서/추출기 (zlib). entry[0]=매니페스트(경로 목록)."""
import struct, zlib, sys, io, os

def be(data):
    v=0
    for b in data: v=(v<<8)|b
    return v

class PSARC:
    def __init__(self, path):
        if hasattr(path,'read'):        # 파일류 객체(SDATReader 등)
            self.f=path; self.path=getattr(path,'name','<stream>')
        else:
            self.f=open(path,'rb'); self.path=path
        self.f.seek(0)
        h=self.f.read(32)
        assert h[0:4]==b'PSAR', "PSAR 아님"
        self.ver=(h[4]<<8|h[5], h[6]<<8|h[7])
        self.comp=h[8:12]
        self.toc_len=struct.unpack('>I',h[12:16])[0]
        self.ent_size=struct.unpack('>I',h[16:20])[0]
        self.n=struct.unpack('>I',h[20:24])[0]
        self.block_size=struct.unpack('>I',h[24:28])[0]
        self.flags=struct.unpack('>I',h[28:32])[0]
        # TOC 엔트리
        toc=self.f.read(self.n*self.ent_size)
        self.entries=[]
        for i in range(self.n):
            e=toc[i*self.ent_size:(i+1)*self.ent_size]
            self.entries.append({
                'md5': e[0:16],
                'block_idx': struct.unpack('>I',e[16:20])[0],
                'orig_size': be(e[20:25]),
                'offset': be(e[25:30]),
            })
        # 블록 크기 테이블
        if self.block_size <= 0x100: self.bw=1
        elif self.block_size <= 0x10000: self.bw=2
        elif self.block_size <= 0x1000000: self.bw=3
        else: self.bw=4
        nblk=(self.toc_len - 32 - self.n*self.ent_size)//self.bw
        bt=self.f.read(nblk*self.bw)
        self.block_table=[be(bt[i*self.bw:(i+1)*self.bw]) for i in range(nblk)]

    def read_entry(self, idx):
        e=self.entries[idx]
        self.f.seek(e['offset'])
        out=bytearray(); bi=e['block_idx']
        while len(out) < e['orig_size']:
            if bi >= len(self.block_table):
                break                                   # 블록테이블 초과 → 중단
            csize=self.block_table[bi]; bi+=1
            before=len(out)
            if csize==0:
                out+=self.f.read(self.block_size)
            else:
                chunk=self.f.read(csize)
                if chunk[:1]==b'\x78':
                    try: out+=zlib.decompress(chunk)
                    except zlib.error: out+=chunk
                else:
                    out+=chunk
            if len(out)==before:
                break                                   # 진전 없음(EOF/빈블록) → 무한루프 방지
        return bytes(out[:e['orig_size']])

    def manifest(self):
        raw=self.read_entry(0)
        return [p for p in raw.decode('utf-8','replace').replace('\r','').split('\n') if p]

if __name__=='__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    p=PSARC(sys.argv[1])
    print(f"버전{p.ver} comp={p.comp} 엔트리={p.n} blocksize={p.block_size} flags={p.flags}")
    names=p.manifest()
    print(f"매니페스트 경로 {len(names)}개 (엔트리 index 1..{p.n-1}에 매핑)\n")
    # 확장자 통계
    from collections import Counter
    exts=Counter(os.path.splitext(n)[1].lower() for n in names)
    print("확장자 분포:", dict(exts.most_common()))
    print("\n--- 상위 60개 경로 ---")
    for i,n in enumerate(names[:60],1):
        e=p.entries[i]
        print(f"{i:4} {e['orig_size']:>10,}B  {n}")
