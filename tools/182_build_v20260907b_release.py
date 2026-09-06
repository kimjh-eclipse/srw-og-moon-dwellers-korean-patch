#!/usr/bin/env python3
"""v20260907b 릴리즈 조각 생성.

변경: Battle (전투 HUD 공격 종별 라벨 9개 한글화, cosl.dds) + 빠른 패처에 「세이브 목록 한글화」 기능.
Common·General2d·Logic 은 v20260907 과 동일.
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
OLD_VER, NEW_VER = "v20260907", "v20260907b"
OLD_PKG = ROOT / f"release_combined_20260907/OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260907b"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
RETAIL = ROOT / "original_backups/Battle.psarc.sdat.orig"
TARGET = ROOT / "korean_build_v3/Battle_hud_labels_ko_20260906.psarc.sdat"
OLD_HASH = "F7A5BA065F32E72294A4F63CD43E42A9D97B4F87869209CCEBD40DF0914B51C3"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
FIXED = {
    "Common": ("Common.psarc.sdat.orig", "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2"),
    "General2d": ("General2d.psarc.sdat.orig", "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473"),
    "Logic": ("Logic.psarc.sdat.orig", "1AFD7A9AE89CBDE7D6F5B329B8A36EDEDA9045C690E3CB6530A26F8DE4A0235B"),
}

CHANGELOG_ENTRY = """v20260907b

[전투 화면 공격 종별 라벨 이미지 한글화]
- 전투 화면 위에 뜨는 공격 종별 표시 이미지 9개를 한글로 바꿨습니다.
  전체 공격, 재공격, 원호 공격, 원호 방어, 합체 공격, 포위 공격,
  콤비네이션 공격, 더블 어택, 맥시멈 브레이크
- 이 이미지는 전투 HUD 아틀라스(cosl.dds) 안에 들어 있습니다. 예전에
  이 파일을 통째로 바꿨을 때 기체명과 HP/EN 표시가 사라진 적이 있어
  이번에는 라벨 9개의 글자 영역 안쪽 픽셀만 다시 그렸습니다.
  기체명·HP/EN 표시가 정상인 것을 실제 전투 화면에서 확인했습니다.
- 변경 파일은 Battle.psarc.sdat 하나입니다. Common·General2d·Logic 은
  v20260907 과 동일합니다.

[세이브 목록 한글화 (빠른 패처 새 기능)]
- RPCS3 세이브 목록에서 시나리오 제목·루트·톱 에이스 등이 한자처럼 깨져
  보이던 것을 한글로 바꾸는 기능을 빠른 패처에 넣었습니다.
  「세이브 목록 한글화 (PARAM.SFO)」 버튼, 또는 명령줄
  OGMD_ISO_QuickPatch.exe --save-hangul "<RPCS3 폴더>"
- 게임은 한글을 게임 폰트용 대체 코드로 저장하는데, 세이브 목록은 시스템
  폰트로 그려서 그 코드가 한자로 보였습니다. 이 기능은 세이브 폴더의
  PARAM.SFO 안 SUB_TITLE·DETAIL 문자열만 실제 한글로 되돌립니다.
  게임 세이브 본체(.SAV)는 건드리지 않습니다.
- 원본 PARAM.SFO 는 dev_hdd0\\home\\<사용자>\\ogmd_sfo_backup_<시각>\\ 에 백업합니다.
- 게임이 새로 저장하면 그 세이브는 다시 대체 코드로 기록됩니다.
  필요할 때마다 다시 실행하세요. 여러 번 실행해도 안전합니다.

[검증]
- xdelta 4개를 일본판 원본에 역적용해 최종 PSARC SHA-256 4/4 일치 확인
- 빠른 패처 내장 대상 해시를 같은 기준으로 갱신
- Battle 은 cosl.dds 한 엔트리 외 모든 엔트리가 v20260826 과 바이트 동일
- 세이브 목록 한글화: 세이브 8개로 변환·재실행(변경 없음) 확인, 파이썬
  참조 구현과 결과 바이트 동일


"""

README_SECTION = """[D. 세이브 목록 한글화]
RPCS3 세이브 목록에서 시나리오 제목·루트·톱 에이스가 한자처럼 깨져 보이면
1. RPCS3를 완전히 종료합니다.
2. OGMD_ISO_QuickPatch.exe의 `RPCS3 / 폴더형 게임 경로`에 RPCS3 폴더를 지정합니다.
3. `세이브 목록 한글화 (PARAM.SFO)`를 누릅니다.
명령줄: OGMD_ISO_QuickPatch.exe --save-hangul "C:\\RPCS3"

세이브 폴더의 PARAM.SFO 안 표시용 문자열만 바꾸고 세이브 본체는 건드리지 않습니다.
원본 PARAM.SFO 는 dev_hdd0\\home\\<사용자>\\ogmd_sfo_backup_<시각>\\ 에 백업됩니다.
게임이 새로 저장하면 그 세이브는 다시 깨져 보이므로 필요할 때마다 다시 실행하세요.

"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def run(*args: str | Path, cwd: Path | None = None) -> None:
    subprocess.run([str(a) for a in args], check=True, cwd=cwd)


def rewrite(path: Path, pairs: list[tuple[str, str]]) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: '{old[:30]}' 없음")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def main() -> None:
    new_hash = digest(TARGET)
    print("Battle target", TARGET.name, new_hash)

    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink()

    xdelta = PKG / "xdelta.exe"
    patch = PKG / "patches/Battle.psarc.sdat.xdelta"
    run(xdelta, "-e", "-9", "-f", "-s", RETAIL, TARGET, patch)
    check = REL / "_roundtrip.psarc.sdat"
    run(xdelta, "-d", "-f", "-s", RETAIL, patch, check)
    if digest(check) != new_hash:
        raise AssertionError("Battle xdelta 역적용 해시 불일치")
    check.unlink()
    print(f"Battle xdelta {patch.stat().st_size:,}B, 역적용 OK")
    for name, (orig, want) in FIXED.items():
        run(xdelta, "-d", "-f", "-s", ROOT / "original_backups" / orig, PKG / f"patches/{name}.psarc.sdat.xdelta", check)
        if digest(check) != want:
            raise AssertionError(f"{name} xdelta 역적용 해시 불일치")
        check.unlink()
    print("xdelta 역적용 4/4 일치")

    rewrite(PKG / "README_사용법.txt", [(OLD_VER, NEW_VER), (OLD_HASH, new_hash),
                                       ("최종 PSARC SHA-256", README_SECTION + "최종 PSARC SHA-256")])
    rewrite(PKG / "install_xdelta.ps1", [(f"버전 {OLD_VER}", f"버전 {NEW_VER}"), (OLD_HASH, new_hash)])
    rewrite(PKG / "verify_xdelta.ps1", [(OLD_HASH, new_hash)])
    cl = PKG / "CHANGELOG.txt"
    raw = cl.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    cl.write_bytes((b"\xef\xbb\xbf" if bom else b"") + (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    rewrite(QP / "build_range_pack.py", [
        ("        # Battle/cosl.dds image localization is intentionally excluded.\n"
         "        # It is a shared HUD atlas and hid unit names plus HP/EN at runtime.\n",
         "        # Battle/cosl.dds: the shared HUD atlas. A whole-file replacement once hid\n"
         "        # unit names and HP/EN; 173 repaints only the 9 attack-type label boxes.\n"),
        ("korean_build_v3/Battle_names_ko_20260825.psarc.sdat", f"korean_build_v3/{TARGET.name}"),
        (OLD_HASH, new_hash)])
    rewrite(QP / "OGMDIsoQuickPatch.cs",
            [('VersionText = "v20260907-ending-transition-key"', f'VersionText = "{NEW_VER}-hud-labels-save-hangul"')])
    run(sys.executable, QP / "build_range_pack.py")
    run(CSC, "-target:winexe", "-optimize+",
        f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"-resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        f"-resource:{QP / 'OGMD_SAVE_proxymap.tsv'},OGMD_SAVE_proxymap.tsv",
        QP / "OGMDIsoQuickPatch.cs")
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")
    print("EXE", digest(PKG / "OGMD_ISO_QuickPatch.exe"))

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
