#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""평문(PSARC 등)을 SDAT로 재암호화. 원본 NPD 헤더를 재사용하고 file_size만 갱신.
블록 = 0x20 메타(해시) + CBC암호화(패딩0x10). 메타는 옵션(hash_fn)으로 계산."""
import struct, hashlib, hmac
from Crypto.Cipher import AES
from sdat import SDAT_KEY, EDAT_KEY_1, parse_header

def forge_metadata(cipher, ck, dev, block_num):
    """flags 0x0100003C(SDAT+ENCRYPTED_KEY+0x10+0x20) 용 블록 메타(0x20) 위조.
    저장해시=HMAC-SHA1(hash_final,cipher)[:0x14], meta[j]^meta[j+0x10]로 인코딩(FLAG_0x20 XOR)."""
    key_result=AES.new(ck,AES.MODE_ECB).encrypt(dev[:12]+struct.pack('>I',block_num))
    hashk     =AES.new(ck,AES.MODE_ECB).encrypt(key_result)          # FLAG_0x10 이중enc
    hash_final=AES.new(EDAT_KEY_1,AES.MODE_ECB).decrypt(hashk)+b'\x00'*4  # generate_hash 0x10000000 + 0패딩
    computed  =hmac.new(hash_final,cipher,hashlib.sha1).digest()[:0x14]
    hi=bytearray(0x10)                       # meta[0x10:0x20]: [0:4]=computed[0x10:0x14], 나머지 0
    hi[0:4]=computed[0x10:0x14]
    lo=bytes(computed[j]^hi[j] for j in range(0x10))  # meta[0:0x10]
    return lo+bytes(hi)

def encode(plain_path, orig_header_bytes, out_path, meta_fn=None, progress=None):
    h=parse_header(orig_header_bytes)
    bs=h['block_size']; dev=h['dev_hash']; dig=h['digest']
    ck=bytes(a^b for a,b in zip(dev,SDAT_KEY))
    import os
    fs=os.path.getsize(plain_path)
    total=(fs+bs-1)//bs
    # 헤더: 원본 복사 + file_size(0x88) 갱신
    hdr=bytearray(orig_header_bytes)
    hdr[0x88:0x90]=struct.pack('>Q', fs)
    fin=open(plain_path,'rb'); fout=open(out_path,'wb')
    fout.write(bytes(hdr))
    for i in range(total):
        length=bs if i<total-1 else (fs-bs*(total-1))
        block=fin.read(length)
        pad=(length+15)&~15
        if len(block)<pad: block=block+b'\x00'*(pad-len(block))
        key_result=AES.new(ck,AES.MODE_ECB).encrypt(dev[:12]+struct.pack('>I',i))
        key_final =AES.new(EDAT_KEY_1,AES.MODE_ECB).decrypt(key_result)
        cipher    =AES.new(key_final,AES.MODE_CBC,dig).encrypt(block)
        meta = forge_metadata(cipher, ck, dev, i)   # 유효 블록해시 위조
        fout.write(meta + cipher)
        if progress and (i%2000==0 or i==total-1): progress(i+1,total,fs)
    fin.close(); fout.close()
    return fs, total

if __name__=='__main__':
    import sys,io
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
    ISO=r'C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso'
    # 원본 NPD 헤더 확보(COMMON)
    with open(ISO,'rb') as f:
        f.seek(735289*2048); orig_hdr=f.read(0x100)
    plain=sys.argv[1]; out=sys.argv[2]
    def prog(i,t,fs): print(f'\r  {i}/{t} 블록',end='',flush=True)
    fs,tot=encode(plain, orig_hdr, out, meta_fn=None, progress=prog)
    print(f'\n완료 {out}: file_size={fs:,} blocks={tot}')
