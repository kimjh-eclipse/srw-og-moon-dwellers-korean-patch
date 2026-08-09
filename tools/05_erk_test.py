#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import struct, sys, io
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from Crypto.Cipher import AES

ISO = rconfig.require('ISO')
base = 982276*2048
SDAT_KEY   = bytes.fromhex("0D655EF8E674A98AB8505CFA7D012933")
EDAT_KEY_0 = bytes.fromhex("BE959CA8308DEFA2E5E180C63712A9AE")
EDAT_KEY_1 = bytes.fromhex("4CA9C14B01C95309969BEC68AA0BC081")

def ecb_enc(k,d): return AES.new(k,AES.MODE_ECB).encrypt(d)
def ecb_dec(k,d): return AES.new(k,AES.MODE_ECB).decrypt(d)
def cbc_dec(k,iv,d): return AES.new(k,AES.MODE_CBC,iv).decrypt(d)

with open(ISO,'rb') as f:
    f.seek(base); hdr=f.read(0x100)
    digest=hdr[0x40:0x50]; dev_hash=hdr[0x60:0x70]
    f.seek(base+0x120); blk=f.read(16)

crypt_key = bytes(a^b for a,b in zip(dev_hash,SDAT_KEY))
block_key = dev_hash[:12] + struct.pack('>I',0)
key_result = ecb_enc(crypt_key, block_key)

for kn,ek in [("EDAT_KEY_0",EDAT_KEY_0),("EDAT_KEY_1",EDAT_KEY_1)]:
    key_final = ecb_dec(ek, key_result)   # CBC_dec IV=0 single block == ECB_dec
    for ivn,iv in [("digest",digest),("zeros",b"\x00"*16)]:
        dec = cbc_dec(key_final, iv, blk)
        tag = "  <<<< PSAR!!!!" if dec[:4]==b"PSAR" else ""
        print(f"[{kn} / iv={ivn}] {dec.hex(' ')}{tag}")
