#!/usr/bin/env python3
"""저장소 클론을 v20260907b 로 갱신 (커밋·푸시는 하지 않음). 해시·크기는 패키지에서 읽는다."""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
OLD_VER, NEW_VER = "v20260907", "v20260907b"
PKG = ROOT / f"release_combined_20260907b/OGMD_KR_{NEW_VER}"
ZIP = ROOT / f"release_combined_20260907b/OGMD_KR_{NEW_VER}.zip"
OLD_ZIP_SIZE, OLD_ZIP_SHA = "104,626,875", "F404229D54D4975853E30D0440602C4CCE81ED6E205052D08AC759CA1C9734DC"
OLD_BATTLE = "F7A5BA065F32E72294A4F63CD43E42A9D97B4F87869209CCEBD40DF0914B51C3"


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
    new_zip_sha, new_zip_size = digest(ZIP), f"{ZIP.stat().st_size:,}"
    new_battle = digest(ROOT / "korean_build_v3/Battle_hud_labels_ko_20260906.psarc.sdat")
    xdelta_total = sum((PKG / "patches" / f"{n}.psarc.sdat.xdelta").stat().st_size for n in ("Common", "General2d", "Logic", "Battle"))
    common = [(OLD_VER, NEW_VER), (OLD_ZIP_SIZE, new_zip_size), (OLD_ZIP_SHA, new_zip_sha)]
    rewrite(REPO / "README.md", common + [(OLD_BATTLE, new_battle)])
    rewrite(REPO / "docs/home.md", common + [("51,874,298", f"{xdelta_total:,}")])
    rewrite(REPO / "docs/install.md", common + [(OLD_BATTLE, new_battle)])

    for name in ("CHANGELOG.txt", "README_사용법.txt", "install_xdelta.ps1", "verify_xdelta.ps1",
                 "restore_xdelta_backup.ps1", "xdelta.exe", "patches/Battle.psarc.sdat.xdelta"):
        shutil.copy2(PKG / name, REPO / name)

    # docs/changelog.md
    pkg_entry = (PKG / "CHANGELOG.txt").read_text(encoding="utf-8-sig").split("\n\n\nv20260907\n", 1)[0]
    body = pkg_entry.split("\n", 1)[1].strip("\n")
    entry = ("------------------------------------------------------------------------\n"
             f"{NEW_VER}  (2026-09-06)\n"
             "------------------------------------------------------------------------\n\n" + body + "\n\n")
    cl = REPO / "docs/changelog.md"
    text = cl.read_text(encoding="utf-8-sig")
    marker = "------------------------------------------------------------------------\nv20260907  ("
    if marker not in text or NEW_VER in text:
        raise AssertionError("docs/changelog.md 삽입 지점 확인 필요")
    cl.write_text(text.replace(marker, entry + marker, 1), encoding="utf-8")

    # known-issues 5번: 세이브 목록 — 해결 수단 추가
    ki = REPO / "docs/known-issues.md"
    text = ki.read_text(encoding="utf-8-sig")
    anchor = "세이브 목록의 글자는 저장하는 시점에 기록되므로, 예전에 만든 세이브는 예전 문구를 유지합니다.\n"
    if anchor not in text:
        raise AssertionError("known-issues 5번 앵커 없음")
    if "세이브 목록 한글화" not in text:
        text = text.replace(anchor, anchor +
            "\n**v20260907b부터** 빠른 패처의 「세이브 목록 한글화 (PARAM.SFO)」 버튼(또는 `--save-hangul \"<RPCS3 폴더>\"`)으로\n"
            "세이브 폴더의 PARAM.SFO 표시용 문자열만 실제 한글로 되돌릴 수 있습니다. 세이브 본체는 건드리지 않고,\n"
            "원본 PARAM.SFO 는 `dev_hdd0\\home\\<사용자>\\ogmd_sfo_backup_<시각>\\` 에 백업됩니다.\n"
            "게임이 새로 저장하면 그 세이브는 다시 깨져 보이므로 필요할 때마다 다시 실행하세요.\n", 1)
        ki.write_text(text, encoding="utf-8")

    # 도구
    for name in ("173_localize_battle_hud_labels.py", "181_add_save_hangul_to_patcher.py", "182_build_v20260907b_release.py",
                 "183_update_repo_v20260907b.py", "ogmd_save_hangul.py"):
        shutil.copy2(ROOT / name, REPO / "tools" / name)
    shutil.copy2(ROOT / "iso_quickpatch/OGMDIsoQuickPatch.cs", REPO / "tools/iso_quickpatch/OGMDIsoQuickPatch.cs") \
        if (REPO / "tools/iso_quickpatch").exists() else None
    (REPO / "tools/data").mkdir(exist_ok=True)
    # 역매핑 표는 .tsv 가 .gitignore 대상이라 명시적으로 강제 추가한다 (git add -f 는 게시 스크립트에서)
    shutil.copy2(ROOT / "korean_build_v3/save_proxy_reverse_map.tsv", REPO / "tools/data/save_proxy_reverse_map.tsv")

    listed = [line.split("  ", 1)[1] for line in (REPO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = []
    for rel in listed:
        src = PKG / rel if rel == "OGMD_ISO_QuickPatch.exe" else REPO / rel
        lines.append(f"{digest(src)}  {rel}")
    (REPO / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for rel in ("README.md", "docs/home.md", "docs/install.md", "README_사용법.txt", "install_xdelta.ps1", "CHANGELOG.txt", "docs/changelog.md"):
        t = (REPO / rel).read_text(encoding="utf-8-sig")
        assert OLD_ZIP_SHA not in t and OLD_BATTLE not in t, rel
    print(f"repo 갱신 완료: zip {new_zip_size}B {new_zip_sha[:8]} / Battle {new_battle[:8]} / xdelta 합계 {xdelta_total:,}")


if __name__ == "__main__":
    main()
