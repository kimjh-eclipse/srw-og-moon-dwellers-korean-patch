#!/usr/bin/env python3
"""Build a compact Common SDAT by grafting only the final Korean font.

The retail Common PSARC layout is retained byte-for-byte except for physical
blocks belonging to /Dat/Font/font.bin.  The output is then compared against
the accepted fully-repacked Common at the decoded-entry level.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_backups" / "Common.psarc.sdat.orig"
ACCEPTED = ROOT / "release_20260728_verified" / "Common.psarc.sdat"
OUT_DIR = ROOT / "korean_build_v3"
OUTPUT = OUT_DIR / "Common_font_fixed_layout_20260808.psarc.sdat"
REPORT = OUT_DIR / "common_font_fixed_layout_20260808_report.json"
FONT_ENTRY = 3
FONT_NAME = "/Dat/Font/font.bin"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad_to(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_plain = OUT_DIR / "COMMON_font_fixed_layout_source.psarc"
    output_plain = OUT_DIR / "COMMON_font_fixed_layout.psarc"
    header = ORIGINAL.read_bytes()[:0x100]

    try:
        with ORIGINAL.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)

        retail = PSARC(str(source_plain))
        retail_manifest = retail.manifest()
        if retail_manifest[FONT_ENTRY - 1] != FONT_NAME:
            raise AssertionError(retail_manifest[FONT_ENTRY - 1])

        with ACCEPTED.open("rb") as stream:
            accepted = PSARC(SDATReader(stream, 0))
            accepted_manifest = accepted.manifest()
            if accepted_manifest != retail_manifest:
                raise AssertionError("accepted Common manifest differs from retail")
            final_font = accepted.read_entry(FONT_ENTRY)

        if len(final_font) != retail.entries[FONT_ENTRY]["orig_size"]:
            raise AssertionError("font size differs from retail slot")

        fixed = rebuild_fixed_blocks(
            source_plain, {FONT_ENTRY: final_font}, output_plain
        )
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("fixed PSARC logical size changed")

        encode(str(output_plain), header, str(OUTPUT))
        pad_to(OUTPUT, ORIGINAL.stat().st_size)

        mismatches: list[dict[str, object]] = []
        with OUTPUT.open("rb") as candidate_stream, ACCEPTED.open("rb") as accepted_stream:
            candidate = PSARC(SDATReader(candidate_stream, 0))
            accepted = PSARC(SDATReader(accepted_stream, 0))
            if candidate.manifest() != accepted.manifest():
                raise AssertionError("candidate manifest differs from accepted")
            for entry in range(candidate.n):
                left = candidate.read_entry(entry)
                right = accepted.read_entry(entry)
                if left != right:
                    mismatches.append(
                        {
                            "entry": entry,
                            "name": "<manifest>" if entry == 0 else retail_manifest[entry - 1],
                            "candidate_sha256": hashlib.sha256(left).hexdigest(),
                            "accepted_sha256": hashlib.sha256(right).hexdigest(),
                        }
                    )

        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:5]}")

        report = {
            "original": str(ORIGINAL),
            "accepted": str(ACCEPTED),
            "output": str(OUTPUT),
            "original_sha256": sha256(ORIGINAL),
            "accepted_sha256": sha256(ACCEPTED),
            "output_sha256": sha256(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "font_entry": FONT_ENTRY,
            "font_name": FONT_NAME,
            "font_size": len(final_font),
            "entries_compared": retail.n,
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        retail_obj = locals().get("retail")
        if retail_obj is not None:
            retail_obj.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
