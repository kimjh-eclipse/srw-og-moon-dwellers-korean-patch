#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""고유 원문을 ChatGPT 번역용 배치(TSV)로 분할 + 태그 보존 지침 생성.
포맷: uid<TAB>원문  (uid는 절대 바꾸지 말 것, 태그는 원문 그대로 보존)"""
import os, json, re

SRC="extract/unique_jp.jsonl"
OUT="extract/for_chatgpt"; os.makedirs(OUT, exist_ok=True)
PER=400   # 배치당 문자열 수

rows=[json.loads(l) for l in open(SRC,encoding="utf-8")]
# 태그 패턴(보존 대상)
TAG=re.compile(r'<[^>\n]*>|\]-\d+|\[[^\]\n]*\]')

nb=0
for start in range(0, len(rows), PER):
    chunk=rows[start:start+PER]
    nb+=1
    with open(f"{OUT}/batch_{nb:03d}.tsv","w",encoding="utf-8") as f:
        for r in chunk:
            # 원문 내 개행은 \n 리터럴로 이스케이프(한 줄 유지)
            jp=r['jp'].replace('\\','\\\\').replace('\n','\\n').replace('\t','\\t')
            f.write(f"{r['uid']}\t{jp}\n")

with open(f"{OUT}/README_번역지침.txt","w",encoding="utf-8") as f:
    f.write(f"""OGMD 한국어화 번역 배치 ({nb}개 파일, 고유 원문 {len(rows):,}개, 배치당 {PER}개)

[포맷]  각 줄 =  uid<TAB>원문(일본어)
        uid = 문자열 고유번호. 절대 변경/삭제/재정렬 금지.

[번역 규칙]  ChatGPT에게 그대로 지시하세요:
1. 각 줄의 uid와 TAB 구분자는 그대로 두고, 원문 부분만 한국어로 번역.
2. 다음 제어코드는 위치·철자 그대로 보존 (번역·삭제·공백변경 금지):
   - <...> 형태 태그  예) <C>, <W>, <S>, <I>, <H>, <Y>, <C0> 등
   - ]-숫자  예) ]-000, ]-001  (화자/참조 코드)
   - [...] 대괄호 코드
   - \\n \\t (리터럴 이스케이프) 는 그대로 유지
3. 줄 병합·분할 금지. 입력 줄 수 = 출력 줄 수.
4. 고유명사(로봇/파일럿/기술명)는 시리즈 공식 한국어 표기 우선.

[검증]  번역 후 13_validate_tl.py 로 태그 보존/줄수 자동 검사.
""")

print(f"배치 {nb}개 생성 → {OUT}/")
print(f"고유 원문 {len(rows):,}개, 배치당 {PER}개")
