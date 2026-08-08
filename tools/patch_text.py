#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""텍스트 재삽입 최상위 파이프라인.
translations = {원문(일본어): 번역문(한국어)} 딕셔너리.
PSARC 내 FIXH/DOFS 텍스트 컨테이너를 자동 탐지 → 매칭 문자열 교체 → 가변 PSARC 재빌드 → SDAT 재암호화.
"""
import struct, json, sys, io
from psarc import PSARC
from dat_rebuild import DatFile
from bmd_rebuild import BmdFile
from scr_rebuild import ScrFile
from common_rebuild import CsbFile
import psarc_write, sdat_encode

def _match(texts, translations):
    return {j:translations[t] for j,t in enumerate(texts) if t in translations and translations[t]!=t}

def patch_psarc(psarc_path, translations, out_psarc, verbose=True):
    """4종 컨테이너 자동 라우팅:
    .dat(FIXH/DOFS, 임의길이) / scr*.bin(LOGO, 제자리) / .bmd(배틀, 제자리) / .csb(COMMON, 제자리)."""
    p=PSARC(psarc_path); names=p.manifest()
    modified={}; n_str=0; n_file=0; n_trunc=0
    for k,name in enumerate(names):
        ei=k+1; low=name.lower()
        try: data=p.read_entry(ei)
        except Exception: continue
        # 1) FIXH/DOFS .dat (임의길이 재삽입)
        try:
            df=DatFile(data); tr=_match(df.texts(), translations)
            if tr:
                modified[ei]=df.rebuild(tr); n_file+=1; n_str+=len(tr)
                if verbose: print(f'  [dat {name}] {len(tr)}개')
            continue
        except Exception: pass
        # 2) 제자리 교체 컨테이너 (scr/bmd/csb)
        handler=None
        if 'scr' in low and low.endswith('.bin'): handler=ScrFile
        elif low.endswith('.bmd'): handler=BmdFile
        elif low.endswith('.csb'): handler=CsbFile
        if handler:
            try:
                hf=handler(data); tr=_match(hf.texts(), translations)
                if tr:
                    out,trunc=hf.replace(tr); modified[ei]=out
                    n_file+=1; n_str+=len(tr); n_trunc+=trunc
                    if verbose: print(f'  [{handler.__name__} {name}] {len(tr)}개'+(f' (잘림 {trunc})' if trunc else ''))
            except Exception: pass
    if verbose: print(f'교체: 파일 {n_file}개, 문자열 {n_str}개'+(f', 잘림 {n_trunc}' if n_trunc else ''))
    psarc_write.rebuild_var(psarc_path, modified, out_psarc)
    return n_file, n_str

def patch_to_sdat(psarc_path, translations, npd_header, out_sdat, tmp_psarc=None):
    tmp_psarc=tmp_psarc or out_sdat+'.psarc.tmp'
    patch_psarc(psarc_path, translations, tmp_psarc)
    sdat_encode.encode(tmp_psarc, npd_header, out_sdat)
    return out_sdat

def deploy(new_sdat, dest_sdat, keep_size=True):
    """dev_hdd0의 대상 .sdat를 교체. 원본은 .orig 백업(최초 1회), mtime을 원본과 동일하게 설정
    (게임 무결성 검사가 파일 수정시각을 확인함 — 코덱스 발견)."""
    import os, shutil
    orig=dest_sdat+'.orig'
    if not os.path.exists(orig): shutil.copy2(dest_sdat, orig)     # 최초 원본 보존(mtime 포함)
    # keep_size: 원본과 정확히 같은 크기로 끝을 0패딩(게임 크기검사 대비)
    data=open(new_sdat,'rb').read()
    osz=os.path.getsize(orig)
    if keep_size and len(data)<osz: data=data+b'\x00'*(osz-len(data))
    open(dest_sdat,'wb').write(data)
    st=os.stat(orig); os.utime(dest_sdat, (st.st_atime, st.st_mtime))  # 원본 mtime 복원
    return dest_sdat

if __name__=='__main__':
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
    # 사용: python patch_text.py <psarc> <translations.json> <out_psarc>
    psarc=sys.argv[1]; trj=sys.argv[2]; outp=sys.argv[3]
    tr=json.load(open(trj,encoding='utf-8'))
    patch_psarc(psarc, tr, outp)
    print('완료:', outp)
