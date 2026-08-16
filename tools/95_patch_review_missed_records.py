#!/usr/bin/env python3
"""Patch QA records missed by earlier passes without changing archive layout."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
INST = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC"
)
ORIG = ROOT / "original_backups"

COMMON = INST / "Common.psarc.sdat"
GENERAL2D = INST / "General2d.psarc.sdat"
LOGIC = INST / "Logic.psarc.sdat"

OUT_COMMON = BUILD / "Common_review_missed_records_20260814.psarc.sdat"
OUT_GENERAL2D = BUILD / "General2d_review_missed_records_20260814.psarc.sdat"
OUT_LOGIC = BUILD / "Logic_review_missed_records_20260814.psarc.sdat"
REPORT = BUILD / "review_missed_records_20260814_report.json"

ENTRY_WTD = 3751

# One-cell ligatures are required by records whose retail capacity is only one
# Japanese CJK glyph (shield) or four Japanese CJK glyphs (support attack).
CP_SHIELD = 0xA0DD
CP_ATTACK = 0xA0DE
SLOTS = {CP_SHIELD: 3749, CP_ATTACK: 3750}


PILOT_RECORDS = (
    (12136, "조종사 선택", "파일럿 선택"),
    (16604, "조종사 목록", "파일럿 목록"),
    (16688, "조종사 선택", "파일럿 선택"),
)

UNIT_UPGRADE_RECORDS = (
    223368, 985340, 986228, 986276, 1211980,
    1589660, 1590548, 1590596,
)

WEAPON_UPGRADE_RECORDS = (
    987116, 988112, 988160, 1591436, 1592432, 1592480,
)

SHIELD_RECORDS = (
    988808, 989588, 989644, 1377176, 1593128, 1593908, 1593964,
)

SUPPORT_ATTACK_RECORDS = (
    400536, 400752, 401072, 401120, 401584, 401632,
    985300, 986132, 986180,
    1577204, 1577420, 1577740, 1577788, 1578252, 1578300,
    1589620, 1590452, 1590500,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font_builder():
    spec = importlib.util.spec_from_file_location("font_builder", ROOT / "16_build_korean_font.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def ligature(text: str) -> Image.Image:
    image = Image.new("L", (32, 32), 0)
    draw = ImageDraw.Draw(image)
    face = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    box = draw.textbbox((0, 0), text, font=face)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((32 - width) // 2 - box[0], (32 - height) // 2 - box[1]),
        text,
        font=face,
        fill=255,
    )
    return image


def pad_to(path: Path, size: int) -> None:
    if path.stat().st_size > size:
        raise AssertionError(f"encoded SDAT grew: {path}")
    with path.open("ab") as stream:
        stream.write(b"\0" * (size - path.stat().st_size))


def load_map(include_logic_suffixes: bool = False) -> dict[str, str]:
    result: dict[str, str] = {}
    names = [
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
    ]
    if include_logic_suffixes:
        names.append("logic_suffix_aliases.tsv")
    for name in names:
        path = BUILD / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def encoded(text: str, table: dict[str, str]) -> bytes:
    return "".join(table.get(char, char) for char in text).encode("utf-8")


def patch_record(
    data: bytearray,
    offset: int,
    expected: bytes,
    replacement: bytes,
    label: str,
) -> dict[str, object]:
    length = struct.unpack(">I", data[offset:offset + 4])[0]
    start = offset + 4
    end = start + length
    actual = bytes(data[start:end]).rstrip(b"\0")
    if actual != expected:
        raise AssertionError(
            f"{label} at {offset}: {actual.hex()} != {expected.hex()}"
        )
    if len(replacement) > length - 1:
        raise AssertionError(
            f"{label} at {offset}: overflow {len(replacement)} > {length - 1}"
        )
    data[start:end] = replacement + b"\0" * (length - len(replacement))
    return {
        "offset": offset,
        "label": label,
        "record_length": length,
        "before_hex": actual.hex(),
        "after_hex": replacement.hex(),
    }


def build_common() -> tuple[dict[str, object], list[Path], list[PSARC]]:
    fb = font_builder()
    source_plain = BUILD / "_common_missed_source.psarc"
    output_plain = BUILD / "_common_missed_output.psarc"
    with COMMON.open("rb") as source, source_plain.open("wb") as target:
        decrypt_stream(source, 0, target)
    archive = PSARC(str(source_plain))
    font = bytearray(archive.read_entry(3))

    for codepoint, text in ((CP_SHIELD, "방패"), (CP_ATTACK, "공격")):
        metric = fb.metric_offset(font, codepoint)
        slot = fb.metric_slot(font, codepoint)
        if slot == 0:
            font[metric + 2:metric + 4] = bytes(
                (SLOTS[codepoint] % fb.METRIC_CELLS_X, SLOTS[codepoint] // fb.METRIC_CELLS_X)
            )
        elif slot != SLOTS[codepoint]:
            raise AssertionError(f"U+{codepoint:04X} unexpectedly uses slot {slot}")
        font[metric:metric + 2] = (31).to_bytes(2, "big")
        fb.inject_cell(font, SLOTS[codepoint], ligature(text))

    fixed = rebuild_fixed_entry_spans(source_plain, {3: bytes(font)}, output_plain)
    encode(str(output_plain), COMMON.read_bytes()[:0x100], str(OUT_COMMON))
    pad_to(OUT_COMMON, COMMON.stat().st_size)
    with OUT_COMMON.open("rb") as stream:
        verify = PSARC(SDATReader(stream, 0))
        if verify.read_entry(3) != bytes(font):
            raise AssertionError("Common font verification failed")
    return fixed, [source_plain, output_plain], [archive]


def build_general2d(table: dict[str, str]) -> tuple[dict[str, object], list[dict[str, object]], list[Path], list[PSARC]]:
    source_plain = BUILD / "_general2d_missed_source.psarc"
    output_plain = BUILD / "_general2d_missed_output.psarc"
    with GENERAL2D.open("rb") as source, source_plain.open("wb") as target:
        decrypt_stream(source, 0, target)
    archive = PSARC(str(source_plain))
    data = bytearray(archive.read_entry(ENTRY_WTD))
    changes: list[dict[str, object]] = []

    for offset, before, after in PILOT_RECORDS:
        changes.append(patch_record(data, offset, encoded(before, table), encoded(after, table), after))

    changes.append(
        patch_record(data, 141008, encoded("변화", table), encoded("개조도", table), "개조도")
    )

    for offset in UNIT_UPGRADE_RECORDS:
        changes.append(
            patch_record(data, offset, encoded("기체", table), encoded("기체 개조도", table), "기체 개조도")
        )

    for offset in WEAPON_UPGRADE_RECORDS:
        changes.append(
            patch_record(data, offset, encoded("무기를 ", table), encoded("무기 개조도", table), "무기 개조도")
        )

    shield = chr(CP_SHIELD).encode("utf-8")
    for offset in SHIELD_RECORDS:
        # Earlier translation left the retail one-glyph field empty.
        changes.append(patch_record(data, offset, b"", shield, "방패"))

    support_attack = encoded("원호", table) + chr(CP_ATTACK).encode("utf-8") + b" "
    for offset in SUPPORT_ATTACK_RECORDS:
        changes.append(
            patch_record(data, offset, encoded("원호공격", table), support_attack, "원호공격 + 레벨 간격")
        )

    fixed = rebuild_fixed_blocks(source_plain, {ENTRY_WTD: bytes(data)}, output_plain)
    encode(str(output_plain), GENERAL2D.read_bytes()[:0x100], str(OUT_GENERAL2D))
    pad_to(OUT_GENERAL2D, GENERAL2D.stat().st_size)
    with OUT_GENERAL2D.open("rb") as stream:
        verify = PSARC(SDATReader(stream, 0))
        mismatches = [
            index for index in range(archive.n)
            if verify.read_entry(index) != (bytes(data) if index == ENTRY_WTD else archive.read_entry(index))
        ]
    if mismatches:
        raise AssertionError(f"General2d semantic mismatches: {mismatches[:20]}")
    return fixed, changes, [source_plain, output_plain], [archive]


def build_logic(table: dict[str, str]) -> tuple[dict[str, object], list[dict[str, object]], list[Path], list[PSARC]]:
    source_plain = BUILD / "_logic_missed_source.psarc"
    output_plain = BUILD / "_logic_missed_output.psarc"
    with LOGIC.open("rb") as source, source_plain.open("wb") as target:
        decrypt_stream(source, 0, target)
    archive = PSARC(str(source_plain))
    replacements: dict[int, bytes] = {}
    changes: list[dict[str, object]] = []

    patches = {
        2: (
            (3283, 59, "자신 유닛의 최대 HP가 ５％ 상승합니다."),
            (3363, 59, "자신 유닛의 최대 EN이 ５％ 상승합니다."),
        ),
        22: (
            (
                21085,
                146,
                "파일럿의 전투 기술력입니다. 수치가 클수록\n"
                "크리티컬 발생률과 특수스킬 카운터의 발동률이 상승합니다.",
            ),
        ),
    }

    for entry_index, rows in patches.items():
        data = bytearray(archive.read_entry(entry_index))
        for offset, span, text in rows:
            replacement = encoded(text, table)
            if len(replacement) > span:
                raise AssertionError(
                    f"Logic entry {entry_index} off {offset}: overflow {len(replacement)} > {span}"
                )
            before = bytes(data[offset:offset + span]).split(b"\0", 1)[0]
            data[offset:offset + span] = replacement + b"\0" * (span - len(replacement))
            changes.append(
                {
                    "entry": entry_index,
                    "offset": offset,
                    "span": span,
                    "target": text,
                    "target_bytes": len(replacement),
                    "before_hex": before.hex(),
                }
            )
        replacements[entry_index] = bytes(data)

    fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
    encode(str(output_plain), LOGIC.read_bytes()[:0x100], str(OUT_LOGIC))
    pad_to(OUT_LOGIC, LOGIC.stat().st_size)
    with OUT_LOGIC.open("rb") as stream:
        verify = PSARC(SDATReader(stream, 0))
        mismatches = [
            index for index in range(archive.n)
            if verify.read_entry(index) != replacements.get(index, archive.read_entry(index))
        ]
    if mismatches:
        raise AssertionError(f"Logic semantic mismatches: {mismatches[:20]}")
    return fixed, changes, [source_plain, output_plain], [archive]


def main() -> None:
    general_table = load_map()
    logic_table = load_map(include_logic_suffixes=True)
    temp_paths: list[Path] = []
    archives: list[PSARC] = []
    try:
        common_fixed, common_temps, common_archives = build_common()
        general_fixed, general_changes, general_temps, general_archives = build_general2d(general_table)
        logic_fixed, logic_changes, logic_temps, logic_archives = build_logic(logic_table)
        temp_paths += common_temps + general_temps + logic_temps
        archives += common_archives + general_archives + logic_archives

        for output, retail in (
            (OUT_COMMON, ORIG / "Common.psarc.sdat.orig"),
            (OUT_GENERAL2D, ORIG / "General2d.psarc.sdat.orig"),
            (OUT_LOGIC, ORIG / "Logic.psarc.sdat.orig"),
        ):
            stat = retail.stat()
            os.utime(output, ns=(stat.st_atime_ns, stat.st_mtime_ns))

        report = {
            "Common": {
                "output": str(OUT_COMMON),
                "sha256": sha256(OUT_COMMON),
                "size": OUT_COMMON.stat().st_size,
                **common_fixed,
            },
            "General2d": {
                "output": str(OUT_GENERAL2D),
                "sha256": sha256(OUT_GENERAL2D),
                "size": OUT_GENERAL2D.stat().st_size,
                "changes": general_changes,
                "semantic_mismatches": 0,
                **general_fixed,
            },
            "Logic": {
                "output": str(OUT_LOGIC),
                "sha256": sha256(OUT_LOGIC),
                "size": OUT_LOGIC.stat().st_size,
                "changes": logic_changes,
                "semantic_mismatches": 0,
                **logic_fixed,
            },
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for archive in archives:
            if hasattr(archive.f, "close"):
                archive.f.close()
        for path in temp_paths:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
