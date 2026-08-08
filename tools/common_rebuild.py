#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMMON PSARC 텍스트 컨테이너 = .csb (chunked 'CSB ' 컨테이너).
구조: 'CSB ' 헤더 + 청크들. 텍스트는 'STRP'(String Pool) 청크에 있다.

STRP 청크 레이아웃(빅엔디안):
  +0x00  'STRP'                     (4)  청크 태그
  +0x04  chunk_size u32             (4)  태그 시작(=STRP)부터 청크 끝까지 총 바이트
  +0x08  string_count u32           (4)  풀에 든 문자열 개수
  +0x0c  string_data                     string_count개의 널종료 UTF-8 문자열
                                         (+ 청크 정렬용 널 패딩 가능)

문자열은 다른 청크('LNP ' 등)에서 '풀 내부 바이트 오프셋'(u32 BE)으로 참조된다.
→ 오프셋을 바꾸면 참조가 전부 깨지므로, .bmd와 동일하게 '제자리 길이제한 교체'.
  번역문(+null)이 원문 span(원문바이트+null) 이내면 무손실, 초과 시 문자경계로 잘림(경고).
무수정 재빌드는 원본과 바이트 동일해야 한다(왕복 검증)."""
import struct

def _u32(d,o): return struct.unpack('>I', d[o:o+4])[0]

class CsbFile:
    MAGIC=b'CSB '
    def __init__(self, data):
        self.d=bytearray(data)
        if bytes(self.d[:4])!=self.MAGIC:
            raise ValueError('CSB 매직 아님')
        self.strp_off=self._find_strp()
        if self.strp_off<0:
            raise ValueError('STRP 청크 없음')
        self.chunk_size=_u32(self.d, self.strp_off+4)
        self.count=_u32(self.d, self.strp_off+8)
        self.data_start=self.strp_off+12
        self.chunk_end=self.strp_off+self.chunk_size
        self.records=self._parse()   # [(abs_off, span(널포함), text)]  len==count

    def _find_strp(self):
        # 청크를 태그+크기로 순회하며 STRP를 찾는다(단순 검색으로 충분히 견고)
        o=self.d.find(b'STRP')
        return o

    def _parse(self):
        recs=[]; o=self.data_start
        for _ in range(self.count):
            e=self.d.find(b'\x00', o)
            if e<0 or e>=self.chunk_end:
                raise ValueError(f'문자열 파싱 범위 초과 @{o:#x}')
            raw=bytes(self.d[o:e])
            t=raw.decode('utf-8')     # 실패 시 예외로 즉시 드러냄
            recs.append((o, e-o+1, t))
            o=e+1
        return recs

    def texts(self):
        return [t for _,_,t in self.records]

    def jp_indices(self):
        """일본어(히라가나/가타카나/한자) 문자를 포함한 문자열의 인덱스."""
        def isjp(c):
            o=ord(c)
            return 0x3040<=o<=0x30ff or 0x3400<=o<=0x9fff or 0xff66<=o<=0xff9f
        return [i for i,(_,_,t) in enumerate(self.records) if any(isjp(c) for c in t)]

    def replace(self, index_to_ko, warn=None):
        """제자리 교체(오프셋/파일크기 불변). 반환: (bytes, 잘린수)."""
        truncated=0
        for i,ko in index_to_ko.items():
            off,span,_=self.records[i]
            kb=ko.encode('utf-8')+b'\x00'
            if len(kb)>span:
                s=ko
                while s and len(s.encode('utf-8'))+1>span: s=s[:-1]
                kb=s.encode('utf-8')+b'\x00'; truncated+=1
                if warn: warn(i, ko, s)
            kb=kb+b'\x00'*(span-len(kb))    # 원본 span으로 널패딩(오프셋 유지)
            self.d[off:off+span]=kb
        return bytes(self.d), truncated

if __name__=='__main__':
    import sys,io
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    from psarc import PSARC
    p=PSARC('COMMON.psarc'); names=p.manifest(); idx={n:i+1 for i,n in enumerate(names)}
    csb=[n for n in names if n.lower().endswith('.csb')]
    total_str=total_jp=0; all_ok=True
    for n in csb:
        d=p.read_entry(idx[n])
        cf=CsbFile(d)
        rt,_=cf.replace({})                 # 무수정 재빌드
        ok=(rt==bytes(d))
        all_ok&=ok
        jp=cf.jp_indices()
        total_str+=len(cf.texts()); total_jp+=len(jp)
        print(f"{n.split('/')[-1]:<28} strings={cf.count:>4} JP포함={len(jp):>4} 왕복동일={ok}")
    print(f"\n총 문자열 {total_str}, JP포함 문자열 {total_jp}, 전체 왕복 바이트동일={all_ok}")
    # 한글 제자리 교체 데모(Archive_Ending 첫 JP 문자열)
    d=p.read_entry(idx['/Dat/Archive/Csb/Archive_2OG.csb'])
    cf=CsbFile(d); jp=cf.jp_indices()
    print("\nArchive_2OG JP 예시(앞5):")
    for i in jp[:5]:
        print(f"  [{i}] {cf.texts()[i]!r}")
    i0=jp[0]
    out,tr=cf.replace({i0:'한글치환테스트'})
    print(f"한글교체 크기동일={len(out)==len(d)} 잘림={tr}")
    print("재파싱 확인:", CsbFile(out).texts()[i0])
