#!/usr/bin/env python3
"""Build a semantically identical Logic using retail fixed entry spans."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
ACCEPTED = ROOT / "korean_build_v3" / "Logic_ace_final_ui7_20260808.psarc.sdat"
OUT_DIR = ROOT / "korean_build_v3"
OUTPUT = OUT_DIR / "Logic_fixed_spans_20260808.psarc.sdat"
REPORT = OUT_DIR / "logic_fixed_spans_20260808_report.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError("encoded SDAT grew")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_plain = OUT_DIR / "LOGIC_fixed_spans_source.psarc"
    output_plain = OUT_DIR / "LOGIC_fixed_spans.psarc"
    header = ORIGINAL.read_bytes()[:0x100]
    try:
        with ORIGINAL.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        retail = PSARC(str(source_plain))
        retail_manifest = retail.manifest()
        replacements: dict[int, bytes] = {}
        with ACCEPTED.open("rb") as stream:
            accepted = PSARC(SDATReader(stream, 0))
            if accepted.manifest() != retail_manifest:
                raise AssertionError("manifest mismatch")
            for entry in range(retail.n):
                old = retail.read_entry(entry)
                new = accepted.read_entry(entry)
                if old != new:
                    if len(old) != len(new):
                        raise AssertionError(f"entry {entry} size mismatch")
                    replacements[entry] = new

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), header, str(OUTPUT))
        pad(OUTPUT, ORIGINAL.stat().st_size)

        mismatches = []
        with OUTPUT.open("rb") as cs, ACCEPTED.open("rb") as acs:
            candidate = PSARC(SDATReader(cs, 0))
            accepted = PSARC(SDATReader(acs, 0))
            for entry in range(candidate.n):
                if candidate.read_entry(entry) != accepted.read_entry(entry):
                    mismatches.append(entry)
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "original": str(ORIGINAL),
            "accepted": str(ACCEPTED),
            "output": str(OUTPUT),
            "original_sha256": digest(ORIGINAL),
            "accepted_sha256": digest(ACCEPTED),
            "output_sha256": digest(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "changed_entries": len(replacements),
            "entries_compared": retail.n,
            "semantic_mismatches": 0,
            **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        obj = locals().get("retail")
        if obj is not None:
            obj.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
