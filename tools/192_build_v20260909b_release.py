#!/usr/bin/env python3
"""v20260909b: PSARC 수정시각 보존 핫픽스 패키지를 빌드·검증한다."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD_VER = "v20260909"
NEW_VER = "v20260909b"
OLD_PKG = ROOT / "release_combined_20260909" / f"OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260909b"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")

TARGET_HASHES = {
    "Common": "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2",
    "General2d": "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473",
    "Logic": "6A192C98E1B2845952D51B52A4CFB44CAA79C5D26F67B42C3BADFC895909D7FE",
    "Battle": "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E",
}
ORIGINALS = {
    "Common": "Common.psarc.sdat.orig",
    "General2d": "General2d.psarc.sdat.orig",
    "Logic": "Logic.psarc.sdat.orig",
    "Battle": "Battle.psarc.sdat.orig",
}
# 정상 실행이 확인된 RPCS3 설치 데이터의 UTC 수정시각.
GAME_DATA_MTIMES = {
    "Common": "2016-05-04T07:55:41Z",
    "General2d": "2016-04-30T05:33:08Z",
    "Logic": "2016-05-04T14:10:23Z",
    "Battle": "2016-05-04T08:07:55Z",
}

CHANGELOG_ENTRY = """v20260909b

[RPCS3 설치 데이터 수정시각 보존 핫픽스]
- 폴더 직접 패치가 ISO 원본용 수정시각을 RPCS3 설치 데이터에도 적용해
  「게임 데이터가 손상되었습니다」가 표시될 수 있던 문제를 고쳤습니다.
- 설치 시 대상 PSARC 각각의 기존 수정시각을 읽어, 패치 결과 교체 후 같은
  시각을 그대로 복원합니다. ISO·폴더형 게임·RPCS3 설치 데이터에 모두 대응합니다.
- 원본 복구도 고정값 대신 백업 파일 자체의 수정시각을 그대로 복원합니다.

[검증]
- 정상 실행이 확인된 RPCS3 설치 데이터 시각으로 실제 xdelta 설치 시험
- 패치 후 PSARC SHA-256 4/4 일치 및 수정시각 4/4 보존 확인
- ZIP 재추출 후 수록 파일 SHA-256 전수 일치


"""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def replace_required(path: Path, pairs: list[tuple[str, str]]) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: 바꿀 문자열 없음: {old[:80]!r}")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def run(*args: str | Path, cwd: Path | None = None) -> None:
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def patch_scripts() -> None:
    install = PKG / "install_xdelta.ps1"
    replace_required(install, [
        ("버전 v20260909", "버전 v20260909b"),
        ("# name = 원본 SHA256 / 패치 후 SHA256 / 크기 / 원래 수정시각(UTC)",
         "# name = 원본 SHA256 / 패치 후 SHA256 / 크기\n# 수정시각은 대상 파일에서 읽어 교체 후 그대로 복원합니다."),
        ("        Mtime  = '2016-05-04T04:37:57Z'\n", ""),
        ("        Mtime  = '2016-04-30T02:15:24Z'\n", ""),
        ("        Mtime  = '2016-05-04T10:52:39Z'\n", ""),
        ("        Mtime  = '2016-05-04T04:50:11Z'\n", ""),
        ("        $ti = Get-Item -LiteralPath $tmp",
         "        # ISO와 RPCS3 설치 데이터의 시각이 다르므로 대상의 실제 값을 보존합니다.\n"
         "        $sourceMtimeUtc = (Get-Item -LiteralPath $src).LastWriteTimeUtc\n\n"
         "        $ti = Get-Item -LiteralPath $tmp"),
        ("        # 수정시각 복원 — 달라지면 부팅/로딩 문제가 생길 수 있습니다.\n"
         "        $mt = [datetime]::Parse($SPEC[$n].Mtime, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)\n"
         "        (Get-Item -LiteralPath $src).LastWriteTimeUtc = $mt",
         "        # 패치 전 대상 파일의 수정시각을 정확히 복원합니다.\n"
         "        (Get-Item -LiteralPath $src).LastWriteTimeUtc = $sourceMtimeUtc"),
    ])

    restore = PKG / "restore_xdelta_backup.ps1"
    replace_required(restore, [
        ("# 원본 SHA-256 및 원래 수정시각(UTC)", "# 원본 SHA-256 (수정시각은 백업 파일 자체의 값을 사용)"),
        ("; Mtime = '2016-05-04T04:37:57Z'", ""),
        ("; Mtime = '2016-04-30T02:15:24Z'", ""),
        ("; Mtime = '2016-05-04T10:52:39Z'", ""),
        ("; Mtime = '2016-05-04T04:50:11Z'", ""),
        ("    $b = Join-Path $BackupDir \"$n.psarc.sdat\"\n    $t = Join-Path $full \"$n.psarc.sdat\"\n    Copy-Item",
         "    $b = Join-Path $BackupDir \"$n.psarc.sdat\"\n    $t = Join-Path $full \"$n.psarc.sdat\"\n    $backupMtimeUtc = (Get-Item -LiteralPath $b).LastWriteTimeUtc\n    Copy-Item"),
        ("    $mt = [datetime]::Parse($SPEC[$n].Mtime, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)\n"
         "    (Get-Item -LiteralPath $t).LastWriteTimeUtc = $mt",
         "    (Get-Item -LiteralPath $t).LastWriteTimeUtc = $backupMtimeUtc"),
    ])

    readme = PKG / "README_사용법.txt"
    replace_required(readme, [("한국어 패치 v20260909", "한국어 패치 v20260909b")])
    raw = readme.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    marker = "두 설치 방식 중 하나만 사용하세요. 같은 대상에 두 방식을 중복 적용하지 마세요."
    note = (marker + "\n\n"
            "이 버전은 폴더 직접 패치 시 각 PSARC의 기존 수정시각을 그대로 보존합니다.\n"
            "RPCS3 설치 데이터에 직접 적용해도 해당 설치 데이터의 시각이 유지됩니다.")
    if marker not in text:
        raise AssertionError("README 안내 삽입 위치 없음")
    text = text.replace(marker, note, 1)
    readme.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))

    changelog = PKG / "CHANGELOG.txt"
    raw = changelog.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    changelog.write_bytes((b"\xef\xbb\xbf" if bom else b"") +
                          (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))


def compile_quickpatch() -> None:
    source = QP / "OGMDIsoQuickPatch.cs"
    source_text = source.read_text(encoding="utf-8-sig")
    old_version = 'VersionText = "v20260909-issue6"'
    new_version = 'VersionText = "v20260909b-mtime-hotfix"'
    if old_version in source_text:
        replace_required(source, [(old_version, new_version)])
    elif new_version not in source_text:
        raise AssertionError("빠른 패처 버전 문자열을 찾을 수 없음")
    run(CSC, "-target:winexe", "-optimize+", f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"-resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        f"-resource:{QP / 'OGMD_SAVE_proxymap.tsv'},OGMD_SAVE_proxymap.tsv",
        source)
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")


def validate_real_install() -> None:
    test_root = REL / "install_test" / "PSARC"
    if test_root.parent.exists():
        shutil.rmtree(test_root.parent)
    test_root.mkdir(parents=True)
    expected_ns: dict[str, int] = {}
    for name, original_name in ORIGINALS.items():
        src = ROOT / "original_backups" / original_name
        dst = test_root / f"{name}.psarc.sdat"
        # 별도 복사본에 RPCS3 설치 데이터 시각을 설정한다. 하드링크는 원본의
        # 파일시각까지 함께 바뀌므로 이 검증에는 사용하지 않는다.
        shutil.copy2(src, dst)
        stamp = datetime.fromisoformat(GAME_DATA_MTIMES[name].replace("Z", "+00:00")).timestamp()
        os.utime(dst, (stamp, stamp))
        expected_ns[name] = dst.stat().st_mtime_ns

    run("powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", PKG / "install_xdelta.ps1", "-TargetDir", test_root, "-SkipBackup")
    for name, expected_hash in TARGET_HASHES.items():
        result = test_root / f"{name}.psarc.sdat"
        if digest(result) != expected_hash:
            raise AssertionError(f"실제 설치 해시 불일치: {name}")
        if result.stat().st_mtime_ns != expected_ns[name]:
            raise AssertionError(f"실제 설치 수정시각 불일치: {name}")
    shutil.rmtree(test_root.parent)
    print("실제 xdelta 설치: 해시 4/4, 수정시각 4/4 보존")


def write_sums_and_zip() -> None:
    sums = PKG / "SHA256SUMS.txt"
    sums.unlink(missing_ok=True)
    files = sorted((p for p in PKG.rglob("*") if p.is_file()),
                   key=lambda p: p.relative_to(PKG).as_posix())
    sums.write_text("\n".join(f"{digest(p)}  {p.relative_to(PKG).as_posix()}" for p in files) + "\n",
                    encoding="utf-8")
    files.append(sums)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PKG.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(REL))
    verify = REL / "zip_verify"
    if verify.exists():
        shutil.rmtree(verify)
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(verify)
    for path in files:
        other = verify / PKG.name / path.relative_to(PKG)
        if not other.is_file() or digest(other) != digest(path):
            raise AssertionError(f"ZIP 재추출 불일치: {path.relative_to(PKG)}")
    shutil.rmtree(verify)


def main() -> None:
    if REL.exists():
        shutil.rmtree(REL)
    REL.mkdir()
    shutil.copytree(OLD_PKG, PKG)
    patch_scripts()
    compile_quickpatch()
    validate_real_install()
    write_sums_and_zip()
    print(f"EXE sha256={digest(PKG / 'OGMD_ISO_QuickPatch.exe')}")
    print(f"ZIP {ZIP.stat().st_size:,}B sha256={digest(ZIP)}")


if __name__ == "__main__":
    main()
