#!/usr/bin/env python3
"""v20260912 배포 패키지 생성.

v20260910 에서 바뀌는 것은 Battle 과 Logic 둘이다.
  Battle : 전투 대사 BMD 의 문자열 참조가 어긋나 일부 대사가 빈 줄로 나오거나
           첫 글자에 찌꺼기가 붙던 것을 고쳤다.
  Logic  : 가이던스 15쪽의 제목과 본문 이미지를 한글로 옮겼다.

  - Battle·Logic xdelta 재생성 + 역적용 해시 대조
  - install/verify 스크립트와 README 의 기대 해시 교체
  - 새 범위 팩으로 EXE 재빌드(버전 문자열 포함)
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
OLD_VER, NEW_VER = "v20260910", "v20260912"
OLD_PKG = ROOT / f"release_combined_20260910/OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260912"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
ORIG = ROOT / "original_backups"
BUILD = ROOT / "korean_build_v3"

# 이름: (소매판, 새 대상, 소매판 해시, 이전 대상 해시, 새 대상 해시, 패치 파일명)
TARGETS = {
    "Battle": (ORIG / "Battle.psarc.sdat.orig",
               BUILD / "battle_refs_20260912/Battle.psarc.sdat",
               "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
               "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E",
               "E7F07D0CED655852CEFD144679829ED3EAEFFF6C06A232D861E1514ACADA66B3",
               "patches/Battle.psarc.sdat.xdelta"),
    "Logic": (ORIG / "Logic.psarc.sdat.orig",
              BUILD / "Logic_guidance_full_ko_20260912.psarc.sdat",
              "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
              "8FA8EC93EFF285BB2AD74DC5D0A23BE8A67EBF1E5A47B9EB269A6E52FE86777C",
              "A2446B21BB01FE32375BC7F337BCDA0E8C2B76083E8681C05ED4B7F50F6F0E28",
              "patches/Logic.psarc.sdat.xdelta"),
}
OLD_VERSION_TEXT = "v20260910-archive-title-icon"
NEW_VERSION_TEXT = "v20260912-battle-guidance"

CHANGELOG_ENTRY = """v20260912

[전투 대사 표시 복구]
- 전투 중 일부 대사가 빈 줄로 나오거나, 첫 글자에 엉뚱한 글자가 붙어
  「흙할 수 없어!」처럼 보이던 문제를 고쳤습니다.
- 원인은 대사 파일(BMD)의 문자열 참조였습니다. 번역을 넣는 과정에서
  문자열이 놓인 자리와 게임이 읽으러 가는 자리가 어긋났습니다.
  대사 내용 자체는 멀쩡했지만 게임이 다른 곳을 읽고 있었습니다.
- 원본의 파일 구조로 실제 참조 위치를 다시 계산해 20,553곳을 바로잡았습니다.
  그중 6,859곳은 빈 영역이나 파일 밖을 가리키고 있었습니다.

[가이던스 한글화]
- 타이틀 화면과 인터미션에서 볼 수 있는 가이던스 15쪽을 한글로 옮겼습니다.
- 쪽 제목 15개와 본문 이미지 15장이 대상입니다. 본문은 텍스트가 아니라
  글자가 그려진 그림이라, 같은 자리에 한글을 다시 그려 넣었습니다.
- 스크린샷, 유닛 그림, 연필·느낌표 아이콘, ALL·MAP 무기 배지,
  START·L1·R1·SELECT 버튼 그림은 원본 그대로 두었습니다.

[검증]
- 전투 대사 참조 66,838개 전수 대조: 전부 일본판 원본과 같은 번호의 대사를 가리킴
- 번역 문자열 40,639개 보존, 미번역 문자열 수 변화 없음
- 가이던스 이미지 15장의 DDS 헤더와 바이트 수 불변, 해당 항목 외 변화 없음
- xdelta 역적용 해시 일치, ZIP 재추출 후 수록 파일 해시 전수 일치


"""

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def run(*args) -> None:
    subprocess.run([str(a) for a in args], check=True)


def rewrite(path: Path, pairs: list[tuple[str, str]], required: bool = True) -> int:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    hits = 0
    for old, new in pairs:
        if old not in text:
            if required:
                raise AssertionError(f"{path.name}: 앵커 없음 -> {old[:60]}")
            continue
        hits += text.count(old)
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return hits


def main() -> None:
    for name, (source, target, source_hash, _old, new_hash, _patch) in TARGETS.items():
        if digest(source) != source_hash:
            raise AssertionError(f"소매판 {name} 해시 불일치")
        if digest(target) != new_hash:
            raise AssertionError(f"새 {name} 해시 불일치")

    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink()
    xdelta = PKG / "xdelta.exe"

    for name, (source, target, _sh, _old, new_hash, rel) in TARGETS.items():
        patch = PKG / rel
        run(xdelta, "-e", "-9", "-f", "-s", source, target, patch)
        check = patch.with_suffix(".roundtrip")
        run(xdelta, "-d", "-f", "-s", source, patch, check)
        if digest(check) != new_hash:
            raise AssertionError(f"{name} xdelta 역적용 해시 불일치")
        check.unlink()
        print(f"{name:7} xdelta {patch.stat().st_size:>12,}B 역적용 OK")

    # 기대 해시와 버전 문자열
    # 기대 해시는 install/verify 에 반드시 있어야 한다. 버전 표기는 파일마다 있을 수도 없을 수도.
    hash_swaps = [(old, new) for _s, _t, _sh, old, new, _r in TARGETS.values()]
    version_swap = [(OLD_VER, NEW_VER)]
    for name in ("install_xdelta.ps1", "verify_xdelta.ps1"):
        hits = rewrite(PKG / name, hash_swaps) + rewrite(PKG / name, version_swap, required=False)
        print(f"{name}: {hits}곳 갱신")
    for name in ("restore_xdelta_backup.ps1", "README_사용법.txt"):
        hits = rewrite(PKG / name, hash_swaps + version_swap, required=False)
        print(f"{name}: {hits}곳 갱신")
    stale = [old for old, _new in hash_swaps + version_swap]
    for name in ("install_xdelta.ps1", "verify_xdelta.ps1", "restore_xdelta_backup.ps1",
                 "README_사용법.txt"):
        raw = (PKG / name).read_bytes().decode("utf-8-sig")
        for value in stale:
            if value in raw:
                raise AssertionError(f"{name}: 옛 값이 남았다 -> {value[:16]}")

    changelog = PKG / "CHANGELOG.txt"
    raw = changelog.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    changelog.write_bytes((b"\xef\xbb\xbf" if bom else b"")
                          + (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    source = QP / "OGMDIsoQuickPatch.cs"
    text = source.read_text(encoding="utf-8")
    if OLD_VERSION_TEXT in text:
        source.write_text(text.replace(OLD_VERSION_TEXT, NEW_VERSION_TEXT), encoding="utf-8")
        print(f"패처 버전 문자열 → {NEW_VERSION_TEXT}")
    elif NEW_VERSION_TEXT not in text:
        raise AssertionError("패처 버전 문자열을 찾지 못했다")

    run(CSC, "-target:winexe", "-optimize+",
        f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"-resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        f"-resource:{QP / 'OGMD_SAVE_proxymap.tsv'},OGMD_SAVE_proxymap.tsv",
        source)
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")
    print("EXE", digest(PKG / "OGMD_ISO_QuickPatch.exe"))

    sums = PKG / "SHA256SUMS.txt"
    files = sorted((p for p in PKG.rglob("*") if p.is_file()),
                   key=lambda p: p.relative_to(PKG).as_posix())
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
