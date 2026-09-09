#!/usr/bin/env python3
"""v20260909c 패키지 생성. v20260909b 에서 빠른 패처만 교체(설치 데이터 정리 기본 켜짐).

PSARC·xdelta·설치 스크립트는 v20260909b 와 동일하다. 문서와 EXE 만 바뀐다.
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
OLD_VER, NEW_VER = "v20260909b", "v20260909c"
OLD_PKG = ROOT / f"release_combined_20260909b/OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260909c"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")

CHANGELOG_ENTRY = """v20260909c

[설치 데이터 정리를 기본값으로]
- ISO 패치 화면의 「설치 데이터와 SPU 캐시만 정리」 옵션을 기본 켜짐으로
  바꿨습니다.
- v20260909b 부터 패치가 파일 수정시각을 그대로 보존합니다. 게임 무결성
  검사는 수정시각을 보기 때문에, 예전처럼 「게임 데이터가 손상되었습니다」가
  뜨지 않습니다. 그런데 게임은 dev_hdd0\\game\\BLJS10335 사본이 남아 있으면
  그 사본을 먼저 읽습니다. 결과적으로 사본을 지우지 않은 경우 오류도 없이
  패치가 적용되지 않은 상태로 플레이하게 됩니다.
  그 상황을 막기 위해 정리를 기본 동작으로 올렸습니다.
- 정리를 켠 상태에서 RPCS3 경로를 지정하지 않았더라도 패치를 막지 않습니다.
  위 위험을 알리고 「정리 없이 계속」을 선택할 수 있습니다.
- 정리 없이 진행하는 경우 패치 확인창에도 같은 경고를 표시합니다.
- 정리 범위는 이전과 같습니다. dev_hdd0\\game\\BLJS10335 와
  cache\\BLJS10335\\spu-safe-v1-tane.dat 만 지우고, 세이브·savestate·
  PPU·셰이더 캐시는 건드리지 않습니다.
- 명령줄은 이전과 같이 --delete-installed-game 을 지정할 때만 정리합니다.

[그 밖에]
- PSARC 4개, xdelta 4개, 설치·검증·복구 스크립트는 v20260909b 와 동일합니다.
  빠른 패처 실행 파일과 문서만 바뀌었습니다.


"""

README_NOTE = """[중요] 롬(ISO 또는 폴더형 게임)을 패치한 뒤에는
<RPCS3 폴더>\\dev_hdd0\\game\\BLJS10335 설치 데이터를 지우거나 옮겨 주세요.
이 버전은 파일 수정시각을 보존하므로 「게임 데이터가 손상되었습니다」가 뜨지
않습니다. 그래서 예전 설치 데이터가 남아 있으면 아무 경고 없이 그 사본이
먼저 쓰이고, 패치가 적용되지 않은 화면을 보게 됩니다.
빠른 패처의 정리 옵션은 기본으로 켜져 있습니다.
설치 데이터는 세이브 폴더가 아닙니다. 세이브는 dev_hdd0\\home 아래에 있습니다.

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
            raise AssertionError(f"{path.name}: '{old[:40]}' 없음")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def main() -> None:
    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink()

    # EXE 재빌드 (범위 팩·세이브 문자 표는 기존 리소스 그대로)
    ranges = QP / "OGMD_ISO_ranges.bin"
    save_map = QP / "OGMD_SAVE_proxymap.tsv"
    for required in (ranges, save_map):
        if not required.is_file():
            raise AssertionError(f"리소스 없음: {required}")
    subprocess.run([str(CSC), "-target:winexe", "-optimize+",
                    f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
                    f"-resource:{ranges},OGMD_ISO_ranges.bin",
                    f"-resource:{save_map},OGMD_SAVE_proxymap.tsv",
                    str(QP / "OGMDIsoQuickPatch.cs")], check=True)
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")
    print("EXE", digest(PKG / "OGMD_ISO_QuickPatch.exe"))

    # 문서
    rewrite(PKG / "README_사용법.txt", [
        (OLD_VER, NEW_VER),
        ("[A. 복호화 ISO]", README_NOTE + "[A. 복호화 ISO]"),
        ("정리 옵션을 선택한 경우에만 dev_hdd0\\game\\BLJS10335 설치 데이터와",
         "정리 옵션(기본 켜짐)을 선택한 경우에만 dev_hdd0\\game\\BLJS10335 설치 데이터와"),
    ])
    rewrite(PKG / "install_xdelta.ps1", [(f"버전 {OLD_VER}", f"버전 {NEW_VER}")])
    cl = PKG / "CHANGELOG.txt"
    raw = cl.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    cl.write_bytes((b"\xef\xbb\xbf" if bom else b"") + (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    # xdelta·스크립트는 909b 와 같아야 한다
    for name in ("patches/Common.psarc.sdat.xdelta", "patches/General2d.psarc.sdat.xdelta",
                 "patches/Logic.psarc.sdat.xdelta", "patches/Battle.psarc.sdat.xdelta",
                 "verify_xdelta.ps1", "restore_xdelta_backup.ps1", "xdelta.exe"):
        if digest(PKG / name) != digest(OLD_PKG / name):
            raise AssertionError(f"{name} 이 v20260909b 와 다름")
    print("xdelta 4개·검증/복구 스크립트 v20260909b 와 동일 확인")

    sums = PKG / "SHA256SUMS.txt"
    files = sorted((p for p in PKG.rglob("*") if p.is_file()), key=lambda p: p.relative_to(PKG).as_posix())
    sums.write_text("\n".join(f"{digest(p)}  {p.relative_to(PKG).as_posix()}" for p in files) + "\n", encoding="utf-8")

    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for p in sorted(PKG.rglob("*")):
            if p.is_file():
                archive.write(p, p.relative_to(REL))
    verify = REL / "zip_verify"
    if verify.exists():
        shutil.rmtree(verify)
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(verify)
    for p in PKG.rglob("*"):
        if p.is_file():
            other = verify / PKG.name / p.relative_to(PKG)
            if not other.is_file() or digest(other) != digest(p):
                raise AssertionError(f"ZIP 재추출 불일치: {p.relative_to(PKG)}")
    shutil.rmtree(verify)
    print(f"zip={ZIP.name} size={ZIP.stat().st_size:,} sha256={digest(ZIP)}")


if __name__ == "__main__":
    main()
