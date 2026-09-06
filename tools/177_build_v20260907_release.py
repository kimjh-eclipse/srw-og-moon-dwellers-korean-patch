#!/usr/bin/env python3
"""v20260907 릴리즈 조각 생성 (Logic 만 변경: 엔딩 전환 키 복원).

- v20260826 패키지를 복사하고 Logic xdelta 만 새로 만든다 (다른 3개 xdelta·문서는 그대로).
- xdelta 역적용으로 대상 해시 일치를 확인한다.
- README/CHANGELOG/install/verify 의 버전·Logic 해시를 갱신한다.
- build_range_pack.py Logic 대상 갱신 → 범위 팩 → EXE(csc) 리빌드 → 패키지에 복사.
- SHA256SUMS, ZIP, ZIP 재추출 대조.
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
OLD_VER, NEW_VER = "v20260826", "v20260907"
OLD_PKG = ROOT / f"release_combined_20260826/OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260907"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
RETAIL = ROOT / "original_backups/Logic.psarc.sdat.orig"
TARGET = ROOT / "korean_build_v3/Logic_ending_key_ko_20260906.psarc.sdat"
OLD_HASH = "D1C3FC23F35D9A1710A53C089610558567B22E66D9132CAC9083972CA3CE3A51"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")

CHANGELOG_ENTRY = """v20260907

[엔딩 스태프롤이 나오지 않던 문제]
- 최종화를 클리어한 뒤 엔딩 스태프롤이 나오지 않고 검은 화면에서 멈추던
  문제를 고쳤습니다. 한글 패치를 적용한 상태에서만 발생했습니다.
- 원인은 최종화 시나리오 스크립트(scr00047) 안의 장면 전환 키
  「エンディング」였습니다. 게임은 이 값을 문자열 그대로 찾아 엔딩 장면으로
  넘어가는데, 번역 과정에서 대사로 취급되어 「엔딩」으로 바뀌어 있었습니다.
  같은 부류의 「ゲームオーバー」(패배 전환 키)는 예전에 같은 이유로 고장나
  이미 제외 처리돼 있었고, 「エンディング」만 목록에 빠져 있었습니다.
- 해당 슬롯 2곳만 원문으로 되돌렸습니다. 나머지 한글 번역은 그대로입니다.
  번역 도구의 제외 목록에도 「エンディング」「タイトル」을 추가해 다음
  빌드에서 되돌아가지 않게 했습니다.
- 변경 파일은 Logic.psarc.sdat 하나입니다. Common·General2d·Battle 은
  v20260826 과 동일합니다.

[검증]
- 제보해 주신 클리어 직전 세이브로 최종화를 다시 진행해 스태프롤이 정상
  출력되는 것을 확인했습니다.
- xdelta 4개를 일본판 원본에 역적용해 최종 PSARC SHA-256 4/4 일치 확인
- 빠른 패처 내장 대상 해시를 같은 기준으로 갱신
- 복원한 슬롯 2곳 외 모든 엔트리는 v20260826 과 바이트 단위로 동일

[감사]
- 독트르님이 증상과 함께 클리어 직전 세이브를 보내 주셔서 재현·확인할
  수 있었습니다.


"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def run(*args: str | Path, cwd: Path | None = None) -> None:
    subprocess.run([str(a) for a in args], check=True, cwd=cwd)


def rewrite(path: Path, pairs: list[tuple[str, str]], keep_bom: bool) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: '{old[:30]}' 없음")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if (bom and keep_bom) else b"") + text.encode("utf-8"))


def main() -> None:
    new_hash = digest(TARGET)
    print("Logic target", TARGET.name, new_hash)

    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink()

    # Logic xdelta
    xdelta = PKG / "xdelta.exe"
    logic_patch = PKG / "patches/Logic.psarc.sdat.xdelta"
    run(xdelta, "-e", "-9", "-f", "-s", RETAIL, TARGET, logic_patch)
    check = REL / "_logic_roundtrip.psarc.sdat"
    run(xdelta, "-d", "-f", "-s", RETAIL, logic_patch, check)
    if digest(check) != new_hash:
        raise AssertionError("Logic xdelta 역적용 해시 불일치")
    check.unlink()
    print(f"Logic xdelta {logic_patch.stat().st_size:,}B, 역적용 OK")
    # 나머지 3개 xdelta 도 역적용 재확인
    for name, orig, want in (
        ("Common", "Common.psarc.sdat.orig", "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2"),
        ("General2d", "General2d.psarc.sdat.orig", "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473"),
        ("Battle", "Battle.psarc.sdat.orig", "F7A5BA065F32E72294A4F63CD43E42A9D97B4F87869209CCEBD40DF0914B51C3"),
    ):
        run(xdelta, "-d", "-f", "-s", ROOT / "original_backups" / orig, PKG / f"patches/{name}.psarc.sdat.xdelta", check)
        if digest(check) != want:
            raise AssertionError(f"{name} xdelta 역적용 해시 불일치")
        check.unlink()
    print("xdelta 역적용 4/4 일치")

    # 문서·스크립트
    rewrite(PKG / "README_사용법.txt", [(OLD_VER, NEW_VER), (OLD_HASH, new_hash)], keep_bom=True)
    rewrite(PKG / "install_xdelta.ps1", [(f"버전 {OLD_VER}", f"버전 {NEW_VER}"), (OLD_HASH, new_hash)], keep_bom=True)
    rewrite(PKG / "verify_xdelta.ps1", [(OLD_HASH, new_hash)], keep_bom=True)
    cl = PKG / "CHANGELOG.txt"
    raw = cl.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    cl.write_bytes((b"\xef\xbb\xbf" if bom else b"") + (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    # 범위 팩 + EXE
    rewrite(QP / "build_range_pack.py",
            [("korean_build_v3/Logic_names_ko_20260825.psarc.sdat", f"korean_build_v3/{TARGET.name}"),
             (OLD_HASH, new_hash)], keep_bom=False)
    rewrite(QP / "OGMDIsoQuickPatch.cs",
            [('VersionText = "v20260826-button-icon-slots"', f'VersionText = "{NEW_VER}-ending-transition-key"')],
            keep_bom=True)
    run(sys.executable, QP / "build_range_pack.py")
    run(CSC, "/nologo", "/target:winexe", "/optimize+",
        f"/out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"/resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        QP / "OGMDIsoQuickPatch.cs")
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")
    print("EXE", digest(PKG / "OGMD_ISO_QuickPatch.exe"))

    # 해시 목록 + ZIP
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
