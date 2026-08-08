#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""범용 UTF-8 텍스트 추출기.
게임 파일에서 일본어(가나/한자/전각) 포함 UTF-8 문자열을 재삽입 좌표와 함께 추출.
반환: [{'off':바이트오프셋, 'blen':바이트길이, 'text':원문}, ...]
"""
def is_jp(cp):
    return (0x3040<=cp<=0x30FF or   # 히라가나/가타카나
            0x4E00<=cp<=0x9FFF or   # 한자
            0x3400<=cp<=0x4DBF or   # 한자 확장A
            0xFF00<=cp<=0xFFEF or   # 전각 영숫자/기호
            0x2160<=cp<=0x2183 or   # 로마숫자
            0x25A0<=cp<=0x26FF)     # 기호(전투/UI)

def extract(buf):
    res=[]; i=0; n=len(buf)
    while i < n:
        b=buf[i]
        # UTF-8 텍스트 런 시작: 인쇄가능 ASCII 또는 멀티바이트 선두
        if b==0x00 or (b<0x20 and b not in (0x09,0x0a)):
            i+=1; continue
        start=i; chars=[]; ok=True
        while i < n:
            b=buf[i]
            if b==0x00: break
            if b<0x80:
                if b<0x20 and b not in (0x09,0x0a):
                    break
                chars.append(b); i+=1
            elif 0xC2<=b<=0xDF and i+1<n and 0x80<=buf[i+1]<=0xBF:
                cp=((b&0x1F)<<6)|(buf[i+1]&0x3F); chars.append(cp); i+=2
            elif 0xE0<=b<=0xEF and i+2<n and 0x80<=buf[i+1]<=0xBF and 0x80<=buf[i+2]<=0xBF:
                cp=((b&0x0F)<<12)|((buf[i+1]&0x3F)<<6)|(buf[i+2]&0x3F)
                # Reject overlong encodings and UTF-16 surrogate code points.
                if cp < 0x800 or 0xD800 <= cp <= 0xDFFF:
                    break
                chars.append(cp); i+=3
            elif 0xF0<=b<=0xF4 and i+3<n and all(0x80<=buf[i+j]<=0xBF for j in(1,2,3)):
                cp=((b&0x07)<<18)|((buf[i+1]&0x3F)<<12)|((buf[i+2]&0x3F)<<6)|(buf[i+3]&0x3F)
                if cp < 0x10000 or cp > 0x10FFFF:
                    break
                chars.append(cp); i+=4
            else:
                break
        blen=i-start
        if chars and any(is_jp(c) for c in chars):
            try:
                text=''.join(chr(c) for c in chars)
                res.append({'off':start,'blen':blen,'text':text})
            except ValueError:
                pass
        if i == start:
            i += 1                      # 소비 못한 단독바이트 → 강제 전진(무한루프 방지)
        elif i < n and buf[i]==0x00:
            i += 1
    return res
