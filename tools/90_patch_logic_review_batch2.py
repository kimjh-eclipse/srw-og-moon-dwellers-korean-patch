#!/usr/bin/env python3
"""Patch reviewed Logic descriptions without changing archive layout."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = Path(r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC\Logic.psarc.sdat")
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_review_batch2_20260814.psarc.sdat"
REPORT = BUILD / "logic_review_batch2_20260814_report.json"

PATCHES = {
    2: [
        (2888, 78, "자신 유닛의 크리티컬 발생률이 10 상승합니다."),
        (3529, 75, "자신 유닛에 [풀 블록] 특수능력을 부여합니다."),
    ],
    4: [
        (86470, 24, "최대 HP+10%"),
        (86501, 45, "최대 HP를 10% 증가시킵니다."),
        (86553, 24, "최대 EN+10%"),
        (86584, 45, "최대 EN을 10% 증가시킵니다."),
    ],
    22: [
        (22652, 60, "＜파일럿에게 특수스킬을 습득시킵니다＞"),
    ],
    # Pilot growth screen: split at the existing fixed field boundary so the
    # final punctuation sits next to '행동할 수 있습니다.' and [변형] starts
    # the second line cleanly.
    24: [
        (7839, 150, "기력 120 이상에서 적 유닛을 격추하면 행동 종료 없이 한 번 더 행동할 수 있습니다. 유닛 하나당"),
        (7990, 157, "한 페이즈에 한 번만 발동합니다. [변형] 등으로 메인 파일럿이 바뀌어도 발동 횟수는 늘어나지 않습니다."),
    ],
}


def load_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv", "general2d_compact_aliases.tsv", "logic_suffix_aliases.tsv"):
        path = BUILD / name
        if path.exists():
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    result[row["hangul"]] = row["proxy"]
    return result


def encoded(text: str, table: dict[str, str]) -> bytes:
    return "".join(table.get(char, char) for char in text).encode("utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "_logic_batch2_source.psarc"
    output_plain = BUILD / "_logic_batch2_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        table = load_map()
        replacements: dict[int, bytes] = {}
        changes = []
        for entry_index, rows in PATCHES.items():
            data = bytearray(source_archive.read_entry(entry_index))
            for offset, span, text in rows:
                replacement = encoded(text, table)
                if len(replacement) > span:
                    raise AssertionError(f"entry {entry_index} off {offset}: overflow {len(replacement)} > {span}")
                before = bytes(data[offset:offset + span]).split(b"\0", 1)[0]
                data[offset:offset + span] = replacement + b"\0" * (span - len(replacement))
                changes.append({
                    "entry": entry_index, "offset": offset, "span": span,
                    "before_hex": before.hex(), "target": text,
                    "target_bytes": len(replacement),
                })
            replacements[entry_index] = bytes(data)

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        with OUTPUT.open("ab") as stream:
            stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        from sdat import SDATReader
        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            mismatches = [
                index for index in range(source_archive.n)
                if candidate.read_entry(index) != replacements.get(index, source_archive.read_entry(index))
            ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = {
            "source_sha256": digest(SOURCE), "output_sha256": digest(OUTPUT),
            "changed_entries": sorted(replacements), "changes": changes,
            "semantic_mismatches": 0, "size": OUTPUT.stat().st_size, **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in (source_archive, candidate):
            if archive is not None and hasattr(archive.f, "close"):
                archive.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
