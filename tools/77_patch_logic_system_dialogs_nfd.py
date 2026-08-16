#!/usr/bin/env python3
"""Bypass the in-game Hangul proxy mapper for PS3 system dialogs.

The two affected prompts are converted to Unicode NFD.  The game's proxy
mapper only replaces precomposed Hangul syllables, while the PS3 system
dialog renderer receives the decomposed Korean text directly.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_system_dialogs_spirit_chain_fixed_20260812.psarc.sdat"
OUTPUT = BUILD / "Logic_system_dialogs_nfd_fixed_20260812.psarc.sdat"
REPORT = BUILD / "logic_system_dialogs_nfd_fixed_20260812_report.json"
ENTRY = 22
PATCHES = (
    (9486, 61, "게임을 계속하시겠습니까?", "계속할까요?"),
    (32143, 54, "게임을 계속하시겠습니까?", "계속할까요?"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = BUILD / "LOGIC_system_dialogs_nfd_source.psarc"
    output_plain = BUILD / "LOGIC_system_dialogs_nfd_fixed.psarc"
    verify_plain = BUILD / "LOGIC_system_dialogs_nfd_verify.psarc"
    source_archive = candidate = None
    try:
        with SOURCE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        source_archive = PSARC(str(source_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        changes = []
        for offset, span, current_text, target_text in PATCHES:
            actual = bytes(entry[offset : offset + span]).split(b"\0", 1)[0]
            if actual != current_text.encode("utf-8"):
                raise AssertionError(f"unexpected prompt at {offset}: {actual.hex()}")
            nfd_text = unicodedata.normalize("NFD", target_text)
            target = nfd_text.encode("utf-8")
            if len(target) > span:
                raise AssertionError(f"NFD prompt does not fit at {offset}")
            entry[offset : offset + span] = target + b"\0" * (span - len(target))
            changes.append({
                "offset": offset,
                "span": span,
                "display_text": target_text,
                "normalization": "NFD",
                "target_bytes": len(target),
                "codepoints": [f"U+{ord(char):04X}" for char in nfd_text],
            })

        fixed = rebuild_fixed_entry_spans(source_plain, {ENTRY: bytes(entry)}, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        if OUTPUT.stat().st_size < SOURCE.stat().st_size:
            with OUTPUT.open("ab") as stream:
                stream.write(b"\0" * (SOURCE.stat().st_size - OUTPUT.stat().st_size))
        if OUTPUT.stat().st_size != SOURCE.stat().st_size:
            raise AssertionError("encoded SDAT size changed")

        with OUTPUT.open("rb") as source, verify_plain.open("wb") as target:
            decrypt_stream(source, 0, target)
        candidate = PSARC(str(verify_plain))
        expected = bytes(entry)
        mismatches = [
            index for index in range(source_archive.n)
            if candidate.read_entry(index) != (
                expected if index == ENTRY else source_archive.read_entry(index)
            )
        ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE),
            "output": str(OUTPUT),
            "source_sha256": digest(SOURCE),
            "output_sha256": digest(OUTPUT),
            "entry": ENTRY,
            "changes": changes,
            "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if source_archive is not None:
            source_archive.f.close()
        if candidate is not None:
            candidate.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)
        verify_plain.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
