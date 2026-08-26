#!/usr/bin/env python3
"""2026-08-26 버튼 아이콘 자리 복원 패치.

원본 windowdataMain.wtd 는 버튼 아이콘을 그릴 위치를 전각 공백 2칸(`　　`)
으로 비워 둔다.  한국어 번역이 그 절을 통째로 지우면서 아이콘이 갈 곳을
잃고 본문 글자 위에 겹쳐 그려졌다.

163 이 같은 증상의 「트윈 배치 안내문」 한 건을 이미 고쳤고 인게임에서
정상 표시가 확인됐다.  같은 방식으로 남은 4건을 복원한다.

  0xA2547  ＜移動先を選択して下さい（　　：持ち替え）＞   ← 제보된 화면
  0x9A46B  自動反撃です（　　：手動設定）。
  0x1130AF 台詞送り（＋　　高速）        '음원 전송' 은 오역
  0x1139FF ＋　　台詞スキップ            '문장 스피프' 는 오타

덤으로 0xA2617 은 원본에 아이콘 자리가 없는데도 전각 괄호 `＜＞` 가 반각
`<>` 로 앞에 몰려 있어 원본 구조로 되돌린다.

모든 교체는 필드 폭 안에서 이뤄지며 폭 자체는 변하지 않는다.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from psarc import PSARC
from sdat import decrypt_stream

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
REPORT = BUILD / "button_icon_slots_20260826_report.json"

SOURCE = BUILD / "General2d_reports_ko_20260824.psarc.sdat"
OUTPUT = BUILD / "General2d_icons_ko_20260826.psarc.sdat"
WTD_MAIN_PATH = "/Dat/Window/WindowToolData/windowdataMain.wtd"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_icons", "163_patch_reports_20260824.py")
replace_field = PREV.replace_field
finish = PREV.finish
WTD_MAIN = PREV.WTD_MAIN

# (현재 문구, 새 문구, 설명) — 선행 제어 바이트는 replace_field 가 보존한다.
JOBS = [
    # 제보된 화면. 원본 `（　　：持ち替え）` 복원.  짝이 되는 `置く` 가
    # 이미 `놓는다` 이므로 `持ち替え` 도 평서형 `바꿔 든다` 로 맞춘다.
    ("<> 이동할 곳을 선택하세요.",
     "＜이동할 곳을 선택하세요（　　：바꿔 든다）＞", "이동 배치 안내문"),
    # 원본에 아이콘 자리는 없지만 전각 괄호가 반각으로 앞에 몰려 있었다.
    ("<> 이동하는 위치를 선택하세요",
     "＜이동시킬 위치를 선택하세요＞", "이동 위치 안내문"),
    ("자동 반격입니다",
     "자동 반격입니다（　　：수동 설정）.", "자동 반격 힌트"),
    # 台詞送り 를 '음원 전송' 으로 옮긴 것은 오역이다.
    ("음원 전송:", "대사 넘기기（＋　　고속）", "대사 넘기기"),
    # 台詞スキップ. '스피프' 는 '스킵' 오타.
    ("+ 문장 스피프", "＋　　대사 스킵", "대사 스킵"),
]


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"입력 없음: {SOURCE}")

    plain = BUILD / "_icons_general_source.psarc"
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

        result["changes"] = changes
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        for change in changes:
            print(f"  {change['label']}: 0x{change['offset']:X} "
                  f"{change['before_bytes']}B -> {change['after_bytes']}B "
                  f"(필드 {change['field']}B)")
        print(f"sha256={result['sha256']}")
    finally:
        # 163/164 는 여기서 실패해도 넘어가 임시 파일이 쌓였다. 확실히 지운다.
        for temporary in (plain, out_plain):
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                print(f"임시 파일 제거 실패: {temporary.name} ({error})")


if __name__ == "__main__":
    main()
