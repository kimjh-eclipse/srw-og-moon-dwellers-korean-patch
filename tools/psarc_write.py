#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PSARC 1.4 라이터 — 특정 엔트리만 교체하고 나머지 블록은 원본 압축본을 그대로 복사.
크기 불변 교체(예: 폰트 픽셀만 변경) 시 블록수/block_idx 불변, csize·offset만 재계산."""
import os, struct, sys, zlib
from pathlib import Path
from psarc import PSARC, be

_zopfli_compress = None
if os.environ.get("OGMD_ZOPFLI"):
    sys.path.insert(0, str(Path(__file__).with_name("vendor")))
    from zopfli.zlib import compress as _zopfli_compress


def enable_zopfli():
    """Enable the bundled Zopfli encoder on demand.

    The normal zlib encoder is much faster and remains the first choice.
    Builders can call this only when a size-constrained archive does not fit.
    Zopfli emits an ordinary RFC 1950 zlib stream, so the PSARC reader does not
    need any corresponding decoder change.
    """
    global _zopfli_compress
    if _zopfli_compress is None:
        vendor = str(Path(__file__).with_name("vendor"))
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
        from zopfli.zlib import compress

        _zopfli_compress = compress
    return _zopfli_compress

def be_n(v, n):
    return bytes((v >> (8*(n-1-i))) & 0xff for i in range(n))

def entry_nblocks(p, idx):
    return (p.entries[idx]['orig_size'] + p.block_size - 1)//p.block_size

def block_byte_positions(p):
    """블록 j의 (원본파일 내 시작오프셋, csize) 리스트. 블록은 block_idx 순서로 연속 저장."""
    data_start = p.toc_len
    pos=[]; off=data_start
    for c in p.block_table:
        pos.append((off, c))
        off += c if c!=0 else p.block_size
    return pos

def compress_blocks(data, block_size):
    """data를 block_size 단위로 zlib 압축. 압축이 이득 없으면 raw(csize=0)로 저장.
    반환: (csize리스트, 블록바이트리스트)"""
    csizes=[]; blobs=[]
    for o in range(0, len(data), block_size):
        chunk=data[o:o+block_size]
        # Try the lossless zlib strategies accepted by PSARC and keep the
        # smallest stream.  Tiny size differences matter because the installed
        # archive must remain no larger than the original logical size.
        candidates=[]
        # The retail archives were not consistently produced with zlib's
        # default memLevel.  Dialogue blocks in LOGIC, in particular, become
        # substantially smaller with memLevel=4.  Try the useful combinations
        # and keep the shortest valid stream.
        for mem_level in range(1, 10):
            for strategy in (
                zlib.Z_DEFAULT_STRATEGY,
                zlib.Z_FILTERED,
                zlib.Z_HUFFMAN_ONLY,
                zlib.Z_RLE,
                zlib.Z_FIXED,
            ):
                encoder=zlib.compressobj(
                    level=9,
                    method=zlib.DEFLATED,
                    wbits=zlib.MAX_WBITS,
                    memLevel=mem_level,
                    strategy=strategy,
                )
                candidates.append(encoder.compress(chunk)+encoder.flush())
        if _zopfli_compress is not None:
            candidates.append(
                _zopfli_compress(
                    chunk,
                    numiterations=int(
                        os.environ.get("OGMD_ZOPFLI_ITERATIONS", "5")
                    ),
                )
            )
        comp=min(candidates, key=len)
        if len(comp) < len(chunk):
            csizes.append(len(comp)); blobs.append(comp)
        else:
            csizes.append(0); blobs.append(chunk)   # raw 전체블록(마지막은 partial이라 csize=len)
            if len(chunk)<block_size: csizes[-1]=len(chunk)
    return csizes, blobs

def rebuild(psarc_path, modified: dict, out_path):
    """modified = {entry_idx: new_bytes(같은 orig_size)}. 원본 블록은 verbatim 복사."""
    p=PSARC(psarc_path)
    raw=open(psarc_path,'rb').read()
    pos=block_byte_positions(p)                 # 원본 블록 위치/크기
    # 새 블록테이블 + 블록바이트 (블록 순서대로)
    new_csize=list(p.block_table)
    new_blocks_bytes={}                          # block_j -> bytes (교체된 것만)
    for idx, newdata in modified.items():
        e=p.entries[idx]
        assert len(newdata)==e['orig_size'], f"크기 불일치 {len(newdata)} != {e['orig_size']}"
        nb=entry_nblocks(p, idx); bi=e['block_idx']
        original_data=p.read_entry(idx)
        cs=[None]*nb; blobs=None
        assert len(cs)==nb, f"블록수 변동 {len(cs)}!={nb}"
        for j in range(nb):
            start=j*p.block_size
            new_chunk=newdata[start:start+p.block_size]
            old_chunk=original_data[start:start+p.block_size]
            if new_chunk==old_chunk:
                continue
            block_cs, block_blobs=compress_blocks(new_chunk, p.block_size)
            assert len(block_cs)==1 and len(block_blobs)==1
            new_csize[bi+j]=block_cs[0]
            new_blocks_bytes[bi+j]=block_blobs[0]
    # 블록 바이트 확보 함수: 교체본 or 원본에서 복사
    def block_bytes(j):
        if j in new_blocks_bytes: return new_blocks_bytes[j]
        o,c=pos[j]; n=c if c!=0 else p.block_size
        return raw[o:o+n]
    # 데이터 영역 재조립하며 각 블록의 새 오프셋 기록
    data_start=p.toc_len
    out=bytearray(); off=data_start
    block_new_off=[]
    for j in range(len(new_csize)):
        b=block_bytes(j); block_new_off.append(off); out+=b; off+=len(b)
    # 엔트리 오프셋 재계산 = 그 엔트리 첫 블록의 새 오프셋
    new_entries=[]
    for e in p.entries:
        new_entries.append({**e, 'offset': block_new_off[e['block_idx']]})
    # 헤더/TOC/블록테이블 직렬화
    hdr=raw[0:32]                                # toc_len 등 불변
    toc=bytearray()
    for e in new_entries:
        toc+=e['md5'] + struct.pack('>I',e['block_idx']) + be_n(e['orig_size'],5) + be_n(e['offset'],5)
    bt=bytearray()
    for c in new_csize: bt+=be_n(c, p.bw)
    body=bytes(hdr)+bytes(toc)+bytes(bt)
    assert len(body)==data_start, f"헤더+TOC+BT 길이 {len(body)} != toc_len {data_start}"
    open(out_path,'wb').write(body+bytes(out))
    return len(body)+len(out)

def rebuild_var(psarc_path, modified: dict, out_path):
    """가변크기 교체: 엔트리 크기가 바뀌어도 block_idx/오프셋/블록테이블 전부 재계산.
    변경 엔트리는 재압축, 나머지는 원본 압축블록 verbatim 복사."""
    p=PSARC(psarc_path); raw=open(psarc_path,'rb').read()
    pos=block_byte_positions(p)
    order=sorted(range(p.n), key=lambda i:p.entries[i]['block_idx'])
    # 엔트리별 원본 블록범위 [bi, bend) = block_idx 델타 (정확)
    bstart={}; bend={}
    for k,i in enumerate(order):
        bstart[i]=p.entries[i]['block_idx']
        bend[i]=p.entries[order[k+1]]['block_idx'] if k+1<len(order) else len(p.block_table)
    new_cs=[]; new_blk=[]; ent_new={}
    for i in order:
        e=p.entries[i]; bidx=len(new_cs)
        if i in modified:
            data=modified[i]; cs,blobs=compress_blocks(data, p.block_size); osz=len(data)
        else:
            cs=[]; blobs=[]
            for j in range(bstart[i], bend[i]):
                o,c=pos[j]; n=c if c!=0 else p.block_size
                # Keep unchanged blocks as zero-copy views.  Copying every source
                # block roughly doubles the archive's peak memory footprint.
                cs.append(p.block_table[j]); blobs.append(memoryview(raw)[o:o+n])
            osz=e['orig_size']
        new_cs+=cs; new_blk+=blobs; ent_new[i]=(bidx,osz)
    nblk=len(new_cs); toc_len=32 + p.n*p.ent_size + nblk*p.bw
    offs=[]; off=toc_len
    for b in new_blk: offs.append(off); off+=len(b)
    hdr=bytearray(raw[0:32]); struct.pack_into('>I',hdr,12,toc_len)
    toc=bytearray()
    for i in range(p.n):
        e=p.entries[i]; bidx,osz=ent_new[i]
        eoff=offs[bidx] if bidx<len(offs) else toc_len
        toc+=e['md5']+struct.pack('>I',bidx)+be_n(osz,5)+be_n(eoff,5)
    bt=bytearray()
    for c in new_cs: bt+=be_n(c,p.bw)
    body=bytes(hdr)+bytes(toc)+bytes(bt)
    assert len(body)==toc_len, f'{len(body)}!={toc_len}'
    # Stream the archive instead of constructing one more archive-sized bytes
    # object with ``body + b''.join(new_blk)``.  Large translated archives can
    # otherwise fail here even though all compression work has completed.
    with open(out_path, 'wb') as stream:
        stream.write(body)
        for block in new_blk:
            stream.write(block)
    return toc_len+sum(len(b) for b in new_blk)

if __name__=='__main__':
    import sys
    src=sys.argv[1]; out=sys.argv[2] if len(sys.argv)>2 else src+'.rebuilt'
    n=rebuild(src, {}, out)
    orig=open(src,'rb').read(); new=open(out,'rb').read()
    print(f'재빌드 {out}: {n:,}B, 원본 {len(orig):,}B')
    print('바이트 동일:', orig==new)
    if orig!=new:
        for i in range(min(len(orig),len(new))):
            if orig[i]!=new[i]: print(f'  첫 불일치 @ {i:#x}: orig={orig[i]:#x} new={new[i]:#x}'); break
