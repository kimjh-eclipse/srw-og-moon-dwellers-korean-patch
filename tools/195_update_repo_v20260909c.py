#!/usr/bin/env python3
"""저장소 클론을 v20260909c 로 갱신 (커밋·푸시는 하지 않음). v20260907b 기준에서 갱신한다."""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
OLD_VER, NEW_VER = "v20260907b", "v20260909c"
PKG = ROOT / f"release_combined_20260909c/OGMD_KR_{NEW_VER}"
ZIP = ROOT / f"release_combined_20260909c/OGMD_KR_{NEW_VER}.zip"
OLD_ZIP_SIZE, OLD_ZIP_SHA = "104,983,409", "80FC91AF1F440731D4B90F4CCDC6CC10D212C7D1DC88EE8545881B4533F94575"
OLD_LOGIC = "1AFD7A9AE89CBDE7D6F5B329B8A36EDEDA9045C690E3CB6530A26F8DE4A0235B"
OLD_BATTLE = "48C356CA87C6BBF9BB0B32424EA46FB8B01FEE3FC6EAF29B698FCEF7300C1523"
NEW_LOGIC = "6A192C98E1B2845952D51B52A4CFB44CAA79C5D26F67B42C3BADFC895909D7FE"
NEW_BATTLE = "F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E"
OLD_XDELTA_TOTAL = "52,044,503"

DOCS_ENTRY = """------------------------------------------------------------------------
v20260909c  (2026-09-09)
------------------------------------------------------------------------

[인명·대사 교정 (이슈 #6)]
- 인명 표기를 헬루가, 구 랜든, 후 루 무르, 고모우돗카, 골라이큰르, 잉그로
  통일했습니다. Logic 380건 46엔트리, Battle 319건 70엔트리.
- 35화 「응」을 「네」로, 보다의 문 독백 문장을 교정했습니다.
- 37화 아즈키가 상관에게 반말하던 대사를 존댓말로 고쳤습니다.
- 38화 「제몬 몰터까지 발사당하면」을 「발사하면」으로 고쳤습니다.
- 토우마의 라이오(雷鳳) 전투대사 29건을 라이오 표기로 맞추고 문장을 다시
  다듬었습니다.
- 번역 원본 자료(translated TSV, jp2ko.json, battle_unique_draft.jsonl)도
  함께 고쳐 다음 빌드에서 되돌아가지 않게 했습니다.

[설치 시 수정시각 보존]
- 설치 직전 각 PSARC 의 수정시각을 읽어 교체 후 같은 시각으로 되돌립니다.
  ISO·폴더형 게임·RPCS3 설치 데이터에 모두 적용됩니다.
- 원본 복구도 고정값이 아니라 백업 파일 자체의 수정시각을 씁니다.
- 이 게임의 무결성 검사는 내용이 아니라 수정시각을 보기 때문에, 폴더 직접
  패치 후 「게임 데이터가 손상되었습니다」가 뜨던 경우가 사라집니다.

[설치 데이터 정리를 기본값으로]
- ISO 패치 화면의 「설치 데이터와 SPU 캐시만 정리」 옵션이 기본 켜짐입니다.
- 수정시각을 보존하면 위 오류가 뜨지 않는데, 게임은 dev_hdd0\\game\\BLJS10335
  사본이 있으면 그것을 먼저 읽습니다. 사본을 지우지 않으면 경고 없이 패치가
  적용되지 않은 화면을 보게 되므로 정리를 기본 동작으로 올렸습니다.
- 정리를 켠 상태에서 RPCS3 경로를 지정하지 않아도 패치는 막히지 않습니다.
  위험을 알리고 「정리 없이 계속」을 선택할 수 있습니다.
- 정리 범위는 이전과 같습니다. dev_hdd0\\game\\BLJS10335 와
  cache\\BLJS10335\\spu-safe-v1-tane.dat 만 지웁니다.

[검증]
- xdelta 4개를 일본판 원본에 역적용해 최종 PSARC SHA-256 4/4 일치
- Battle 이슈 대상 798건 재검사 잔존 0건, 라이오 29/29
- 수정 엔트리 SDAT 재읽기 일치, ZIP 재추출 후 수록 파일 해시 전수 일치
- 35~38화 대사와 라이오 전투대사를 인게임에서 확인

[감사의 말]
- 이번 교정은 GitHub 이슈 #6 의 제보에서 나왔습니다.

"""

KNOWN_ISSUE_NOTE = """
## 롬을 패치한 뒤에는 설치 데이터를 지우세요

**v20260909c부터** 패치는 파일 수정시각을 보존합니다. 이 게임의 무결성 검사는 내용이 아니라
수정시각을 보기 때문에, 롬을 패치해도 「게임 데이터가 손상되었습니다」가 더는 뜨지 않습니다.

그런데 게임은 `<RPCS3 폴더>\\dev_hdd0\\game\\BLJS10335` 설치 데이터가 남아 있으면
그 사본을 먼저 읽습니다. 지금까지는 위 오류가 "사본을 지워야 한다"는 신호 역할을 했는데,
그 신호가 사라졌으므로 **사본을 지우지 않으면 아무 경고 없이 패치가 적용되지 않은 화면**을
보게 됩니다.

빠른 패처의 「설치 데이터와 SPU 캐시만 정리」 옵션은 기본으로 켜져 있습니다.
직접 지우실 때도 이 폴더는 세이브 폴더가 아니므로 세이브는 사라지지 않습니다.
세이브는 `dev_hdd0\\home` 아래에 있습니다.
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
    new_zip_sha, new_zip_size = digest(ZIP), f"{ZIP.stat().st_size:,}"
    xdelta_total = sum((PKG / "patches" / f"{n}.psarc.sdat.xdelta").stat().st_size
                       for n in ("Common", "General2d", "Logic", "Battle"))
    common = [(OLD_VER, NEW_VER), (OLD_ZIP_SIZE, new_zip_size), (OLD_ZIP_SHA, new_zip_sha)]
    hashes = [(OLD_LOGIC, NEW_LOGIC), (OLD_BATTLE, NEW_BATTLE)]
    rewrite(REPO / "README.md", common + hashes)
    rewrite(REPO / "docs/home.md", common + [(OLD_XDELTA_TOTAL, f"{xdelta_total:,}")])
    rewrite(REPO / "docs/install.md", common + hashes)

    for name in ("CHANGELOG.txt", "README_사용법.txt", "install_xdelta.ps1", "verify_xdelta.ps1",
                 "restore_xdelta_backup.ps1", "xdelta.exe",
                 "patches/Common.psarc.sdat.xdelta", "patches/General2d.psarc.sdat.xdelta",
                 "patches/Logic.psarc.sdat.xdelta", "patches/Battle.psarc.sdat.xdelta"):
        shutil.copy2(PKG / name, REPO / name)

    cl = REPO / "docs/changelog.md"
    text = cl.read_text(encoding="utf-8-sig")
    marker = "------------------------------------------------------------------------\nv20260907b  ("
    if marker not in text or NEW_VER in text:
        raise AssertionError("docs/changelog.md 삽입 지점 확인 필요")
    cl.write_text(text.replace(marker, DOCS_ENTRY + marker, 1), encoding="utf-8")

    ki = REPO / "docs/known-issues.md"
    text = ki.read_text(encoding="utf-8-sig")
    if "롬을 패치한 뒤에는 설치 데이터를 지우세요" not in text:
        anchor = "## 번역 범위 정리\n"
        if anchor not in text:
            raise AssertionError("known-issues 삽입 지점 확인 필요")
        ki.write_text(text.replace(anchor, KNOWN_ISSUE_NOTE.lstrip("\n") + "\n" + anchor, 1), encoding="utf-8")

    for name in ("185_audit_issue6.py", "186_audit_battle_issue6_retail.py", "187_dump_logic_scenes_issue6.py",
                 "188_patch_issue6_20260909.py", "189_sync_issue6_translation_sources.py",
                 "190_build_v20260909_release.py", "191_analyze_issue6_battle_sizes.py",
                 "192_build_v20260909b_release.py", "193_default_gamedata_cleanup.py",
                 "194_build_v20260909c_release.py", "195_update_repo_v20260909c.py"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, REPO / "tools" / name)
        else:
            print("건너뜀(없음):", name)
    shutil.copy2(ROOT / "iso_quickpatch/OGMDIsoQuickPatch.cs", REPO / "tools/iso_quickpatch/OGMDIsoQuickPatch.cs")
    shutil.copy2(ROOT / "iso_quickpatch/build_range_pack.py", REPO / "tools/iso_quickpatch/build_range_pack.py")
    for name in ("27_build_logic_translation.py", "32_build_battle_safe_full.py"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, REPO / "tools" / name)

    listed = [line.split("  ", 1)[1] for line in (REPO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = []
    for rel in listed:
        src = PKG / rel if rel == "OGMD_ISO_QuickPatch.exe" else REPO / rel
        lines.append(f"{digest(src)}  {rel}")
    (REPO / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for rel in ("README.md", "docs/home.md", "docs/install.md", "README_사용법.txt",
                "install_xdelta.ps1", "CHANGELOG.txt", "docs/changelog.md"):
        t = (REPO / rel).read_text(encoding="utf-8-sig")
        for stale in (OLD_ZIP_SHA, OLD_LOGIC, OLD_BATTLE):
            assert stale not in t, (rel, stale[:8])
    print(f"repo 갱신: zip {new_zip_size}B {new_zip_sha[:8]} / Logic {NEW_LOGIC[:8]} / Battle {NEW_BATTLE[:8]} / xdelta 합계 {xdelta_total:,}")


if __name__ == "__main__":
    main()
