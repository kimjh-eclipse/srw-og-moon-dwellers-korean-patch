#!/usr/bin/env python3
"""저장소 클론을 v20260912 로 갱신 (커밋·푸시는 하지 않음). v20260910 기준에서 올린다."""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
OLD_VER, NEW_VER = "v20260910", "v20260912"
PKG = ROOT / f"release_combined_20260912/OGMD_KR_{NEW_VER}"
ZIP = ROOT / f"release_combined_20260912/OGMD_KR_{NEW_VER}.zip"
OLD_ZIP_SIZE, OLD_ZIP_SHA = "105,302,382", "CB5225069E63FF3E291DCDF2A334822020FCBFD7A068D256EDEFCBAF799E7FCD"
OLD_XDELTA_TOTAL = "52,202,261"
OLD_PATCH_COUNT = "xdelta 패치 4개"
# 이름: (새 해시, 옛 해시)
HASHES = {
    "Logic": ("A2446B21BB01FE32375BC7F337BCDA0E8C2B76083E8681C05ED4B7F50F6F0E28",
              "8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C"),
    "Battle": ("E7F07D0CED655852CEFD144679829ED3EAEFFF6C06A232D861E1514ACADA66B3",
               "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E"),
}

DOCS_ENTRY = """------------------------------------------------------------------------
v20260912  (2026-09-12)
------------------------------------------------------------------------

[전투 대사 표시 복구]
- 전투 중 일부 대사가 빈 줄로 나오거나, 첫 글자에 엉뚱한 글자가 붙어
  「흙할 수 없어!」처럼 보이던 문제를 고쳤습니다.
- 원인은 대사 파일(BMD)의 문자열 참조였습니다. 번역을 넣는 과정에서
  문자열이 놓인 자리와 게임이 읽으러 가는 자리가 어긋났습니다.
  대사 내용 자체는 멀쩡했지만 게임이 다른 곳을 읽고 있었습니다.
- 기존 코드는 문자열 영역의 시작점을 「긴 문자열이 처음 나오는 곳」으로
  추측했고, 263개 파일 중 61개에서 1~2바이트 앞을 시작점으로 잡았습니다.
  참조를 고칠 때도 접두부를 4바이트씩 훑어 값이 같으면 바꾸는 방식이라
  정렬이 어긋난 참조는 놓치고 포인터가 아닌 값까지 덮어썼습니다.
- 원본 헤더의 구조(group/event/line 수)로 문자열 영역과 실제 포인터
  자리를 계산해 참조 20,553곳을 바로잡았습니다. 그중 6,859곳은 빈 영역이나
  파일 밖을 가리키고 있었습니다.

[가이던스 한글화]
- 타이틀 화면과 인터미션의 가이던스 15쪽을 한글로 옮겼습니다.
  쪽 제목 15개(2og_GuidanceSummary.csb)와 본문 이미지 15장입니다.
- 본문은 텍스트가 아니라 967x392 무압축 32비트 이미지에 글자가 구워진
  형태였습니다. 원본에서 글자만 걷어내고 같은 좌표에 한글을 다시 그렸습니다.
- 스크린샷, 유닛 그림, 연필·느낌표 아이콘, ALL·MAP 무기 배지,
  START·L1·R1·SELECT 버튼 그림은 원본 픽셀을 보존했습니다.
  한글이 짧아져 빈 자리가 생기는 3곳은 배지를 글자 뒤로 당겨 붙였습니다.
- DDS 헤더와 파일 크기는 변하지 않았습니다.

[검증]
- 전투 대사 참조 66,838개 전수 대조: sentinel 2개를 뺀 66,836개가 전부
  일본판 원본과 같은 번호의 대사를 가리킵니다. 어긋남 0, 무효 참조 0
- 번역 문자열 40,639개 보존, 미번역 문자열 수 변화 없음
- 가이던스 이미지 15장 헤더·크기 불변, 해당 항목 외 변화 없음
- xdelta 6개를 일본판 원본에 역적용해 결과 SHA-256 6/6 일치
- 일본판 원본 ISO 사본으로 빠른 패처 6/6 패치, 복구 후 원본 해시 일치
- ZIP 재추출 후 수록 파일 해시 전수 일치

[알려진 제약]
- 아카이브 재생 중단 확인창의 「再生を中止します。」「よろしいですか？」
  두 줄은 게임 데이터가 아니라 실행 파일 안에 있습니다. 위치는 확인했으나
  고치려면 실행 파일을 다시 서명해야 하고 ISO 구조가 달라집니다.
  확인창 한 줄 때문에 부팅 경로를 건드리지 않기로 했습니다.

"""

# v20260910 문서의 잘못된 설명을 바로잡는다(당시에는 못 찾은 것으로 적혀 있었다).
OLD_QUESTION = """- 아카이브 재생 중단 확인창의 「再生を中止します。」「よろしいですか？」
  두 줄은 PSARC 다섯 개를 여러 인코딩으로 전수 검색했지만 찾지 못했습니다.
  실행 파일 쪽으로 보이며 파일 교체 방식으로는 손댈 수 없습니다."""
NEW_QUESTION = """- 아카이브 재생 중단 확인창의 「再生を中止します。」「よろしいですか？」
  두 줄은 PSARC 다섯 개에서 찾지 못했습니다.
  (v20260912에서 실행 파일 안에 있음을 확인했습니다.)"""

TOOLS = ("258_repair_battle_references.py", "260_measure_inplace_fit.py",
         "262_write_iso_slots.py", "263_verify_battle_refs_full.py",
         "264_build_v20260912_release.py", "265_translate_guidance_titles.py",
         "266_pack_guidance_images.py", "267_update_repo_v20260912.py",
         "243_check_iso_slots.py", "bmd_rebuild.py",
         "guidance_render.py", "guidance_pages.py")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def rewrite(path: Path, pairs: list[tuple[str, str]], required: bool = True) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            if required:
                raise AssertionError(f"{path.name}: 앵커 없음 -> {old[:50]}")
            continue
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def main() -> None:
    new_zip_sha, new_zip_size = digest(ZIP), f"{ZIP.stat().st_size:,}"
    patches = sorted((PKG / "patches").iterdir())
    xdelta_total = sum(p.stat().st_size for p in patches)
    common = [(OLD_VER, NEW_VER), (OLD_ZIP_SIZE, new_zip_size), (OLD_ZIP_SHA, new_zip_sha)]
    swaps = [(old, new) for new, old in HASHES.values()]

    rewrite(REPO / "README.md", common + swaps)
    rewrite(REPO / "docs/home.md",
            common + [(OLD_XDELTA_TOTAL, f"{xdelta_total:,}"),
                      (OLD_PATCH_COUNT, f"xdelta 패치 {len(patches)}개")])
    rewrite(REPO / "docs/install.md", common + swaps)

    for name in ("CHANGELOG.txt", "README_사용법.txt", "install_xdelta.ps1", "verify_xdelta.ps1",
                 "restore_xdelta_backup.ps1", "xdelta.exe"):
        shutil.copy2(PKG / name, REPO / name)
    for patch in patches:
        shutil.copy2(patch, REPO / "patches" / patch.name)

    changelog = REPO / "docs/changelog.md"
    text = changelog.read_text(encoding="utf-8-sig")
    marker = "------------------------------------------------------------------------\nv20260910  ("
    if marker not in text or ("\n" + NEW_VER + "  (") in text:
        raise AssertionError("docs/changelog.md 삽입 지점 확인 필요")
    text = text.replace(marker, DOCS_ENTRY + marker, 1)
    if OLD_QUESTION in text:
        text = text.replace(OLD_QUESTION, NEW_QUESTION, 1)
    else:
        print("주의: v20260910 의 QUESTION 설명 문단을 찾지 못해 그대로 두었습니다")
    changelog.write_text(text, encoding="utf-8")

    for name in TOOLS:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, REPO / "tools" / name)
        else:
            print("건너뜀(없음):", name)
    shutil.copy2(ROOT / "iso_quickpatch/OGMDIsoQuickPatch.cs", REPO / "tools/iso_quickpatch/OGMDIsoQuickPatch.cs")
    shutil.copy2(ROOT / "iso_quickpatch/build_range_pack.py", REPO / "tools/iso_quickpatch/build_range_pack.py")

    listed = [line.split("  ", 1)[1] for line in
              (REPO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    listed.sort()
    lines = []
    for rel in listed:
        src = PKG / rel if rel == "OGMD_ISO_QuickPatch.exe" else REPO / rel
        lines.append(f"{digest(src)}  {rel}")
    (REPO / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for rel in ("README.md", "docs/home.md", "docs/install.md", "README_사용법.txt",
                "install_xdelta.ps1", "CHANGELOG.txt", "docs/changelog.md"):
        text = (REPO / rel).read_text(encoding="utf-8-sig")
        for stale in [OLD_ZIP_SHA] + [old for _, old in HASHES.values()]:
            assert stale not in text, (rel, stale[:8])
    print(f"repo 갱신: zip {new_zip_size}B {new_zip_sha[:8]} / "
          f"xdelta 합계 {xdelta_total:,} / 패치 {len(patches)}개")


if __name__ == "__main__":
    main()
