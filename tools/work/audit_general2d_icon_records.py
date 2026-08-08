from __future__ import annotations

import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psarc import PSARC
from sdat import SDATReader


ROOT = Path(__file__).resolve().parents[1]
ENTRY = 3751


def reverse_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        with (ROOT / "korean_build_v3" / name).open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["proxy"]] = row["hangul"]
    return result


def decode(raw: bytes, reverse: dict[str, str]) -> str:
    text = raw.rstrip(b"\0").decode("utf-8", errors="replace")
    return "".join(reverse.get(char, char) for char in text)


def main() -> None:
    path = Path(sys.argv[1])
    with path.open("rb") as stream:
        data = PSARC(SDATReader(stream, 0)).read_entry(ENTRY)
    reverse = reverse_map()
    dump_all = len(sys.argv) >= 4
    scan_start = int(sys.argv[2]) if dump_all else 0
    scan_end = int(sys.argv[3]) if dump_all else len(data) - 8
    found: set[int] = set()
    for offset in range(scan_start, min(scan_end, len(data) - 8), 4):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        if not 1 <= length <= 512 or offset + 4 + length > len(data):
            continue
        payload = data[offset + 4 : offset + 4 + length]
        if not dump_all and b"<I=" not in payload and b"<X=" not in payload:
            continue
        if dump_all:
            try:
                shown = decode(payload, reverse)
            except Exception:
                continue
            if not shown.strip() or "�" in shown or any(ord(c) < 0x20 for c in shown):
                continue
        else:
            shown = decode(payload, reverse)
        if offset in found:
            continue
        found.add(offset)
        print(f"{offset}\tlen={length}\t{shown}")


if __name__ == "__main__":
    main()
