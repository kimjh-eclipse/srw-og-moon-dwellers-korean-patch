#!/usr/bin/env python3
"""Build fixed-layout Logic with the reviewed scenario 0/1 objectives."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "korean_build_v3" / "Logic_ace_final_ui7_20260808.psarc.sdat"
OUTPUT = ROOT / "korean_build_v3" / "Logic_objectives_20260811.psarc.sdat"
REPORT = ROOT / "korean_build_v3" / "logic_objectives_20260811_report.json"

# entry, offset, original byte span, reviewed display text
OBJECTIVES = (
    (36, 39885, 24, "1. 적 전멸."),
    (36, 39910, 36, "1. 에 셀다 격추."),
    (36, 39947, 12, "없음."),
    (37, 27805, 71, "1. 컴패티블 카이저의 HP를 #0 이하로 만든다."),
    (37, 27877, 30, "1. 아키미 격추."),
    (37, 27908, 78, "소울 세이버 FF가 피격되지 않고 승리 조건을 달성한다."),
)


def load_map() -> dict[str, str]:
    result = {}
    for path in (
        ROOT / "korean_build_v3" / "korean_font_map.tsv",
        ROOT / "korean_build_v3" / "compact_aliases.tsv",
    ):
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(ch, ch) for ch in text).encode("utf-8")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source_plain = ROOT / "korean_build_v3" / "LOGIC_objectives_source.psarc"
    output_plain = ROOT / "korean_build_v3" / "LOGIC_objectives.psarc"
    mapping = load_map()
    header = BASE.read_bytes()[:0x100]
    expected_entries: dict[int, bytes] = {}
    try:
        with BASE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        retail = PSARC(str(source_plain))
        replacements = {}

        for entry, offset, span, text in OBJECTIVES:
            data = bytearray(replacements.get(entry, retail.read_entry(entry)))
            encoded = proxy_encode(text, mapping)
            if len(encoded) >= span:
                raise AssertionError(f"objective does not fit: {text!r}")
            data[offset : offset + span] = encoded + b"\0" * (span - len(encoded))
            replacements[entry] = bytes(data)
            expected_entries[entry] = bytes(data)

        fixed = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        if output_plain.stat().st_size != logical_size:
            raise AssertionError("logical PSARC size changed")
        encode(str(output_plain), header, str(OUTPUT))
        if OUTPUT.stat().st_size > BASE.stat().st_size:
            raise AssertionError("encoded SDAT grew")
        if OUTPUT.stat().st_size < BASE.stat().st_size:
            with OUTPUT.open("ab") as stream:
                stream.write(b"\0" * (BASE.stat().st_size - OUTPUT.stat().st_size))

        with OUTPUT.open("rb") as stream:
            check = PSARC(SDATReader(stream, 0))
            if check.manifest() != retail.manifest():
                raise AssertionError("manifest changed")
            for entry, expected in expected_entries.items():
                if check.read_entry(entry) != expected:
                    raise AssertionError(f"readback mismatch at entry {entry}")

        report = {
            "base": str(BASE),
            "output": str(OUTPUT),
            "base_sha256": sha(BASE),
            "output_sha256": sha(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "changed_entries": len(replacements),
            "objectives": [text for _, _, _, text in OBJECTIVES],
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=True, indent=2))
    finally:
        obj = locals().get("retail")
        if obj is not None:
            obj.f.close()
        # Windows can retain a short-lived mapping lock after the PSARC reader
        # closes.  Temporary cleanup must not turn a verified build into a
        # reported failure.
        for temporary in (source_plain, output_plain):
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
