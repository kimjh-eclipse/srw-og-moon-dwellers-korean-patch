#!/usr/bin/env python3
"""저장소 클론을 v20260910 으로 갱신 (커밋·푸시는 하지 않음). v20260909c 기준에서 올린다."""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
OLD_VER, NEW_VER = "v20260909c", "v20260910"
PKG = ROOT / f"release_combined_20260910/OGMD_KR_{NEW_VER}"
ZIP = ROOT / f"release_combined_20260910/OGMD_KR_{NEW_VER}.zip"
OLD_ZIP_SIZE, OLD_ZIP_SHA = "104,868,548", "465E7F7BE3759CEBBE0E7246BFD042F96E1EFA1AB36AF5FA199C6FBDC49C574F"
OLD_XDELTA_TOTAL = "51,986,590"
HASHES = {
    "Common": ("52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373",
               "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2"),
    "General2d": ("6BCB01A3D66FE668ECA2BF5167D9552DBD1D6F6DB1B0A24083FD40DA2D14AD47",
                  "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473"),
    "Logic": ("8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C",
              "6A192C98E1B2845952D51B52A4CFB44CAA79C5D26F67B42C3BADFC895909D7FE"),
}

DOCS_ENTRY = """------------------------------------------------------------------------
v20260910  (2026-09-10)
------------------------------------------------------------------------

[아카이브 5편 전체 한글화]
- 타이틀 화면의 아카이브에서 볼 수 있는 이전 작품 줄거리를 전부 한글로
  옮겼습니다. 문단 246개입니다.
  OG 1 34개, OG 2 40개, OG 외전 36개, 다크 프리즌 26개, 제2차 OG 110개
- 아카이브 메뉴와 REPORT 안내문, 재생 중단 확인 문구도 함께 손봤습니다.
- 문단마다 줄 수와 한 줄 길이를 화면 폭에 맞춰 다시 끊었습니다.
  최대 6줄, 한 줄 42자입니다.

[게임 목록 제목과 아이콘]
- RPCS3 게임 목록에 「슈퍼로봇대전 OG 문 드웰러즈」로 표시됩니다.
- 게임 목록 아이콘도 한국어판으로 바꿨습니다.
- 빠른 패처와 xdelta 방식 모두 PS3_GAME\\PARAM.SFO 와 PS3_GAME\\ICON0.PNG
  두 파일을 함께 처리합니다. 타이틀 ID와 버전 항목은 건드리지 않습니다.
- 게임 데이터 사본처럼 원본 해시가 다른 경우에는 그 파일만 건너뜁니다.

[대사 가독성]
- 시나리오 대사와 사전 항목의 줄 끊김을 다시 정리했습니다.
  단어 중간에서 줄이 바뀌던 곳, 기체·인물 사전의 링크 표기 앞뒤 공백,
  강룡전대 상층부 대화의 긴 문장을 손봤습니다.

[검증]
- xdelta 6개를 일본판 원본에 역적용해 결과 SHA-256 6/6 일치
- 아카이브 문단 전수 검사: 일본어·한자 잔여 0, 미지원 글자 0, 잘린 문단 0
- 일본판 원본 ISO 사본으로 빠른 패처 6/6 패치, 복구 후 원본 해시 일치
- 폴더형 게임 구성으로 설치·검사·복구 왕복 확인
- ZIP 재추출 후 수록 파일 해시 전수 일치

[알려진 제약]
- 아카이브 재생 중단 확인창의 「再生を中止します。」「よろしいですか？」
  두 줄은 PSARC 다섯 개를 여러 인코딩으로 전수 검색했지만 찾지 못했습니다.
  실행 파일 쪽으로 보이며 파일 교체 방식으로는 손댈 수 없습니다.

"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def rewrite(path: Path, pairs: list[tuple[str, str]]) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: 앵커 없음 -> {old[:50]}")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def main() -> None:
    new_zip_sha, new_zip_size = digest(ZIP), f"{ZIP.stat().st_size:,}"
    xdelta_total = sum(p.stat().st_size for p in (PKG / "patches").iterdir())
    common = [(OLD_VER, NEW_VER), (OLD_ZIP_SIZE, new_zip_size), (OLD_ZIP_SHA, new_zip_sha)]
    swaps = [(old, new) for new, old in HASHES.values()]
    rewrite(REPO / "README.md", common + swaps)
    rewrite(REPO / "docs/home.md", common + [(OLD_XDELTA_TOTAL, f"{xdelta_total:,}")])
    rewrite(REPO / "docs/install.md", common + swaps)

    for name in ("CHANGELOG.txt", "README_사용법.txt", "install_xdelta.ps1", "verify_xdelta.ps1",
                 "restore_xdelta_backup.ps1", "xdelta.exe"):
        shutil.copy2(PKG / name, REPO / name)
    for patch in sorted((PKG / "patches").iterdir()):
        shutil.copy2(patch, REPO / "patches" / patch.name)

    cl = REPO / "docs/changelog.md"
    text = cl.read_text(encoding="utf-8-sig")
    marker = "------------------------------------------------------------------------\nv20260909c  ("
    if marker not in text or ("\n" + NEW_VER + "  (") in text:
        raise AssertionError("docs/changelog.md 삽입 지점 확인 필요")
    cl.write_text(text.replace(marker, DOCS_ENTRY + marker, 1), encoding="utf-8")

    for name in ("236_find_archive_question_strings.py", "237_scan_eboot_for_question.py",
                 "238_extract_retail_title_icon.py", "239_prepare_v20260910_targets.py",
                 "240_extend_range_pack_and_patcher.py", "241_build_v20260910_release.py",
                 "242_extend_install_scripts.py", "243_check_iso_slots.py",
                 "244_update_repo_v20260910.py"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, REPO / "tools" / name)
        else:
            print("건너뜀(없음):", name)
    shutil.copy2(ROOT / "iso_quickpatch/OGMDIsoQuickPatch.cs", REPO / "tools/iso_quickpatch/OGMDIsoQuickPatch.cs")
    shutil.copy2(ROOT / "iso_quickpatch/build_range_pack.py", REPO / "tools/iso_quickpatch/build_range_pack.py")

    # SHA256SUMS: 기존 목록 + 새 패치 파일 두 개
    listed = [line.split("  ", 1)[1] for line in (REPO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    for extra in ("patches/PARAM.SFO.xdelta", "patches/ICON0.PNG.xdelta"):
        if extra not in listed:
            listed.append(extra)
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
    print(f"repo 갱신: zip {new_zip_size}B {new_zip_sha[:8]} / xdelta 합계 {xdelta_total:,} / 패치 {len(list((PKG / 'patches').iterdir()))}개")


if __name__ == "__main__":
    main()
