#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검증 완료된 OGMD SDAT 복호화 모듈.
파라미터: version4, flags 0x0100003C (SDAT, ERK, 비압축, 0x20 인터리브)
  crypt_key = dev_hash ^ SDAT_KEY
  key_result= ECB_enc(crypt_key, dev_hash[:12]+blk_be)
  key_final = ECB_dec(EDAT_KEY_1, key_result)   # ERK 변환 (v>=2)
  plain     = CBC_dec(key_final, IV=digest, cipher)
  블록 N 위치 = 0x100 + N*(0x20+block_size) + 0x20
"""
import struct
from Crypto.Cipher import AES
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다

SDAT_KEY   = bytes.fromhex("0D655EF8E674A98AB8505CFA7D012933")
EDAT_KEY_1 = bytes.fromhex("4CA9C14B01C95309969BEC68AA0BC081")

def _ecb_enc(k,d): return AES.new(k,AES.MODE_ECB).encrypt(d)
def _ecb_dec(k,d): return AES.new(k,AES.MODE_ECB).decrypt(d)
def _cbc_dec(k,iv,d): return AES.new(k,AES.MODE_CBC,iv).decrypt(d)

def parse_header(hdr):
    assert hdr[0:4]==b'NPD\x00', "NPD 아님"
    info = {
        'version'  : struct.unpack('>I',hdr[0x04:0x08])[0],
        'digest'   : hdr[0x40:0x50],
        'title_hash':hdr[0x50:0x60],
        'dev_hash' : hdr[0x60:0x70],
        'flags'    : struct.unpack('>I',hdr[0x80:0x84])[0],
        'block_size':struct.unpack('>I',hdr[0x84:0x88])[0],
        'file_size': struct.unpack('>Q',hdr[0x88:0x90])[0],
    }
    return info

def decrypt_stream(fin, base_off, fout, progress=None):
    """fin의 base_off 위치에 있는 SDAT를 복호화해 fout에 기록. 평문 크기 반환."""
    fin.seek(base_off); hdr=fin.read(0x100)
    h=parse_header(hdr)
    bs=h['block_size']; fs=h['file_size']; dev=h['dev_hash']; dig=h['digest']
    assert h['flags'] & 0x01000000, "SDAT 플래그 아님"
    crypt_key = bytes(a^b for a,b in zip(dev,SDAT_KEY))
    total = (fs + bs - 1)//bs
    written=0
    for i in range(total):
        blk_off = base_off + 0x100 + i*(0x20+bs) + 0x20
        length  = bs if i < total-1 else (fs - bs*(total-1))
        pad     = (length+15)&~15
        fin.seek(blk_off); cipher=fin.read(pad)
        if len(cipher) < pad:               # 마지막 블록 디스크 절삭 대비
            cipher = cipher + b"\x00"*(pad-len(cipher))
        block_key = dev[:12] + struct.pack('>I', i)
        key_result= _ecb_enc(crypt_key, block_key)
        key_final = _ecb_dec(EDAT_KEY_1, key_result)
        plain     = _cbc_dec(key_final, dig, cipher)
        fout.write(plain[:length]); written+=length
        if progress and (i % 512 == 0 or i==total-1):
            progress(i+1, total, written)
    return written, h

class SDATReader:
    """SDAT를 평문 오프셋 기준 랜덤액세스로 복호화하는 파일류 객체.
    각 블록은 블록번호로 키가 유도되어 독립 복호화 가능 → 전체를 디스크에 풀 필요 없음."""
    def __init__(self, fin, base_off):
        self.fin=fin; self.base=base_off
        fin.seek(base_off); hdr=fin.read(0x100); self.h=parse_header(hdr)
        assert self.h['flags'] & 0x01000000, "SDAT 아님"
        self.bs=self.h['block_size']; self.fs=self.h['file_size']
        self.dev=self.h['dev_hash']; self.dig=self.h['digest']
        self.crypt_key=bytes(a^b for a,b in zip(self.dev,SDAT_KEY))
        self.total=(self.fs+self.bs-1)//self.bs
        self._cache={}; self._order=[]; self._pos=0
    def _block(self, i):
        if i in self._cache: return self._cache[i]
        length = self.bs if i < self.total-1 else (self.fs - self.bs*(self.total-1))
        pad=(length+15)&~15
        self.fin.seek(self.base + 0x100 + i*(0x20+self.bs) + 0x20)
        cipher=self.fin.read(pad)
        if len(cipher)<pad: cipher+=b"\x00"*(pad-len(cipher))
        bk=self.dev[:12]+struct.pack('>I',i)
        kf=_ecb_dec(EDAT_KEY_1, _ecb_enc(self.crypt_key, bk))
        plain=_cbc_dec(kf, self.dig, cipher)[:length]
        self._cache[i]=plain; self._order.append(i)
        if len(self._order)>8:
            old=self._order.pop(0)
            if old in self._cache: del self._cache[old]
        return plain
    def seek(self, off, whence=0):
        if whence==0: self._pos=off
        elif whence==1: self._pos+=off
        else: self._pos=self.fs+off
        return self._pos
    def tell(self): return self._pos
    def read(self, n=-1):
        if n<0: n=self.fs-self._pos
        out=bytearray(); end=min(self._pos+n, self.fs)
        while self._pos<end:
            bi=self._pos//self.bs; boff=self._pos%self.bs
            blk=self._block(bi); take=min(self.bs-boff, end-self._pos)
            out+=blk[boff:boff+take]; self._pos+=take
        return bytes(out)

if __name__ == '__main__':
    import sys
    ISO=rconfig.require('ISO')
    LBA={"LOGIC_PSARC.SDAT":982276,"COMMON_PSARC.SDAT":735289,"GENERAL2D_PSARC.SDAT":436663}
    name=sys.argv[1] if len(sys.argv)>1 else "LOGIC_PSARC.SDAT"
    out =sys.argv[2] if len(sys.argv)>2 else name.replace('.SDAT','.psarc')
    def prog(i,t,w): print(f"\r  {i}/{t} 블록  ({w:,} B)", end='', flush=True)
    with open(ISO,'rb') as fin, open(out,'wb') as fout:
        n,h=decrypt_stream(fin, LBA[name]*2048, fout, prog)
    print(f"\n완료: {out}  ({n:,} B)  첫4B검증은 head로 확인")
