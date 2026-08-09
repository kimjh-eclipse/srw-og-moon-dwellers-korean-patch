#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a LOGIC dialogue PoC or all translations that fit existing fields."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import argparse
import csv
import hashlib
import json
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from psarc_write import compress_blocks, enable_zopfli, entry_nblocks, rebuild
from sdat import SDATReader
from sdat_encode import encode


POC_UID = 9048
TRANSLATION_OVERRIDES = load_table('TRANSLATION_OVERRIDES')

# ``uid`` is not globally unique in the game's string extraction: a dialogue
# record can share its UID with an unrelated weapon, bonus-description, or
# archive byte sequence.  Never apply an override solely because a UID
# matches.  The exact source text keeps the UI/dialogue corrections scoped to
# the records they were written for.
OVERRIDE_SOURCE_TEXT = load_table('OVERRIDE_SOURCE_TEXT')


def normalize_translation(text: str) -> str:
    """Apply project-wide terminology fixes before proxy encoding."""
    # Angle brackets in these resources are visible keyword delimiters, not
    # control codes.  Translate their contents as well, while preserving the
    # delimiters themselves for the in-game dictionary links.
    replacements = load_table('replacements')
    for source, target in replacements:
        text = text.replace(source, target)
    # Some legacy rows kept faction labels in literal angle brackets.  These
    # are not control codes and must render as ordinary Korean text.
    text = text.replace(load_table("_INLINE")[0], load_table("_INLINE")[1])
    text = re.sub(load_table("_INLINE")[2], " ", text)
    return text


def compact_fixeddata_translation(text: str, file_path: str) -> str:
    """Shorten only database/help prose when a fixed UTF-8 field overflows.

    Dialogue is deliberately excluded: changing its sentence endings globally
    would make a character's voice inconsistent.  These substitutions are
    confined to static help, ability and dictionary records where concise
    declarative wording is appropriate.
    """
    if "/Dat/FixedData/" not in file_path:
        return text
    replacements = load_table('replacements__2')
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def fit_translation(
    text: str, capacity: int, mapping: dict[str, str], file_path: str = ""
) -> str:
    """Compact only typography until an otherwise-overflowing line fits."""
    candidates = [
        text,
        text.replace("@　", "@"),
    ]
    candidates.append(
        candidates[-1].translate(
            str.maketrans("！？（）［］", "!?()[]")
        )
    )
    candidates.append(candidates[-1].replace("……", "…"))
    if candidates[-1].startswith("「") and candidates[-1].endswith("」"):
        candidates.append(candidates[-1][1:-1])
    # Frequently duplicated scenario labels and objective strings.  These are
    # exact, meaning-preserving shortenings for retail fixed slots; keeping
    # them here resolves every duplicate consistently without truncation.
    exact_short = load_table('exact_short')
    candidates.append(exact_short.get(candidates[-1], candidates[-1]))
    # Apply semantic shortening only after the lossless typography options.
    # This keeps the normal Korean wording whenever it already fits.
    candidates.append(compact_fixeddata_translation(candidates[-1], file_path))
    for candidate in candidates:
        if len(proxy_encode(candidate, mapping)) <= capacity:
            return candidate
    return text


def unescape_tsv(text: str) -> str:
    output = []
    index = 0
    while index < len(text):
        if text[index] != "\\" or index + 1 >= len(text):
            output.append(text[index])
            index += 1
            continue
        code = text[index + 1]
        if code == "n":
            output.append("\n")
        elif code == "t":
            output.append("\t")
        elif code == "\\":
            output.append("\\")
        else:
            output.extend(("\\", code))
        index += 2
    return "".join(output)


def load_translations(folder: Path) -> dict[int, str]:
    result = {}
    for path in sorted(folder.glob("batch_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            result[int(uid)] = unescape_tsv(text)
    return result


def load_manual_fits(folder: Path) -> dict[tuple[int, str, str], str]:
    """Load reviewed fixed-slot translations using a collision-safe key."""
    result: dict[tuple[int, str, str], str] = {}
    for path in sorted(folder.glob("logic_*_manual_fit.jsonl")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["uid"]), row["file"], row["source"])
            target = row["new_target"]
            previous = result.get(key)
            if previous is not None and previous != target:
                raise ValueError(
                    f"conflicting manual fit for {key} at {path}:{line_number}"
                )
            result[key] = target
    return result


def build_keyword_link_map(
    master: list[dict],
    translations: dict[int, str],
    manual_fits: dict[tuple[int, str, str], str],
    mapping: dict[str, str],
) -> dict[str, str]:
    """Map every original ``<keyword>`` target to its final Korean title.

    The game resolves glossary links by the visible text inside angle
    brackets.  Translating a keyword title but leaving an old Japanese target
    in dialogue or glossary prose therefore makes the link disappear.  Build
    the mapping from the actual KeyWordData title records so every reference
    uses exactly the same spelling and spacing as its destination.
    """
    keyword_rows = [
        row
        for row in master
        if row.get("file") == "/Dat/FixedData/KeyWordData.dat"
    ]
    all_targets = {
        target
        for row in master
        for target in re.findall(r"<([^<>]+)>", row["text"])
    }
    keyword_titles = {row["text"] for row in keyword_rows}
    # Angle brackets are also used by renderer controls such as <C=...>,
    # </C>, <W>, and <X>.  Only labels that actually have a KeyWordData
    # title record are glossary links.
    referenced = all_targets & keyword_titles
    title_rows: dict[str, dict] = {}
    for row in keyword_rows:
        source = row["text"]
        if source not in referenced:
            continue
        if source in title_rows:
            raise ValueError(f"duplicate keyword title: {source!r}")
        title_rows[source] = row

    result = {}
    for source, row in title_rows.items():
        title = normalize_translation(
            translated_text(row, translations, manual_fits)
        )
        title = fit_translation(
            title, row["blen"], mapping, row.get("file", "")
        )
        if "<" in title or ">" in title:
            raise ValueError(f"invalid translated keyword title: {title!r}")
        result[source] = title
    return result


def synchronize_keyword_links(
    source: str, translated: str, keyword_link_map: dict[str, str]
) -> str:
    """Replace translated link labels with the exact destination titles."""
    source_targets = re.findall(r"<([^<>]+)>", source)
    if not source_targets:
        return translated
    translated_targets = re.findall(r"<([^<>]+)>", translated)
    if len(source_targets) != len(translated_targets):
        raise ValueError(
            "keyword link count changed: "
            f"{source_targets!r} -> {translated_targets!r}"
        )
    replacements = iter(
        keyword_link_map.get(target) for target in source_targets
    )

    def replace(match: re.Match[str]) -> str:
        replacement = next(replacements)
        if replacement is None:
            # Renderer control, not a glossary link.
            return match.group(0)
        return f"<{replacement}>"

    return re.sub(r"<[^<>]+>", replace, translated)


def load_roll_caption_rows(path: Path) -> list[dict]:
    """Load only the explicitly translated CSB roll-caption records.

    ``master.jsonl`` intentionally omits these non-dialogue LOGIC resources;
    keep their inclusion narrow so unrelated binary strings remain untouched.
    """
    wanted = set(range(26582, 26602))
    rows = []
    with path.open("rb") as stream:
        for raw in stream:
            try:
                row = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if row.get("uid") in wanted and row.get("psarc") == "LOGIC":
                rows.append(row)
    if {row["uid"] for row in rows} != wanted:
        raise ValueError("opening roll-caption records were not found")
    return rows


def translated_text(
    row: dict,
    translations: dict[int, str],
    manual_fits: dict[tuple[int, str, str], str] | None = None,
) -> str:
    """Return only source-matched overrides; UID collisions are common here."""
    uid = row["uid"]
    manual_key = (uid, row.get("file", ""), row["text"])
    if manual_fits is not None and manual_key in manual_fits:
        text = manual_fits[manual_key]
    elif 26582 <= uid <= 26601:
        # These roll captions are unique non-dialogue records loaded outside
        # the regular TSV batches.
        text = TRANSLATION_OVERRIDES[uid]
    elif (
        uid in TRANSLATION_OVERRIDES
        and row.get("text") == OVERRIDE_SOURCE_TEXT.get(uid)
    ):
        text = TRANSLATION_OVERRIDES[uid]
    elif uid in TRANSLATION_OVERRIDES:
        # This is an unrelated record that happens to reuse the UID.  Keeping
        # its original bytes is safer than injecting a short UI label into a
        # weapon name or a long dictionary description.
        text = row["text"]
    else:
        text = translations[uid]
    if uid == 26582:
        # The opening roll centers each physical line.  Long Korean paragraphs
        # otherwise extend beyond both screen edges, so wrap them explicitly.
        paragraphs = text.split("\n\n")
        text = "\n\n".join(
            "\n".join(
                textwrap.wrap(
                    paragraph,
                    # These roll captions use a wide proportional font and
                    # are center-aligned; 32 Korean glyphs still clip beyond
                    # both edges at 1920px.  Twenty fits with visible margins.
                    width=20,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
            for paragraph in paragraphs
        )
    return text


def load_proxy_map(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            row["hangul"]: row["proxy"]
            for row in csv.DictReader(stream, delimiter="\t")
        }


def proxy_encode(text: str, mapping: dict[str, str]) -> bytes:
    encoded_text = "".join(mapping.get(ch, ch) for ch in text)
    missing = {
        ch
        for ch in encoded_text
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F
    }
    if missing:
        raise ValueError(f"missing Korean proxies: {sorted(missing)}")
    encoded = encoded_text.encode("utf-8")
    if len(encoded) > len(text.encode("utf-8")):
        raise AssertionError("proxy encoding increased UTF-8 byte length")
    return encoded


def pad_file(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"{path} is too large: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("poc", "fit", "full", "fullfixed"),
        default="poc",
    )
    parser.add_argument(
        "--require-zlib-fit",
        action="store_true",
        help=(
            "fail if the normal zlib rebuild exceeds the retail PSARC size; "
            "do not retry with Zopfli"
        ),
    )
    args = parser.parse_args()

    root = Path("work_ogmd")
    build = root / "korean_build_v3"
    source_psarc = root / "LOGIC.psarc"
    source_sdat = root / "original_backups" / "Logic.psarc.sdat.orig"
    tag = {
        "poc": "dialogue_poc",
        "fit": "fit_all",
        "full": "full_all",
        "fullfixed": "full_fixed",
    }[args.mode]
    out_psarc = build / f"LOGIC_{tag}.psarc"
    out_sdat = build / f"Logic_{tag}.psarc.sdat"

    master = [
        json.loads(line)
        for line in (root / "extract" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    master.extend(load_roll_caption_rows(root / "extract_all" / "master_all.jsonl"))
    translations = load_translations(root / "translated")
    manual_fits = load_manual_fits(root / "review_v1")
    proxy_map = load_proxy_map(build / "korean_font_map.tsv")
    compact_map = build / "compact_aliases.tsv"
    if compact_map.exists():
        proxy_map.update(load_proxy_map(compact_map))
    keyword_link_map = build_keyword_link_map(
        master, translations, manual_fits, proxy_map
    )
    selected = [
        row
        for row in master
        if row["psarc"] == "LOGIC"
        and (
            args.mode in ("fit", "full", "fullfixed")
            or row["uid"] == POC_UID
        )
    ]

    psarc = PSARC(str(source_psarc))
    grouped = defaultdict(list)
    for row in selected:
        grouped[row["entry"]].append(row)

    modified = {}
    applied_by_entry = {}
    applied = 0
    overflow = 0
    source_mismatch = 0
    duplicate = 0
    seen_locations = set()
    for entry, rows in sorted(grouped.items()):
        original_entry = psarc.read_entry(entry)
        patched = bytearray(original_entry)
        changed = False
        for row in sorted(rows, key=lambda item: item["off"]):
            location = (entry, row["off"], row["blen"])
            if location in seen_locations:
                duplicate += 1
                continue
            seen_locations.add(location)
            translated = normalize_translation(
                translated_text(row, translations, manual_fits)
            )
            translated = synchronize_keyword_links(
                row["text"], translated, keyword_link_map
            )
            translated = fit_translation(
                translated, row["blen"], proxy_map, row.get("file", "")
            )
            encoded = proxy_encode(translated, proxy_map)
            if len(encoded) > row["blen"]:
                overflow += 1
                continue
            start = row["off"]
            end = start + row["blen"]
            if original_entry[start:end] != row["text"].encode("utf-8"):
                source_mismatch += 1
                continue
            patched[start:end] = encoded + b"\0" * (row["blen"] - len(encoded))
            applied += 1
            changed = True
        if changed:
            modified[entry] = bytes(patched)
            applied_by_entry[entry] = sum(
                1
                for row in rows
                if (entry, row["off"], row["blen"]) in seen_locations
                and len(
                    proxy_encode(
                        fit_translation(
                            synchronize_keyword_links(
                                row["text"],
                                normalize_translation(
                                    translated_text(
                                        row, translations, manual_fits
                                    )
                                ),
                                keyword_link_map,
                            ),
                            row["blen"],
                            proxy_map,
                            row.get("file", ""),
                        ),
                        proxy_map,
                    )
                )
                <= row["blen"]
                and original_entry[
                    row["off"] : row["off"] + row["blen"]
                ]
                == row["text"].encode("utf-8")
            )

    if args.mode == "poc" and applied != 2:
        raise AssertionError(f"expected 2 PoC occurrences, applied {applied}")

    budget_skipped_entries = 0
    budget_skipped_occurrences = 0
    entry_stats = []
    selected_entries = set(modified)
    if args.mode == "fit":
        entry_stats = []
        for entry, data in modified.items():
            psarc_entry = psarc.entries[entry]
            block_index = psarc_entry["block_idx"]
            block_count = entry_nblocks(psarc, entry)
            original_data = psarc.read_entry(entry)
            delta = 0
            for local_block in range(block_count):
                start = local_block * psarc.block_size
                new_chunk = data[start : start + psarc.block_size]
                old_chunk = original_data[start : start + psarc.block_size]
                if new_chunk == old_chunk:
                    continue
                table_size = psarc.block_table[block_index + local_block]
                old_size = table_size if table_size else psarc.block_size
                _csizes, blobs = compress_blocks(new_chunk, psarc.block_size)
                delta += len(blobs[0]) - old_size
            entry_stats.append(
                {
                    "entry": entry,
                    "delta": delta,
                    "occurrences": applied_by_entry[entry],
                }
            )

        selected_entries = {
            stat["entry"] for stat in entry_stats if stat["delta"] <= 0
        }
        # Keep a small reserve for PSARC boundary/accounting differences that
        # are not represented by the per-entry compressed-byte sum.
        compression_safety_reserve = 1024
        remaining = max(
            0,
            -sum(
                stat["delta"]
                for stat in entry_stats
                if stat["delta"] <= 0
            )
            - compression_safety_reserve,
        )
        positive = sorted(
            (stat for stat in entry_stats if stat["delta"] > 0),
            key=lambda stat: (
                -(stat["occurrences"] / stat["delta"]),
                stat["delta"],
            ),
        )
        deferred = []
        for stat in positive:
            if stat["delta"] <= remaining:
                selected_entries.add(stat["entry"])
                remaining -= stat["delta"]
            else:
                deferred.append(stat)
        # Use any leftover bytes on the smallest deferred entries.
        for stat in sorted(deferred, key=lambda item: item["delta"]):
            if stat["delta"] <= remaining:
                selected_entries.add(stat["entry"])
                remaining -= stat["delta"]

        skipped = [
            stat for stat in entry_stats if stat["entry"] not in selected_entries
        ]
        budget_skipped_entries = len(skipped)
        budget_skipped_occurrences = sum(
            stat["occurrences"] for stat in skipped
        )
        modified = {
            entry: data
            for entry, data in modified.items()
            if entry in selected_entries
        }
        applied -= budget_skipped_occurrences

    if args.mode == "fullfixed" and args.require_zlib_fit:
        compression_deltas = []
        for entry, data in modified.items():
            psarc_entry = psarc.entries[entry]
            block_index = psarc_entry["block_idx"]
            block_count = entry_nblocks(psarc, entry)
            original_data = psarc.read_entry(entry)
            delta = 0
            changed_blocks = 0
            for local_block in range(block_count):
                start = local_block * psarc.block_size
                new_chunk = data[start : start + psarc.block_size]
                old_chunk = original_data[start : start + psarc.block_size]
                if new_chunk == old_chunk:
                    continue
                changed_blocks += 1
                table_size = psarc.block_table[block_index + local_block]
                old_size = table_size if table_size else psarc.block_size
                _csizes, blobs = compress_blocks(new_chunk, psarc.block_size)
                delta += len(blobs[0]) - old_size
            compression_deltas.append(
                {
                    "entry": entry,
                    "delta": delta,
                    "occurrences": applied_by_entry[entry],
                    "changed_blocks": changed_blocks,
                }
            )
        compression_deltas.sort(key=lambda item: item["delta"], reverse=True)
        (root / "review_v1" / "logic_compression_deltas.json").write_text(
            json.dumps(compression_deltas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    rebuild(str(source_psarc), modified, str(out_psarc))
    compression_backend = "zlib"
    compressed_psarc_size = out_psarc.stat().st_size
    # LOGIC must retain the retail archive's logical size because the outer
    # SDAT and the game's integrity checks are size-sensitive.  Korean proxy
    # text can make a small number of changed zlib blocks slightly larger than
    # their retail counterparts even though every entry keeps its original
    # length and every pointer remains valid.  Retry only those changed blocks
    # with the bundled Zopfli encoder when the fast zlib pass does not fit.
    # Zopfli produces a standard zlib stream; this changes compression only,
    # never strings, entry sizes, block indices, pointers, or unmodified data.
    if (
        args.mode == "fullfixed"
        and compressed_psarc_size > source_psarc.stat().st_size
    ):
        if args.require_zlib_fit:
            excess = compressed_psarc_size - source_psarc.stat().st_size
            raise RuntimeError(
                "normal zlib rebuild exceeds the retail PSARC size by "
                f"{excess} bytes"
            )
        enable_zopfli()
        rebuild(str(source_psarc), modified, str(out_psarc))
        compression_backend = "zopfli"
        compressed_psarc_size = out_psarc.stat().st_size
    if args.mode == "fit" and out_psarc.stat().st_size > source_psarc.stat().st_size:
        removable = sorted(
            (
                stat
                for stat in entry_stats
                if stat["entry"] in selected_entries and stat["delta"] > 0
            ),
            key=lambda stat: (
                stat["occurrences"] / stat["delta"],
                -stat["delta"],
            ),
        )
        removed = []
        excess = out_psarc.stat().st_size - source_psarc.stat().st_size
        reclaimed = 0
        for stat in removable:
            removed.append(stat)
            reclaimed += stat["delta"]
            if reclaimed >= excess + 1024:
                break
        if not removed:
            raise AssertionError("no removable entries for PSARC size overrun")
        for stat in removed:
            modified.pop(stat["entry"], None)
            selected_entries.discard(stat["entry"])
        budget_skipped_entries += len(removed)
        removed_occurrences = sum(stat["occurrences"] for stat in removed)
        budget_skipped_occurrences += removed_occurrences
        applied -= removed_occurrences
        rebuild(str(source_psarc), modified, str(out_psarc))

    if args.mode != "full":
        pad_file(out_psarc, source_psarc.stat().st_size)
    encode(str(out_psarc), source_sdat.read_bytes()[:0x100], str(out_sdat))
    if args.mode != "full":
        pad_file(out_sdat, source_sdat.stat().st_size)

    with out_sdat.open("rb") as stream:
        readback_psarc = PSARC(SDATReader(stream, 0))
        for entry, expected in modified.items():
            if readback_psarc.read_entry(entry) != expected:
                raise AssertionError(f"readback mismatch at entry {entry}")

    report = {
        "mode": args.mode,
        "selected_occurrences": len(selected),
        "modified_entries": len(modified),
        "applied_occurrences": applied,
        "overflow_occurrences": overflow,
        "source_mismatch": source_mismatch,
        "duplicate_locations": duplicate,
        "budget_skipped_entries": budget_skipped_entries,
        "budget_skipped_occurrences": budget_skipped_occurrences,
        "compression_backend": compression_backend,
        "compressed_psarc_size_before_padding": compressed_psarc_size,
        "psarc_size": out_psarc.stat().st_size,
        "sdat_size": out_sdat.stat().st_size,
        "sdat_sha256": hashlib.sha256(out_sdat.read_bytes()).hexdigest(),
    }
    (build / f"logic_{tag}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
