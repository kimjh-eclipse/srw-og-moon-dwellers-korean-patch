#!/usr/bin/env python3
"""엔딩 전환 키 `エンディング` 복원 (2026-09-06).

증상: 한글 패치로 최종화 클리어 후 엔딩 스태프롤이 나오지 않고 검은 화면에서 멈춤 (하유하우님 제보).
원인: `/Dat/logic/scr00047.bin` 의 장면 키 표(`[ＳＤ２]-006`, `[ＳＤ２]-007`, `エンディング`, `[３]-000`, ...)
      안에 있는 `エンディング` 을 27 번역기가 대사로 보고 `엔딩` 으로 바꿨다. 엔진은 이 값을 문자열 일치로
      찾아 엔딩 장면으로 넘어가므로, 못 찾으면 그 자리에서 멈춘다.
      같은 부류의 `ゲームオーバー`(패배 전환 키)는 예전에 같은 이유로 고장났고 68 이 수리했다(27 에 제외 규칙 존재).
      `エンディング` 은 그 제외 목록에 빠져 있었고, 아무도 엔딩까지 가지 않아 이번에 드러났다.
      68 과 동일한 방식: 해당 슬롯만 원문으로 제자리 복원, 아카이브 배치 무변경.

대상: /Dat/logic/scr00047.bin (e83) 0x1D872, /Dat/logic/old_20151105/scr00047.bin (e161) 0x1AE05
      (구백업 디렉터리는 미사용 추정이나 함께 복원)

분기 실험으로 확정한 근거 (ending_crash_investigation/ENDING_CRASH_FINDINGS_20260906.md):
  소매판 밑바탕 + 47화 스크립트만 소매판 → 통과. 나머지 한글 266개 무죄.

재발 방지: 27_build_logic_translation.py 의 SCENE_TRANSITION_KEYS 에 エンディング·タイトル 추가.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader, decrypt_stream

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
SOURCE = BUILD / "Logic_names_ko_20260825.psarc.sdat"
OUTPUT = BUILD / "Logic_ending_key_ko_20260906.psarc.sdat"
REPORT = BUILD / "ending_key_20260906_report.json"
KEY = "エンディング".encode("utf-8")
NUL = b"\x00"
TARGETS = ("/Dat/logic/scr00047.bin", "/Dat/logic/old_20151105/scr00047.bin")


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_endkey", "163_patch_reports_20260824.py")
finish = PREV.finish


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    with RETAIL.open("rb") as rs, SOURCE.open("rb") as ss:
        R, K = PSARC(SDATReader(rs, 0)), PSARC(SDATReader(ss, 0))
        manifest = R.manifest()
        modified: dict[int, bytes] = {}
        restored = []
        for path in TARGETS:
            entry = manifest.index(path) + 1
            retail, current = R.read_entry(entry), bytearray(K.read_entry(entry))
            pos, hits = 0, 0
            for piece in retail.split(NUL):
                if piece == KEY:
                    if current[pos:pos + len(piece)] == piece:
                        pass  # 이미 원문
                    else:
                        before = current[pos:pos + len(piece)].split(NUL)[0]
                        current[pos:pos + len(piece)] = piece
                        restored.append({"path": path, "entry": entry, "offset": hex(pos),
                                         "before": before.decode("utf-8", "replace")})
                    hits += 1
                pos += len(piece) + 1
            if hits != 1:
                raise AssertionError(f"{path}: 키 슬롯 {hits}개 (1개 기대)")
            if current[pos - 1:pos] not in (b"", NUL):
                pass
            modified[entry] = bytes(current)
    if len(restored) != 2:
        raise AssertionError(f"복원 슬롯 {len(restored)}개 (2개 기대): {restored}")

    plain = BUILD / "_endkey_logic_source.psarc"
    out_plain = BUILD / (plain.stem + "_out.psarc")
    try:
        with SOURCE.open("rb") as stream, plain.open("wb") as target:
            logical_size, _ = decrypt_stream(stream, 0, target)
        result = finish(SOURCE, OUTPUT, plain, modified, logical_size,
                        "Logic.psarc.sdat.orig", fixed_spans=True)
    finally:
        for temporary in (plain, out_plain):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    # 복원 외 모든 엔트리는 SOURCE 와 동일해야 한다
    with OUTPUT.open("rb") as os_, SOURCE.open("rb") as ss:
        O, K = PSARC(SDATReader(os_, 0)), PSARC(SDATReader(ss, 0))
        for e in range(1, O.n):
            want = modified.get(e) or K.read_entry(e)
            if O.read_entry(e) != want:
                raise AssertionError(f"재읽기 불일치 entry {e}")
    result["restored"] = restored
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in restored:
        print(f"  {r['path']} e{r['entry']} {r['offset']}: {r['before']!r} -> エンディング")
    print("pack:", result["pack"])
    print("sha256=", result["sha256"])


if __name__ == "__main__":
    main()
