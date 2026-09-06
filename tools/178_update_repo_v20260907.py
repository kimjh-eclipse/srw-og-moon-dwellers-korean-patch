#!/usr/bin/env python3
"""저장소 클론을 v20260907 로 갱신 (커밋·푸시는 하지 않음)."""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1])
PKG = ROOT / "release_combined_20260907/OGMD_KR_v20260907"

OLD_VER, NEW_VER = "v20260826", "v20260907"
OLD_ZIP_SIZE, NEW_ZIP_SIZE = "104,626,181", "104,626,875"
OLD_ZIP_SHA = "A12BE193B703D8296FB5D89D837A64258F4555637D71F67CB74BEB6428447905"
NEW_ZIP_SHA = "F404229D54D4975853E30D0440602C4CCE81ED6E205052D08AC759CA1C9734DC"
OLD_LOGIC = "D1C3FC23F35D9A1710A53C089610558567B22E66D9132CAC9083972CA3CE3A51"
NEW_LOGIC = "1AFD7A9AE89CBDE7D6F5B329B8A36EDEDA9045C690E3CB6530A26F8DE4A0235B"

DOCS_CHANGELOG_ENTRY = """------------------------------------------------------------------------
v20260907  (2026-09-06)
------------------------------------------------------------------------

[엔딩 스태프롤이 나오지 않던 문제]
- 최종화를 클리어한 뒤 엔딩 스태프롤이 나오지 않고 검은 화면에서 멈추던
  문제를 고쳤습니다. 한글 패치를 적용한 상태에서만 발생했습니다.
- 원인은 최종화 시나리오 스크립트(scr00047) 안의 장면 전환 키
  「エンディング」였습니다. 게임은 이 값을 문자열 그대로 찾아 엔딩 장면으로
  넘어가는데, 번역 과정에서 대사로 취급되어 「엔딩」으로 바뀌어 있었습니다.
  같은 부류의 「ゲームオーバー」(패배 전환 키)는 예전에 같은 이유로 고장나
  이미 제외 처리돼 있었고, 「エンディング」만 목록에 빠져 있었습니다.
- 해당 슬롯 2곳만 원문으로 되돌렸습니다. 나머지 한글 번역은 그대로입니다.
  번역 도구의 제외 목록에도 「エンディング」「タイトル」을 추가했습니다.
- 변경 파일은 Logic.psarc.sdat 하나입니다. Common·General2d·Battle 은
  v20260826 과 동일합니다.

[검증]
- 제보해 주신 클리어 직전 세이브로 최종화를 다시 진행해 스태프롤이 정상
  출력되는 것을 확인했습니다.
- xdelta 4개를 일본판 원본에 역적용해 최종 PSARC SHA-256 4/4 일치 확인
- 빠른 패처 내장 대상 해시를 같은 기준으로 갱신
- 복원한 슬롯 2곳 외 모든 엔트리는 v20260826 과 바이트 단위로 동일

[감사의 말]
- 독트르님이 증상과 함께 클리어 직전 세이브를 보내 주셔서 재현·확인할
  수 있었습니다.

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
    common = [(OLD_VER, NEW_VER), (OLD_ZIP_SIZE, NEW_ZIP_SIZE), (OLD_ZIP_SHA, NEW_ZIP_SHA)]
    rewrite(REPO / "README.md", common + [(OLD_LOGIC, NEW_LOGIC)])
    rewrite(REPO / "docs/home.md", common + [("51,874,675", "51,874,298")])
    rewrite(REPO / "docs/install.md", common + [(OLD_LOGIC, NEW_LOGIC)])

    # 패키지 파일 그대로 반영
    for name in ("CHANGELOG.txt", "README_사용법.txt", "install_xdelta.ps1", "verify_xdelta.ps1",
                 "restore_xdelta_backup.ps1", "xdelta.exe", "patches/Logic.psarc.sdat.xdelta"):
        shutil.copy2(PKG / name, REPO / name)

    # docs/changelog.md: 헤더 뒤 첫 항목 앞에 삽입
    cl = REPO / "docs/changelog.md"
    text = cl.read_text(encoding="utf-8-sig")
    marker = "------------------------------------------------------------------------\nv20260826"
    if marker not in text or "v20260907" in text:
        raise AssertionError("docs/changelog.md 삽입 지점 확인 필요")
    cl.write_text(text.replace(marker, DOCS_CHANGELOG_ENTRY + marker, 1), encoding="utf-8")

    # 도구
    for name in ("27_build_logic_translation.py", "176_restore_ending_transition_key.py",
                 "177_build_v20260907_release.py", "178_update_repo_v20260907.py"):
        shutil.copy2(ROOT / name, REPO / "tools" / name)

    # SHA256SUMS.txt: 기존 목록의 파일 그대로 다시 계산 (EXE 는 패키지 것)
    listed = [line.split("  ", 1)[1] for line in (REPO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = []
    for rel in listed:
        src = PKG / rel if rel == "OGMD_ISO_QuickPatch.exe" else REPO / rel
        lines.append(f"{digest(src)}  {rel}")
    (REPO / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for rel in ("README.md", "docs/home.md", "docs/install.md", "README_사용법.txt", "install_xdelta.ps1", "CHANGELOG.txt", "docs/changelog.md"):
        t = (REPO / rel).read_text(encoding="utf-8-sig")
        assert OLD_ZIP_SHA not in t and OLD_LOGIC not in t, rel
    print("repo 갱신 완료; Logic xdelta", digest(REPO / "patches/Logic.psarc.sdat.xdelta")[:8])


if __name__ == "__main__":
    main()
