#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Battle BMD message rebuilding.

Format: header/metadata + big-endian relative-offset references + a
NUL-terminated UTF-8 string pool.  ``replace`` remains available for a
byte-stable edit, while ``replace_variable`` rebuilds the pool and retargets
all proven relative references so translated dialogue may grow safely.
"""
import re
import struct

_UTF8=re.compile(rb'(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3})+')

class BmdFile:
    def __init__(self, data, pool_start=None):
        self.d=bytearray(data)
        # After a variable rebuild, the final bytes of the preceding pointer
        # table can coincidentally be printable ASCII.  In that case a raw
        # UTF-8 scan may start two bytes too early across the table/pool
        # boundary.  Callers that are validating a rebuilt BMD can therefore
        # provide the already-proven original pool location.
        self.pool_start=self._find_pool() if pool_start is None else pool_start
        self.records=self._parse()   # [(off, span(널포함), text)]

    def _find_pool(self):
        # 첫 '긴 UTF-8 문자열'(≥3문자) 위치를 풀 시작으로
        for m in _UTF8.finditer(bytes(self.d)):
            seg=m.group()
            try: t=seg.decode('utf-8')
            except: continue
            if len(t)>=3 and any(ord(c)>0x2000 for c in t):
                return m.start()
        return len(self.d)

    def _parse(self):
        recs=[]; o=self.pool_start; N=len(self.d)
        while o<N:
            e=self.d.find(b'\x00',o)
            if e<0: break
            raw=bytes(self.d[o:e])
            try: t=raw.decode('utf-8')
            except UnicodeDecodeError:
                # 풀 종료(푸터) 추정 → 중단
                break
            if raw:
                recs.append((o, e-o+1, t))   # span 널 포함
            o=e+1
        return recs

    def texts(self):
        return [t for _,_,t in self.records]

    def replace(self, index_to_ko, warn=None):
        """제자리 교체. 반환: (bytes, 잘린수). 오프셋/크기 불변."""
        truncated=0
        for i,ko in index_to_ko.items():
            off,span,_=self.records[i]
            kb=ko.encode('utf-8')+b'\x00'
            if len(kb)>span:
                # 원문 바이트길이 초과 → 들어갈 만큼 자름(문자 경계 보존)
                s=ko
                while len(s.encode('utf-8'))+1>span and s: s=s[:-1]
                kb=s.encode('utf-8')+b'\x00'; truncated+=1
                if warn: warn(i, ko, s)
            kb=kb+b'\x00'*(span-len(kb))     # 원본 span으로 0패딩(오프셋 유지)
            self.d[off:off+span]=kb
        return bytes(self.d), truncated

    def replace_variable(self, index_to_text):
        """Rebuild the UTF-8 pool and retarget its big-endian offset table.

        Battle BMDs store string addresses as 32-bit big-endian offsets from
        ``pool_start``.  Unlike the old in-place helper, this method permits
        translated strings to grow while retaining the header and trailing
        data verbatim.  It deliberately refuses files whose pointer coverage
        cannot be proven from the existing pool.
        """
        old_pool_end = self.records[-1][0] + self.records[-1][1] if self.records else self.pool_start
        old_rel = [off - self.pool_start for off, _span, _text in self.records]
        new_pool = bytearray()
        new_rel = []
        for index, (_off, _span, text) in enumerate(self.records):
            new_rel.append(len(new_pool))
            value = index_to_text.get(index, text)
            new_pool += value.encode("utf-8") + b"\0"

        prefix = bytearray(self.d[: self.pool_start])
        pointer_hits = 0
        offsets = {old: new for old, new in zip(old_rel, new_rel)}
        for pos in range(0, len(prefix) - 3, 4):
            value = struct.unpack_from(">I", prefix, pos)[0]
            if value in offsets:
                struct.pack_into(">I", prefix, pos, offsets[value])
                pointer_hits += 1
        if self.records and pointer_hits < len(self.records):
            raise ValueError(
                f"insufficient BMD pointer coverage: {pointer_hits} for {len(self.records)} strings"
            )
        return bytes(prefix + new_pool + self.d[old_pool_end:])

if __name__=='__main__':
    import sys,io
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
    from sdat import SDATReader
    from psarc import PSARC
    BAT=r'C:/Emul/PS3/rpcs3-v0.0.27-14986-db7f84f9_win64/dev_hdd0/game/BLJS10335/USRDIR/PSARC/Battle.psarc.sdat'
    p=PSARC(SDATReader(open(BAT,'rb'),0)); names=p.manifest(); idx={n:i+1 for i,n in enumerate(names)}
    d=p.read_entry(idx['/Dat/Battle/Message/@Ja/0002_ja.bmd'])
    bf=BmdFile(d)
    print(f'문자열 {len(bf.records)}개, pool@{bf.pool_start:#x}')
    print('앞3:', bf.texts()[:3])
    # 무수정 재빌드 == 원본?
    out,_=bf.replace({})
    print('무수정 왕복 바이트동일:', out==bytes(d))
    # 한글 제자리 교체 테스트
    bf2=BmdFile(d)
    out2,tr=bf2.replace({0:'저 적은 본함으로 잡는다',1:'전원 분투를 기대한다'})
    print(f'한글교체 크기동일: {len(out2)==len(d)}, 잘림 {tr}')
    print('재파싱:', BmdFile(out2).texts()[:3])
