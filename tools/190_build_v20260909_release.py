#!/usr/bin/env python3
"""GitHub issue #6 수정본 v20260909 패키지와 빠른 패처를 빌드·검증한다."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OLD_VER, NEW_VER = "v20260907b", "v20260909"
OLD_PKG = ROOT / "release_combined_20260907b" / f"OGMD_KR_{OLD_VER}"
REL = ROOT / "release_combined_20260909"
PKG = REL / f"OGMD_KR_{NEW_VER}"
ZIP = REL / f"OGMD_KR_{NEW_VER}.zip"
QP = ROOT / "iso_quickpatch"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
TARGETS = {
    "Logic": ROOT / "korean_build_v3/Logic_issue6_ko_20260909.psarc.sdat",
    "Battle": ROOT / "korean_build_v3/Battle_issue6_ko_20260909.psarc.sdat",
}
OLD_HASHES = {
    "Logic": "1AFD7A9AE89CBDE7D6F5B329B8A36EDEDA9045C690E3CB6530A26F8DE4A0235B",
    "Battle": "48C356CA87C6BBF9BB0B32424EA46FB8B01FEE3FC6EAF29B698FCEF7300C1523",
}
FIXED = {
    "Common": ("Common.psarc.sdat.orig", "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2"),
    "General2d": ("General2d.psarc.sdat.orig", "699C18FDF5F2E6F5650D4D08669C3168A941E8E587137833341D861ED066C473"),
}

CHANGELOG_ENTRY = """v20260909

[GitHub 이슈 #6 수정]
- 인명 표기를 헬루가, 구 랜든, 후 루 무르, 고모우돗카,
  골라이큰르, 잉그로 통일했습니다.
- 35~38화에서 제보된 존댓말과 어색한 문장을 바로잡았습니다.
- 토우마가 라이오(雷鳳)를 번개·뇌봉 등으로 부르던 전투대사 29개를
  라이오로 고치고 문장도 자연스럽게 다듬었습니다.
- 기존 엔딩 전환 키 수정과 세이브 목록 한글화 기능은 유지됩니다.

[검증]
- Logic/Battle 수정 엔트리 전부 재읽기 일치
- 소매판 원본에 xdelta 4개 역적용 후 최종 SHA-256 4/4 일치
- Battle 이슈 대상 798건 재검사: 잘못된 표기 0건, 라이오 29/29


"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def run(*args: str | Path, cwd: Path | None = None) -> None:
    subprocess.run([str(arg) for arg in args], check=True, cwd=cwd)


def rewrite(path: Path, pairs: list[tuple[str, str]]) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    for old, new in pairs:
        if old not in text:
            raise AssertionError(f"{path.name}: {old[:30]!r} 없음")
        text = text.replace(old, new)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def rewrite_idempotent(path: Path, pairs: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    pending = [(old, new) for old, new in pairs if old in text]
    for old, new in pairs:
        if old not in text and new not in text:
            raise AssertionError(f"{path.name}: 이전/새 값 모두 없음: {old[:30]!r}")
    if pending:
        rewrite(path, pending)


def main() -> None:
    hashes = {name: digest(path) for name, path in TARGETS.items()}
    print("targets", hashes)
    if PKG.exists():
        shutil.rmtree(PKG)
    REL.mkdir(exist_ok=True)
    shutil.copytree(OLD_PKG, PKG)
    (PKG / "SHA256SUMS.txt").unlink(missing_ok=True)
    xdelta = PKG / "xdelta.exe"
    for name, target in TARGETS.items():
        retail = ROOT / "original_backups" / f"{name}.psarc.sdat.orig"
        patch = PKG / "patches" / f"{name}.psarc.sdat.xdelta"
        # Battle 원본은 1.7GB라 -9의 이득보다 계산 시간이 지나치게 크다.
        # -3도 동일한 결과를 복원하며 릴리즈 패치 크기는 충분히 작다.
        run(xdelta, "-e", "-3", "-f", "-s", retail, target, patch)
        check = REL / f"_roundtrip_{name}.psarc.sdat"
        run(xdelta, "-d", "-f", "-s", retail, patch, check)
        if digest(check) != hashes[name]:
            raise AssertionError(f"{name} xdelta 역적용 불일치")
        check.unlink()
        print(f"{name} xdelta {patch.stat().st_size:,}B")
    for name, (orig, expected) in FIXED.items():
        check = REL / f"_roundtrip_{name}.psarc.sdat"
        run(xdelta, "-d", "-f", "-s", ROOT / "original_backups" / orig,
            PKG / "patches" / f"{name}.psarc.sdat.xdelta", check)
        if digest(check) != expected:
            raise AssertionError(f"{name} 고정 xdelta 불일치")
        check.unlink()
    print("xdelta 역적용 4/4 일치")

    pairs = [(OLD_VER, NEW_VER)] + [(OLD_HASHES[n], hashes[n]) for n in TARGETS]
    rewrite(PKG / "README_사용법.txt", pairs)
    rewrite(PKG / "install_xdelta.ps1", pairs)
    rewrite(PKG / "verify_xdelta.ps1", [(OLD_HASHES[n], hashes[n]) for n in TARGETS])
    changelog = PKG / "CHANGELOG.txt"
    raw = changelog.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    changelog.write_bytes((b"\xef\xbb\xbf" if bom else b"") +
                          (CHANGELOG_ENTRY + raw.decode("utf-8-sig")).encode("utf-8"))

    rewrite_idempotent(QP / "build_range_pack.py", [
        ("korean_build_v3/Logic_ending_key_ko_20260906.psarc.sdat", f"korean_build_v3/{TARGETS['Logic'].name}"),
        ("korean_build_v3/Battle_hud_labels_ko_20260906.psarc.sdat", f"korean_build_v3/{TARGETS['Battle'].name}"),
        (OLD_HASHES["Logic"], hashes["Logic"]),
        (OLD_HASHES["Battle"], hashes["Battle"]),
    ])
    rewrite_idempotent(QP / "OGMDIsoQuickPatch.cs", [
        ('VersionText = "v20260907b-hud-labels-save-hangul"',
         'VersionText = "v20260909-issue6"'),
    ])
    run(sys.executable, QP / "build_range_pack.py")
    run(CSC, "-target:winexe", "-optimize+", f"-out:{QP / 'OGMD_ISO_QuickPatch.exe'}",
        f"-resource:{QP / 'OGMD_ISO_ranges.bin'},OGMD_ISO_ranges.bin",
        f"-resource:{QP / 'OGMD_SAVE_proxymap.tsv'},OGMD_SAVE_proxymap.tsv",
        QP / "OGMDIsoQuickPatch.cs")
    shutil.copy2(QP / "OGMD_ISO_QuickPatch.exe", PKG / "OGMD_ISO_QuickPatch.exe")

    sums = PKG / "SHA256SUMS.txt"
    files = sorted((p for p in PKG.rglob("*") if p.is_file()), key=lambda p: p.relative_to(PKG).as_posix())
    sums.write_text("\n".join(f"{digest(p)}  {p.relative_to(PKG).as_posix()}" for p in files) + "\n", encoding="utf-8")
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
    print(f"EXE sha256={digest(PKG / 'OGMD_ISO_QuickPatch.exe')}")
    print(f"ZIP {ZIP.stat().st_size:,}B sha256={digest(ZIP)}")


if __name__ == "__main__":
    main()
