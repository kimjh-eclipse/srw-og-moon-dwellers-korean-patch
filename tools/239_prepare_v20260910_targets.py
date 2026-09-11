#!/usr/bin/env python3
"""v20260910 배포 대상 6개를 정본 이름으로 정리한다.

- 아카이브 작업 결과 3개(Common·General2d·Logic)를 korean_build_v3 정본 이름으로 복사
- Battle 은 이슈 #6 판(F1AC61F8) 유지
- 한글 ICON0.PNG 를 ISO 슬롯 크기(114,574B)에 맞춰 0 패딩 (PNG 는 IEND 뒤 바이트를 무시한다)
- PARAM.SFO 제목 확인
"""
from __future__ import annotations

import hashlib
import io
import shutil
import struct
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
TITLES = BUILD / "game_titles_20260910"
ICON_SLOT = 114574

COPIES = {
    BUILD / "archive_all_20260910/Common.psarc.sdat": BUILD / "Common_archive_ko_20260910.psarc.sdat",
    BUILD / "archive_trial_20260910/General2d.psarc.sdat": BUILD / "General2d_archive_ko_20260910.psarc.sdat",
    BUILD / "archive_report_20260910/Logic.psarc.sdat": BUILD / "Logic_archive_ko_20260910.psarc.sdat",
    TITLES / "BLJS10335_disc/PS3_GAME/PARAM.SFO": BUILD / "PARAM_SFO_ko_20260910.bin",
}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def sfo_strings(blob: bytes) -> dict[str, str]:
    _, _, key_off, data_off, count = struct.unpack_from("<4sIIII", blob, 0)
    out = {}
    for i in range(count):
        k_off, fmt, length, _, d_off = struct.unpack_from("<HHIII", blob, 0x14 + 16 * i)
        key = blob[key_off + k_off:blob.index(b"\0", key_off + k_off)].decode()
        if fmt == 0x0204:
            out[key] = blob[data_off + d_off:data_off + d_off + length].rstrip(b"\0").decode("utf-8", "replace")
    return out


def main() -> None:
    for source, dest in COPIES.items():
        if not source.is_file():
            raise SystemExit(f"원본 없음: {source}")
        if not dest.is_file() or sha(dest) != sha(source):
            shutil.copy2(source, dest)
        print(f"{dest.name:44} {dest.stat().st_size:>13,}B  {sha(dest)[:16]}")

    battle = BUILD / "Battle_issue6_ko_20260909.psarc.sdat"
    print(f"{battle.name:44} {battle.stat().st_size:>13,}B  {sha(battle)[:16]}")

    # ICON0.PNG 패딩
    icon_source = TITLES / "ICON0.PNG"
    icon_dest = BUILD / "ICON0_PNG_ko_20260910.bin"
    data = icon_source.read_bytes()
    if b"IEND" not in data[-32:]:
        raise SystemExit("PNG 끝에 IEND 가 없다 — 패딩하면 위험")
    if len(data) > ICON_SLOT:
        raise SystemExit(f"한글 아이콘이 슬롯보다 크다: {len(data)} > {ICON_SLOT}")
    padded = data + b"\0" * (ICON_SLOT - len(data))
    icon_dest.write_bytes(padded)
    print(f"{icon_dest.name:44} {icon_dest.stat().st_size:>13,}B  {sha(icon_dest)[:16]}"
          f"  (원본 {len(data):,}B + 패딩 {ICON_SLOT - len(data):,}B)")

    # 제목 확인
    for label, path in (("소매판", ROOT / "original_backups/PARAM.SFO.orig"),
                        ("한글판", BUILD / "PARAM_SFO_ko_20260910.bin")):
        fields = sfo_strings(path.read_bytes())
        print(f"\n{label} PARAM.SFO TITLE = {fields.get('TITLE')!r}")
        print(f"{label} TITLE_ID = {fields.get('TITLE_ID')!r}  APP_VER={fields.get('APP_VER')!r}")


if __name__ == "__main__":
    main()
