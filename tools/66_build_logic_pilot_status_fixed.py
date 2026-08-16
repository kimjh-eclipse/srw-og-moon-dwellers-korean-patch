#!/usr/bin/env python3
"""Patch reviewed pilot-status strings on top of the latest Logic build."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "korean_build_v3" / "Logic_before_pilot_status_20260812.psarc.sdat"
OUTPUT = ROOT / "korean_build_v3" / "Logic_pilot_status_20260812.psarc.sdat"
REPORT = ROOT / "korean_build_v3" / "logic_pilot_status_20260812_report.json"

# entry, offset, byte span, expected installed text, reviewed replacement
PATCHES = (
    # The final syllable uses a wider compact glyph, producing a visible gap
    # before the level suffix without overflowing these fixed byte spans.
    (24, 2789, 6, "저력", "저력"),
    (24, 3140, 12, "원호방어", "원호방어"),
    (24, 3301, 15, "카운터", "카운터"),
    (24, 4088, 12, "연속공격", "연속공격"),
    (
        26,
        1213,
        70,
        "F１턴 동안 공격의 명중률이 １００％가 됩니다",
        "1턴 동안 공격의 명중률이 100%가 됩니다.",
    ),
    # Keep the original full-width parentheses: this continuation line is
    # skipped by the spirit-command panel when it begins with ASCII '('.
    (26, 1284, 36, "（「번뜩임」이 우선）.", "（번뜩임이 우선）"),
)


def load_maps() -> tuple[dict[str, str], dict[str, str]]:
    forward: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for name in (
        "korean_font_map.tsv",
        "compact_aliases.tsv",
        "general2d_compact_aliases.tsv",
        "logic_suffix_aliases.tsv",
    ):
        path = ROOT / "korean_build_v3" / name
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                forward[row["hangul"]] = row["proxy"]
                reverse[row["proxy"]] = row["hangul"]
    return forward, reverse


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    return "".join(mapping.get(char, char) for char in text).encode("utf-8")


def proxy_decode(raw: bytes, mapping: dict[str, str]) -> str:
    text = raw.split(b"\0", 1)[0].decode("utf-8")
    return "".join(mapping.get(char, char) for char in text)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    source_plain = ROOT / "korean_build_v3" / "LOGIC_pilot_status_source.psarc"
    output_plain = ROOT / "korean_build_v3" / "LOGIC_pilot_status.psarc"
    forward, reverse = load_maps()
    header = BASE.read_bytes()[:0x100]
    expected_entries: dict[int, bytes] = {}
    try:
        with BASE.open("rb") as source, source_plain.open("wb") as target:
            logical_size, _ = decrypt_stream(source, 0, target)
        retail = PSARC(str(source_plain))
        replacements: dict[int, bytes] = {}

        for entry, offset, span, expected, target in PATCHES:
            data = bytearray(replacements.get(entry, retail.read_entry(entry)))
            current = proxy_decode(data[offset : offset + span], reverse)
            if current != expected:
                raise AssertionError(
                    f"source mismatch entry {entry} offset {offset}: "
                    f"{current!r} != {expected!r}"
                )
            encoded = proxy_encode(target, forward)
            if len(encoded) > span:
                raise AssertionError(
                    f"replacement does not fit entry {entry} offset {offset}: "
                    f"{len(encoded)} > {span}"
                )
            # SpiritData stores these two descriptions as adjacent C strings.
            # Interior NUL padding after the shortened first line makes the
            # game's sequential reader stop before the priority note.
            pad = b" " if entry == 26 and offset in (1213, 1284) else b"\0"
            data[offset : offset + span] = encoded + pad * (span - len(encoded))
            replacements[entry] = bytes(data)

        expected_entries.update(replacements)
        # The current installed archive has no spare compressed bytes in
        # SkillData.  Rebuild the PSARC TOC so the changed entry can grow by a
        # few bytes while preserving every entry's uncompressed contents.
        rebuild(str(source_plain), replacements, str(output_plain))
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
            mismatches = []
            for entry in range(check.n):
                expected = expected_entries.get(entry, retail.read_entry(entry))
                if check.read_entry(entry) != expected:
                    mismatches.append(entry)
            if mismatches:
                raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "base": str(BASE),
            "output": str(OUTPUT),
            "base_sha256": sha(BASE),
            "output_sha256": sha(OUTPUT),
            "size": OUTPUT.stat().st_size,
            "changed_entries": sorted(replacements),
            "patches": [target for *_, target in PATCHES],
            "source_psarc_size": logical_size,
            "output_psarc_size": output_plain.stat().st_size,
            "semantic_mismatches": 0,
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
        for temporary in (source_plain, output_plain):
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
