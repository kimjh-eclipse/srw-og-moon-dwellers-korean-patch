#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LOGIC PSARC 안 scr*.bin(매직 "LOGO") 스크립트 텍스트 재삽입기.

포맷 요약(리버싱 결과):
  - 헤더: 0x00 "LOGO" 매직, 0x04 파일길이(u32 BE), 0x08~0x13 예약(0),
    0x14부터 (섹션오프셋 u32 BE, 카운트 u32 BE) 쌍의 섹션 테이블.
    테이블은 오프셋이 0xffffffff 인 엔트리에서 종료되고, ff 패딩 뒤 파일길이가 한 번 더 나온다.
    (카운트 필드는 바이트 크기가 아니라 엔트리 수. 섹션 데이터는 오프셋 오름차순이 아니라
     서로 인터리브/중복될 수 있음.)
  - 문자열: 파일 뒤쪽 여러 하위 풀에 널종료 UTF-8 로 저장. 화자라벨 "[ＤＭ]-이름",
    "[１]-003" 류 코드, 미션 목표/메뉴 문자열 등. 인라인 제어코드(<...>, ]-, [...])는
    문자열 바이트의 일부로 그대로 보존된다.
  - **문자열 참조 방식**: 스크립트 바이트코드는 문자열을 (섹션,인덱스)로 참조하며
    문자열의 '바이트 오프셋'을 직접 저장하지 않는다. 실측 검증: scr00042/00000/00045
    에서 추출된 240/97/189개 텍스트의 파일내 오프셋을 BE/LE u16·u24·u32 전폭으로
    전수 검색 → 참조 0건. 즉 문자열을 '제자리(span 유지)'로 덮어써도 어떤 포인터/인덱스도
    깨지지 않는다.

재삽입 방식 = **제자리 길이제한 교체(bmd_rebuild.py 방식)**.
  이유:
   (1) 문자열은 raw 오프셋으로 참조되지 않으므로 제자리 덮어쓰기는 바이트코드에 무해(입증됨).
   (2) 반대로 '임의 길이(오프셋 재계산)'는 불가: 헤더 밖 바이트코드가 뒤쪽 데이터 영역을
       가리키는 절대 포인터(예: scr00042 @0x161f9->0x16b00, @0x16799->0x17700)를 갖고 있어
       풀을 키우면 이들이 어긋난다. 진짜 포인터와 우연한 바이트값 구분이 불가능해 위험.
   (3) JP→KR 은 UTF-8 상 CJK/전각이 3바이트로 동일 → 한국어가 원문 바이트 이내로 들어가는
       경우가 대부분이라 제자리 교체로 실사용 커버.
  한계: 번역문(+널)이 원문 텍스트런 바이트길이를 초과하면 문자 경계에서 잘림(경고).

문자열 목록/인덱스는 프로젝트 표준 추출기 textextract.extract() 와 동일하게 산출한다.
(extract_all/master_all.jsonl 의 off/blen/text 와 인덱스가 일치 → 번역배치 재삽입에 그대로 사용)
"""

from textextract import extract


class ScrFile:
    MAGIC = b'LOGO'

    def __init__(self, data):
        self.d = bytearray(data)
        if bytes(self.d[:4]) != self.MAGIC:
            raise ValueError('LOGO 매직 아님: %r' % bytes(self.d[:4]))
        # 프로젝트 표준 추출기로 번역 대상 문자열을 결정(인덱스=추출 순서)
        self.records = extract(bytes(self.d))   # [{'off','blen','text'}, ...]
        # 각 레코드가 널 종료되는지 확인(제자리 span 계산의 전제)
        N = len(self.d)
        for r in self.records:
            o, bl = r['off'], r['blen']
            r['span'] = bl + 1 if (o + bl < N and self.d[o + bl] == 0) else bl

    def texts(self):
        """번역 대상 문자열 리스트(추출 순서 = 재삽입 인덱스)."""
        return [r['text'] for r in self.records]

    def replace(self, index_to_ko, warn=None):
        """제자리 길이제한 교체. index_to_ko: {인덱스:번역문}.
        반환: (bytes, 잘린수). 파일 크기·모든 오프셋/포인터 불변."""
        truncated = 0
        for i, ko in index_to_ko.items():
            r = self.records[i]
            off, span = r['off'], r['span']
            kb = ko.encode('utf-8')
            # 널 종료 1바이트 확보(span에 원본 널 포함) — kb+널이 span 이내여야 함
            if len(kb) + 1 > span:
                s = ko
                while len(s.encode('utf-8')) + 1 > span and s:
                    s = s[:-1]
                if warn:
                    warn(i, ko, s)
                kb = s.encode('utf-8')
                truncated += 1
            block = kb + b'\x00' * (span - len(kb))   # 원본 span으로 널 패딩(오프셋 유지)
            self.d[off:off + span] = block
        return bytes(self.d), truncated

    def rebuild(self, index_to_ko=None, warn=None):
        """dat/bmd 핸들러와 시그니처 통일용 래퍼. 반환: bytes."""
        out, _ = self.replace(index_to_ko or {}, warn=warn)
        return out


if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    from psarc import PSARC

    p = PSARC('LOGIC.psarc')
    names = p.manifest()
    idx = {n: i + 1 for i, n in enumerate(names)}
    scr = [n for n in names
           if n.startswith('/Dat/logic/scr') and n.endswith('.bin') and 'old_' not in n]

    # 1) 대표 파일 구조/샘플
    d0 = p.read_entry(idx['/Dat/logic/scr00042.bin'])
    sf0 = ScrFile(d0)
    print('=== scr00042.bin ===')
    print('추출 문자열 수:', len(sf0.records))
    print('샘플:', [t[:32] for t in sf0.texts()[40:46]])

    # 2) 무수정 왕복 + 자기자신 재인코딩 왕복(바이트동일) — 다수 파일
    print('\n=== 왕복 바이트동일 검증 (%d개 파일) ===' % len(scr[:12]))
    all_ok = True
    total_strings = 0
    for n in scr[:12]:
        d = p.read_entry(idx[n])
        sf = ScrFile(d)
        total_strings += len(sf.records)
        # (a) 무수정
        out_noop = sf.rebuild()
        ok_noop = out_noop == bytes(d)
        # (b) 모든 문자열을 자기 자신으로 재인코딩(encode/pad 로직 검증)
        sf2 = ScrFile(d)
        selfmap = {i: t for i, t in enumerate(sf2.texts())}
        out_self, tr = sf2.replace(selfmap)
        ok_self = out_self == bytes(d)
        all_ok &= ok_noop and ok_self
        print('  %-28s strings=%3d  noop=%s  self-reencode=%s (trunc=%d)'
              % (n.split('/')[-1], len(sf.records), ok_noop, ok_self, tr))
    print('전체 왕복 바이트동일:', all_ok)

    # 3) 한글 합성 교체 테스트(제자리)
    print('\n=== 한글 교체 테스트 (scr00042) ===')
    sf3 = ScrFile(d0)
    orig = sf3.texts()
    # 원문 바이트 이내로 들어가는 짧은 한글로 앞 3개 교체
    warns = []
    kmap = {40: '테스트한글', 41: '가나다', 42: '조종사'}
    out3, tr = sf3.replace(kmap, warn=lambda i, o, s: warns.append((i, o, s)))
    print('크기 동일:', len(out3) == len(d0), '| 잘림:', tr)
    # 재삽입 검증: 원본 인덱스의 off에서 raw 바이트를 널까지 읽어 확인
    # (extract()는 한글 미검출이라 재추출로는 검증 불가 → raw 바이트로 확인)
    for i, ko in kmap.items():
        off = sf3.records[i]['off']
        end = out3.index(b'\x00', off)
        got = bytes(out3[off:end]).decode('utf-8')
        print('  idx%d  %r -> %r  OK=%s' % (i, orig[i][:20], got, got == ko))
    # 교체 안 한 위치는 원문 보존 확인(raw)
    off0 = sf3.records[0]['off']
    got0 = bytes(out3[off0:out3.index(b'\x00', off0)]).decode('utf-8')
    print('  비교체 idx0 보존:', got0 == orig[0])
    # 원문보다 긴 한글 → 잘림 경고 동작 확인
    sf4 = ScrFile(d0)
    w = []
    _, tr2 = sf4.replace({44: '아주아주아주아주아주아주아주아주긴번역문장입니다'},
                         warn=lambda i, o, s: w.append((o, s)))
    print('  긴문장 잘림 발생:', tr2 == 1, '| 잘린결과:', w[0][1] if w else None)

    # 4) 전체 165개 파일 파서 견고성(파싱 예외 없이 통과)
    print('\n=== 전체 파서 견고성 (%d개 scr) ===' % len(scr))
    fail = 0
    grand = 0
    for n in scr:
        try:
            sf = ScrFile(p.read_entry(idx[n]))
            grand += len(sf.records)
            # 무수정 왕복 확인
            if sf.rebuild() != bytes(p.read_entry(idx[n])):
                print('  !! 왕복불일치', n)
                fail += 1
        except Exception as e:
            print('  !! 파싱실패', n, e)
            fail += 1
    print('실패 %d/%d, 파싱 총 문자열 %d개' % (fail, len(scr), grand))
