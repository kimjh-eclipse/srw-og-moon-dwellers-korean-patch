#!/usr/bin/env python3
"""Increase the compact 공격 glyph advance so `원호공격 L2` has a real gap."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = Path(
    r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64"
    r"\dev_hdd0\game\BLJS10335\USRDIR\PSARC\Common.psarc.sdat"
)
RETAIL = ROOT / "original_backups" / "Common.psarc.sdat.orig"
OUTPUT = BUILD / "Common_support_attack_advance_20260814.psarc.sdat"
REPORT = BUILD / "common_support_attack_advance_20260814_report.json"
ENTRY = 3
CODEPOINT = 0xA0DE
EXPECTED_WIDTH = 31
TARGET_WIDTH = 38
EXPECTED_SLOT = 3750


def font_builder():
    spec = importlib.util.spec_from_file_location("font_builder", ROOT / "16_build_korean_font.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "_common_support_advance_source.psarc"
    output_plain = BUILD / "_common_support_advance_output.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        font = bytearray(source_archive.read_entry(ENTRY))
        fb = font_builder()
        metric = fb.metric_offset(font, CODEPOINT)
        current_width = int.from_bytes(font[metric:metric + 2], "big")
        current_slot = fb.metric_slot(font, CODEPOINT)
        if current_width != EXPECTED_WIDTH or current_slot != EXPECTED_SLOT:
            raise AssertionError(
                f"unexpected compact 공격 metric: width={current_width}, slot={current_slot}"
            )
        font[metric:metric + 2] = TARGET_WIDTH.to_bytes(2, "big")

        replacement = {ENTRY: bytes(font)}
        fixed = rebuild_fixed_entry_spans(source_plain, replacement, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size > SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        with OUTPUT.open("ab") as stream:
            stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            candidate_font = candidate.read_entry(ENTRY)
            if int.from_bytes(candidate_font[metric:metric + 2], "big") != TARGET_WIDTH:
                raise AssertionError("candidate glyph advance verification failed")
            mismatches = [
                index
                for index in range(source_archive.n)
                if candidate.read_entry(index)
                != replacement.get(index, source_archive.read_entry(index))
            ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        retail_stat = RETAIL.stat()
        os.utime(OUTPUT, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "source": str(SOURCE),
            "source_sha256": digest(SOURCE),
            "output": str(OUTPUT),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "entry": ENTRY,
            "codepoint": f"U+{CODEPOINT:04X}",
            "slot": EXPECTED_SLOT,
            "width_before": EXPECTED_WIDTH,
            "width_after": TARGET_WIDTH,
            "text_uses": 18,
            "semantic_mismatches": 0,
            **fixed,
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
