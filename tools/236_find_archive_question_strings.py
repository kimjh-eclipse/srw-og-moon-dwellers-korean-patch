#!/usr/bin/env python3
"""아카이브 재생 중단 QUESTION 팝업의 일본어 두 줄을 찾는다.

화면: 「再生を中止します。」 / 「よろしいですか？」 (네 / 아니요 는 이미 한글)
게임 데이터(설치본)의 Logic·Common·General2d 를 훑어 엔트리·오프셋·필드 용량을 뽑는다.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

GAME = Path(r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC")
NEEDLES = ("再生を中止", "よろしいですか", "中止します")


def field_at(data: bytes, pos: int) -> tuple[int, int, bytes]:
    """pos 를 포함하는 NUL 구분 필드의 (시작, 용량, 내용)."""
    start = data.rfind(b"\0", 0, pos) + 1
    end = data.find(b"\0", pos)
    if end < 0:
        end = len(data)
    # 뒤따르는 NUL 패딩까지 용량으로 센다
    pad = end
    while pad < len(data) and data[pad] == 0:
        pad += 1
    return start, pad - start, data[start:end]


def main() -> None:
    for archive_name in ("Battle", "General3d"):
        path = GAME / f"{archive_name}.psarc.sdat"
        print(f"\n===== {archive_name} ({path.stat().st_size:,}B)")
        with path.open("rb") as stream:
            archive = PSARC(SDATReader(stream, 0))
            names = archive.manifest()
            for entry in range(1, archive.n):
                try:
                    data = archive.read_entry(entry)
                except Exception as exc:  # noqa: BLE001
                    print(f"  entry {entry} 읽기 실패: {exc}")
                    continue
                for needle in NEEDLES:
                    raw = needle.encode("utf-8")
                    pos = data.find(raw)
                    while pos >= 0:
                        start, cap, content = field_at(data, pos)
                        try:
                            text = content.decode("utf-8")
                        except UnicodeDecodeError:
                            text = repr(content[:80])
                        print(f"  entry {entry} {names[entry - 1]}")
                        print(f"    hit={needle} at 0x{pos:X} field=0x{start:X} cap={cap} len={len(content)}")
                        print(f"    text={text[:120]}")
                        pos = data.find(raw, pos + 1)


if __name__ == "__main__":
    main()
