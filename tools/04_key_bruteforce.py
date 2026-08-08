#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데이터 오프셋 0x120 고정, 키/IV 유도 조합을 브루트포스하여 PSAR 탐색."""
import struct
from Crypto.Cipher import AES

ISO = r"C:/Emul/Switch/패치유틸.xdeltaUI/Super Robot Taisen OG - The Moon Dwellers (Japan).iso"
base = 982276*2048
SDAT_KEY = bytes.fromhex("0D655EF8E674A98AB8505CFA7D012933")
EDAT_KEY_0 = bytes.fromhex("BE959CA8308DEFA2E5E180C63712A9AE")
EDAT_KEY_1 = bytes.fromhex("4CA9C14B01C95309969BEC68AA0BC081")

with open(ISO,'rb') as f:
    f.seek(base); hdr=f.read(0x120)
    digest=hdr[0x40:0x50]; title_hash=hdr[0x50:0x60]; dev_hash=hdr[0x60:0x70]
    f.seek(base+0x120); blk=f.read(32)

def ecb_enc(k,d): return AES.new(k,AES.MODE_ECB).encrypt(d)
def ecb_dec(k,d): return AES.new(k,AES.MODE_ECB).decrypt(d)
def cbc_dec(k,iv,d): return AES.new(k,AES.MODE_CBC,iv).decrypt(d)

block_key = dev_hash[:12] + struct.pack('>I',0)

crypt_candidates = {
 "devhash^SDAT": bytes(a^b for a,b in zip(dev_hash,SDAT_KEY)),
 "SDAT_KEY": SDAT_KEY,
 "dev_hash": dev_hash,
 "title^SDAT": bytes(a^b for a,b in zip(title_hash,SDAT_KEY)),
 "digest^SDAT": bytes(a^b for a,b in zip(digest,SDAT_KEY)),
 "EDAT_KEY_0": EDAT_KEY_0,
 "EDAT_KEY_1": EDAT_KEY_1,
}
iv_candidates = {"zeros":b"\x00"*16, "digest":digest, "title":title_hash, "devhash":dev_hash}

found=False
for ckn,ck in crypt_candidates.items():
    # per-block key 유도 방식들
    pbk_variants = {
        "ecbENC(ck,bk)": ecb_enc(ck, block_key),
        "ecbDEC(ck,bk)": ecb_dec(ck, block_key),
        "ck_direct":     ck,
    }
    for pkn,pbk in pbk_variants.items():
        for ivn,iv in iv_candidates.items():
            try:
                dec = cbc_dec(pbk, iv, blk[:16])
            except Exception:
                continue
            if dec[:4]==b"PSAR":
                print(f"*** HIT: crypt={ckn} perblock={pkn} iv={ivn}  -> {dec.hex(' ')}")
                found=True
            elif dec[:2]==b"PS" or dec[:4]==b"\x50\x53\x41\x52":
                print(f"  근접: crypt={ckn} perblock={pkn} iv={ivn} -> {dec[:8].hex(' ')}")
if not found:
    print("PSAR 조합 없음 — 더 깊은 분석 필요")
