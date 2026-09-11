#!/usr/bin/env python3
"""v20260910 배포 패키지 생성.

- v20260909c 패키지를 밑바탕으로 xdelta 6개(PSARC 4 + PARAM.SFO + ICON0.PNG) 재생성
- install/verify/restore 스크립트에 제목·아이콘 처리를 추가 (없거나 해시가 다르면 건너뜀)
- 범위 팩(6개 항목) 기준으로 EXE 재빌드
- SHA256SUMS·ZIP·재추출 대조
"""
from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OLD_VER, NEW_VER = "v20260909c", "v20260910"
OLD_PKG = ROOT / f"release_combined_20260909c/OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260910"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
ORIG = ROOT / "original_backups"
BUILD = ROOT / "korean_build_v3"

PSARC = {
    "Common": (ORIG / "Common.psarc.sdat.orig", BUILD / "Common_archive_ko_20260910.psarc.sdat",
               "99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB",
               "52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373"),
    "General2d": (ORIG / "General2d.psarc.sdat.orig", BUILD / "General2d_archive_ko_20260910.psarc.sdat",
                  "04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667",
                  "6BCB01A3D66FE668ECA2BF5167D9552DBD1D6F6DB1B0A24083FD40DA2D14AD47"),
    "Logic": (ORIG / "Logic.psarc.sdat.orig", BUILD / "Logic_archive_ko_20260910.psarc.sdat",
              "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
              "8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C"),
    "Battle": (ORIG / "Battle.psarc.sdat.orig", BUILD / "Battle_issue6_ko_20260909.psarc.sdat",
               "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
               "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E"),
}
EXTRA = {
    "PARAM.SFO": (ORIG / "PARAM.SFO.orig", BUILD / "PARAM_SFO_ko_20260910.bin",
                  "0A876ACFABB16CEAA017EDD51A700079678AA8E61C0B7AEFE0B59CB19B59FF22",
                  "B7ABDFE7FED52FB9EEEDDE02FBD33475A449C20B4EE6099E59BC025E1F32DE54", 1040),
    "ICON0.PNG": (ORIG / "ICON0.PNG.orig", BUILD / "ICON0_PNG_ko_20260910.bin",
                  "9B2E67DC606CEF3CD269E13DDA425445820A65F034DE4B3BC000435EA0B9B136",
                  "0B038E45343B203DE00D1323247FD5AFFFF3AB61AF35A8206010EA5601948A00", 114574),
}
OLD_TARGETS = {
    "Common": "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2",
    "General2d": "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473",
    "Logic": "6A192C98E1B2845952D51B52A4CFB44CAA79C5D26F67B42C3BADFC895909D7FE",
    "Battle": "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E",
}

CHANGELOG_ENTRY = """v20260910

[아카이브 5편 전체 한글화]
- 타이틀 화면의 아카이브에서 볼 수 있는 이전 작품 줄거리를 전부 한글로
  옮겼습니다. 문단 246개입니다.
  OG 1 34개, OG 2 40개, OG 외전 36개, 다크 프리즌 26개, 제2차 OG 110개
- 아카이브 메뉴와 REPORT 안내문, 재생 중단 확인 문구도 함께 손봤습니다.
- 문단마다 줄 수와 한 줄 길이를 화면 폭에 맞춰 다시 끊었습니다.
  최대 6줄, 한 줄 42자입니다.

[게임 목록 제목과 아이콘]
- RPCS3 게임 목록에 「슈퍼로봇대전 OG 문 드웰러즈」로 표시됩니다.
- 게임 목록 아이콘도 한글판으로 바꿨습니다.
- 빠른 패처는 이제 PSARC 4개와 함께 PS3_GAME\\PARAM.SFO,
  PS3_GAME\\ICON0.PNG 두 파일도 패치합니다. 타이틀 ID와 버전 항목은
  건드리지 않습니다.
- xdelta 방식도 두 파일을 함께 적용합니다. 게임 데이터 사본처럼 원본
  해시가 다른 경우에는 그 파일만 건너뛰고 나머지를 정상 적용합니다.

[대사 가독성]
- 시나리오 대사와 사전 항목의 줄 끊김을 다시 정리했습니다.
  단어 중간에서 줄이 바뀌던 곳, 기체·인물 사전의 링크 표기 앞뒤 공백,
  강룡전대 상층부 대화의 긴 문장, 코우타 관련 문장을 손봤습니다.

[검증]
- xdelta 6개를 일본판 원본에 역적용해 결과 SHA-256 6/6 일치
- 아카이브 문단 전수 검사: 일본어·한자 잔여 0, 미지원 글리프 0, 잘린 문단 0
- 빠른 패처 범위 팩 6개 항목 대상 해시 일치
- ZIP 재추출 후 수록 파일 해시 전수 일치


"""

README_SECTION = """[제목과 아이콘]
이 버전은 RPCS3 게임 목록의 제목을 「슈퍼로봇대전 OG 문 드웰러즈」로,
아이콘을 한글판으로 바꿉니다. 대상은 PS3_GAME\\PARAM.SFO 와
PS3_GAME\\ICON0.PNG 두 파일이며, 타이틀 ID·버전 항목은 바꾸지 않습니다.

방법 A(빠른 패처)와 방법 C(xdelta) 모두 이 두 파일을 함께 처리합니다.
게임 데이터 사본처럼 원본 해시가 다른 경우에는 그 파일만 건너뛰고
나머지를 정상 적용합니다.

"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def run(*args) -> None:
    subprocess.run([str(a) for a in args], check=True)


def rewrite(path: Path, pairs: list[tuple[str, str]]) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: 앵커 없음 -> {old[:60]}")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def make_patch(xdelta: Path, source: Path, target: Path, out: Path, want_hash: str) -> None:
    run(xdelta, "-e", "-9", "-f", "-s", source, target, out)
    check = out.with_suffix(".roundtrip")
    run(xdelta, "-d", "-f", "-s", source, out, check)
    if digest(check) != want_hash:
        raise AssertionError(f"{out.name} 역적용 해시 불일치")
    check.unlink()


def main() -> None:
    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink()
    xdelta = PKG / "xdelta.exe"

    for name, (source, target, source_hash, target_hash) in PSARC.items():
        if digest(source) != source_hash:
            raise AssertionError(f"{name} 소매판 해시 불일치")
        make_patch(xdelta, source, target, PKG / f"patches/{name}.psarc.sdat.xdelta", target_hash)
        print(f"{name:10} xdelta {(PKG / f'patches/{name}.psarc.sdat.xdelta').stat().st_size:>12,}B 역적용 OK")
    for name, (source, target, source_hash, target_hash, size) in EXTRA.items():
        if digest(source) != source_hash or target.stat().st_size != size:
            raise AssertionError(f"{name} 원본/크기 불일치")
        make_patch(xdelta, source, target, PKG / f"patches/{name}.xdelta", target_hash)
        print(f"{name:10} xdelta {(PKG / f'patches/{name}.xdelta').stat().st_size:>12,}B 역적용 OK")

    # 설치 스크립트 3종 확장
    import importlib.util
    spec = importlib.util.spec_from_file_location("ps1ext", ROOT / "242_extend_install_scripts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.extend(PKG, PSARC, EXTRA, OLD_TARGETS, OLD_VER, NEW_VER)

    # 문서
    rewrite(PKG / "README_사용법.txt", [
        (OLD_VER, NEW_VER),
        ("[A. 복호화 ISO]", README_SECTION + "[A. 복호화 ISO]"),
    ] + [(OLD_TARGETS[n], PSARC[n][3]) for n in ("Common", "General2d", "Logic") if OLD_TARGETS[n] != PSARC[n][3]])
    changelog = PKG / "CHANGELOG.txt"
    raw = changelog.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    changelog.write_bytes((b"\xef\xbb\xbf" if bom else b"")
                          + (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    # EXE
    run(CSC, "-target:winexe", "-optimize+",
        f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"-resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        f"-resource:{QP / 'OGMD_SAVE_proxymap.tsv'},OGMD_SAVE_proxymap.tsv",
        QP / "OGMDIsoQuickPatch.cs")
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")
    print("EXE", digest(PKG / "OGMD_ISO_QuickPatch.exe"))

    sums = PKG / "SHA256SUMS.txt"
    files = sorted((p for p in PKG.rglob("*") if p.is_file()), key=lambda p: p.relative_to(PKG).as_posix())
    sums.write_text("\n".join(f"{digest(p)}  {p.relative_to(PKG).as_posix()}" for p in files) + "\n",
                    encoding="utf-8")

    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PKG.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(REL))
    verify = REL / "zip_verify"
    if verify.exists():
        shutil.rmtree(verify)
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(verify)
    for path in PKG.rglob("*"):
        if path.is_file():
            other = verify / PKG.name / path.relative_to(PKG)
            if not other.is_file() or digest(other) != digest(path):
                raise AssertionError(f"ZIP 재추출 불일치: {path.relative_to(PKG)}")
    shutil.rmtree(verify)
    print(f"zip={ZIP.name} size={ZIP.stat().st_size:,} sha256={digest(ZIP)}")


if __name__ == "__main__":
    main()
