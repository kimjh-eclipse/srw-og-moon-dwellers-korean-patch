#!/usr/bin/env python3
"""이동 배치 안내문 정리 (2026-08-26).

165 가 버튼 아이콘 자리(`（　　：…）`)를 복원한 뒤 인게임에서 확인한 결과:

  - 아이콘 위치는 문자열이 아니라 레코드별로 게임이 정한다.  두 레코드의
    텍스트를 완전히 동일하게 맞춰도 아이콘 뒤 여백이 한 글자분 다르게
    나온다.  문자열 조정으로는 두 화면을 같게 만들 수 없다.
  - 따라서 여기서는 원본 구조에 맞추는 것까지만 한다.

이 스크립트가 하는 일:

  1. 앞부분 문구 통일.  원본은 두 레코드가 모두 `＜移動先を選択して下さい`
     로 동일한데 163 은 `이동 지점을`, 165 는 `이동할 곳을` 로 나눠 옮겼다.
     `이동할 곳을` 로 통일한다.
  2. `持ち替え` 직역인 `바꿔 든다` 를 `놓는다` 와 짝이 되는 `바꾼다` 로.
  3. 콜론 뒤 여백 한 칸.  아이콘이 오른쪽 텍스트에 붙는 것을 줄인다.

남은 제약은 두 화면 사이 한 글자분 여백 차이다.  아이콘 좌표 계산을
찾아야 해결되므로 다음 버전 과제로 넘긴다.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from psarc import PSARC
from sdat import decrypt_stream

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "General2d_icons_ko_20260826.psarc.sdat"
OUTPUT = BUILD / "General2d_prompts_ko_20260826.psarc.sdat"
WTD_MAIN_PATH = "/Dat/Window/WindowToolData/windowdataMain.wtd"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_probe", "163_patch_reports_20260824.py")
replace_field = PREV.replace_field
finish = PREV.finish
WTD_MAIN = PREV.WTD_MAIN

# 측정 결과: 아이콘은 콜론 자리에 그려지고 폭이 한 칸보다 넓다.
# 콜론 뒤에 여백을 하나 넣어 오른쪽 텍스트와 떨어뜨린다.
# 문구도 `持ち替え` 직역인 `바꿔 든다` 대신 `놓는다` 와 짝이 되는 `바꾼다` 로.
JOBS = [
    ("＜이동 지점을 선택하세요（　　：놓는다）＞",
     "＜이동할 곳을 선택하세요（　　：　놓는다）＞", "놓는다 앞부분 통일"),
    ("＜이동할 곳을 선택하세요（　　：바꿔 든다）＞",
     "＜이동할 곳을 선택하세요（　　：　바꾼다）＞", "바꾼다 앞부분 통일"),
]


def main() -> None:
    plain = BUILD / "_prompts_general_source.psarc"
    out_plain = BUILD / (plain.stem + "_out.psarc")
    try:
        with SOURCE.open("rb") as stream, plain.open("wb") as target:
            logical_size, _ = decrypt_stream(stream, 0, target)
        archive = PSARC(str(plain))
        try:
            if archive.manifest()[WTD_MAIN - 1] != WTD_MAIN_PATH:
                raise AssertionError("windowdataMain 식별 변화")
            data = bytearray(archive.read_entry(WTD_MAIN))
            changes = []
            for old_text, new_text, label in JOBS:
                changes.extend(
                    replace_field(data, old_text, new_text, label, expect=1))
            result = finish(SOURCE, OUTPUT, plain, {WTD_MAIN: bytes(data)},
                            logical_size, "General2d.psarc.sdat.orig",
                            fixed_spans=False)
        finally:
            archive.f.close()
        for change in changes:
            print(f"  {change['label']}: 0x{change['offset']:X} "
                  f"{change['before_bytes']}B -> {change['after_bytes']}B "
                  f"(필드 {change['field']}B)")
        print(f"sha256={result['sha256']}")
    finally:
        for temporary in (plain, out_plain):
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                print(f"임시 파일 제거 실패: {temporary.name} ({error})")


if __name__ == "__main__":
    main()
