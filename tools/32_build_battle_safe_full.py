#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a safe, size-preserving Battle SDAT from fitting draft translations.

Entries that cannot use the current font or would exceed their fixed BMD span
are deliberately left in Japanese.  A changed PSARC block is also retained
only when its compressed size does not grow, preserving the original archive
budget without truncating dialogue.
"""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import csv
import hashlib
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

from Crypto.Cipher import AES

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import rebuild_var
from sdat import EDAT_KEY_1, SDAT_KEY, SDATReader, parse_header
from sdat_encode import encode as encode_sdat


# Short combat barks need deliberate, consistent imperatives.  They are too
# terse for machine translation to infer the intended combat tone reliably.
BATTLE_OVERRIDES = load_table('BATTLE_OVERRIDES')

# Second-pass human review: these lines were either left in Japanese or mistranslated
# by the automatic draft.  Keep dialogue unquoted: the game already supplies its
# own dialogue presentation and literal Japanese brackets render poorly with this font.
BATTLE_REVIEW_OVERRIDES = load_table('BATTLE_REVIEW_OVERRIDES')


def normalize_battle_text(text: str) -> str:
    """Normalize Korean dialogue presentation without touching game codes."""
    # The game already provides a dialogue box.  Copied quotation marks render
    # incorrectly in the injected font, so remove paired outer quotation only.
    text = text.strip()
    # NLLB occasionally emits its unknown-token placeholder (U+2047) or an
    # unrelated Indic-script fragment inside an otherwise Korean line.  Those
    # are model artifacts, never intentional game text.  Explicit overrides
    # above restore lines where the missing word is meaningful; for any
    # remaining low-priority bark, remove the corrupt glyph rather than render
    # a visibly broken foreign character in-game.
    text = text.replace("⁇", "")
    text = text.replace("α", load_table("_INLINE")[3]).replace("oci_Latn", "")
    text = re.sub(r"[\u0900-\u0FFF\u1000-\u1FFF]", "", text)
    text = re.sub(r" {2,}", " ", text).strip()
    pairs = (("「", "」"), ("『", "』"), ('"', '"'), ("“", "”"))
    for left, right in pairs:
        if text.startswith(left) and text.endswith(right):
            text = text[len(left) : len(text) - len(right)].strip()
            break
    return re.sub(r" {2,}", " ", text)


def load_map(build: Path) -> dict[str, str]:
    result = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        with (build / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def encode(text: str, mapping: dict[str, str]) -> bytes | None:
    value = "".join(mapping.get(ch, ch) for ch in text)
    if any(0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F for ch in value):
        return None
    return value.encode("utf-8")


def normalize_dialogue_quotes(text: str, source_text: str) -> str:
    """Restore battle-dialogue brackets from the Japanese source structure."""
    text = text.strip()
    if not (source_text.startswith("「") and source_text.endswith("」")):
        return text

    # NLLB emitted several malformed variants: "text"., "text", and a
    # single leading curly quote.  Remove only the outer translation artifact;
    # punctuation inside the actual line remains untouched.
    if text.endswith('".'):
        text = text[:-1]
    if text and text[0] in '"“”＂「':
        text = text[1:]
    if text and text[-1] in '"“”＂」':
        text = text[:-1]
    if text.endswith(".") and not source_text.endswith("。」"):
        text = text[:-1]
    return f"「{text.strip()}」"


def prepare_dialogue(
    text: str,
    mapping: dict[str, str],
    source_text: str = "",
) -> bytes | None:
    # Korean personal names inherited the Japanese middle-dot/equal separator.
    # Display Korean names with an ordinary space in every battle resource.
    text = re.sub(load_table("_INLINE")[0], " ", text)
    text = normalize_dialogue_quotes(text, source_text)
    candidates = [text, text.replace("@　", "@"), text.replace("　", " ")]
    candidates += [candidate.replace("……", "…") for candidate in candidates[-2:]]
    if text.startswith("「") and text.endswith("」"):
        candidates.append(text[1:-1])
    for candidate in candidates:
        raw = encode(candidate, mapping)
        if raw is not None:
            return raw
    return None


def stream_sdat(chunks, plain_size: int, original_header: bytes, output: Path) -> None:
    header_info = parse_header(original_header)
    block_size, dev, digest = header_info["block_size"], header_info["dev_hash"], header_info["digest"]
    crypt_key = bytes(a ^ b for a, b in zip(dev, SDAT_KEY))
    header = bytearray(original_header)
    header[0x88:0x90] = struct.pack(">Q", plain_size)
    pending, written, number = bytearray(), 0, 0
    with output.open("wb") as dst:
        dst.write(header)
        for chunk in chunks:
            pending.extend(chunk)
            while len(pending) >= block_size:
                raw = bytes(pending[:block_size]); del pending[:block_size]
                key = AES.new(EDAT_KEY_1, AES.MODE_ECB).decrypt(AES.new(crypt_key, AES.MODE_ECB).encrypt(dev[:12] + struct.pack(">I", number)))
                cipher = AES.new(key, AES.MODE_CBC, digest).encrypt(raw)
                dst.write(forge_metadata(cipher, crypt_key, dev, number)); dst.write(cipher)
                written += len(raw); number += 1
        if pending:
            raw_len = len(pending)
            raw = bytes(pending) + b"\0" * ((-raw_len) & 15)
            key = AES.new(EDAT_KEY_1, AES.MODE_ECB).decrypt(AES.new(crypt_key, AES.MODE_ECB).encrypt(dev[:12] + struct.pack(">I", number)))
            cipher = AES.new(key, AES.MODE_CBC, digest).encrypt(raw)
            dst.write(forge_metadata(cipher, crypt_key, dev, number)); dst.write(cipher)
            written += raw_len; number += 1
    if written != plain_size:
        raise AssertionError(f"stream size {written} != {plain_size}")


def load_parallel_review_overrides(root: Path) -> dict[str, str]:
    """Load the contiguous, human-reviewed battle batches when present.

    The review files deliberately retain the original Japanese source so a
    stale or misaligned batch cannot silently override another string.
    """
    review_dirs = [
        root / "battle_review_parallel",
        root / "battle_review_next",
    ]
    draft_path = root / "battle_translation" / "battle_unique_draft.jsonl"
    if not any(path.is_dir() for path in review_dirs):
        return {}

    draft = [
        json.loads(line)
        for line in draft_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    overrides: dict[str, str] = {}
    seen_uids: set[int] = set()
    review_paths = []
    for review_dir in review_dirs:
        if review_dir.is_dir():
            review_paths.extend(review_dir.glob("review_*.jsonl"))
    for path in sorted(review_paths):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            item = json.loads(line)
            uid = item["uid"]
            source = item.get("jp", item.get("source"))
            if uid in seen_uids:
                raise AssertionError(f"duplicate review uid {uid} in {path}")
            if uid < 0 or uid >= len(draft):
                raise AssertionError(f"review uid {uid} is out of range")
            if source != draft[uid]["jp"]:
                raise AssertionError(
                    f"review source mismatch at {path.name}:{line_number}"
                )
            translated = item.get("new_ko", item.get("ko", ""))
            if not translated.strip():
                raise AssertionError(
                    f"empty review translation at {path.name}:{line_number}"
                )
            previous = overrides.get(source)
            if previous is not None and previous != translated:
                raise AssertionError(
                    f"conflicting reviewed translation for uid {uid}"
                )
            overrides[source] = translated
            seen_uids.add(uid)

    # Legacy reviewed rows that exceeded their fixed BMD spans are kept as
    # small TSV overlays.  They intentionally replace an already-reviewed
    # UID while preserving the original source alignment above.
    legacy_seen: set[int] = set()
    legacy_dir = root / "battle_review_next"
    legacy_paths = sorted(legacy_dir.glob("legacy_fit_*.tsv"))
    split_bases = {
        path.stem[:-1]
        for path in legacy_paths
        if path.stem[-1:] in {"a", "b", "c"}
    }
    legacy_paths = [
        path for path in legacy_paths if path.stem not in split_bases
    ]
    for path in legacy_paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            uid_text, translated = line.split("\t", 1)
            uid = int(uid_text)
            if uid in legacy_seen:
                raise AssertionError(f"duplicate legacy fit uid {uid} in {path}")
            if uid not in seen_uids:
                raise AssertionError(f"legacy fit uid {uid} has no reviewed source")
            source = draft[uid]["jp"]
            if not translated.strip():
                raise AssertionError(
                    f"empty legacy fit translation at {path.name}:{line_number}"
                )
            if source.count("/") != translated.count("/"):
                raise AssertionError(
                    f"legacy fit slash mismatch at {path.name}:{line_number}"
                )
            overrides[source] = translated
            legacy_seen.add(uid)

    # Final terminology normalization.  These are Fury proper names and
    # organization ranks, not mathematical separators or ordinary Korean
    # nouns.  Apply this after every legacy fit overlay so an older compact
    # row cannot reintroduce the obsolete spellings.
    for source, translated in list(overrides.items()):
        overrides[source] = (
            translated
            .replace(load_table("_INLINE")[26], load_table("_INLINE")[27])
            .replace(load_table("_INLINE")[24], load_table("_INLINE")[25])
            .replace(load_table("_INLINE")[22], load_table("_INLINE")[23])
            .replace(load_table("_INLINE")[20], load_table("_INLINE")[21])
            .replace(load_table("_INLINE")[18], load_table("_INLINE")[19])
            .replace(load_table("_INLINE")[16], load_table("_INLINE")[17])
            .replace(load_table("_INLINE")[14], load_table("_INLINE")[15])
            .replace(load_table("_INLINE")[12], load_table("_INLINE")[13])
            .replace(load_table("_INLINE")[10], load_table("_INLINE")[11])
            .replace(load_table("_INLINE")[8], load_table("_INLINE")[9])
            .replace(load_table("_INLINE")[6], load_table("_INLINE")[7])
            .replace(load_table("_INLINE")[4], load_table("_INLINE")[5])
            .replace(load_table("_INLINE")[1], load_table("_INLINE")[2])
        )
    return overrides


def main() -> None:
    root = Path("work_ogmd")
    build = root / "korean_build_v5"
    source = root / "original_backups" / "Battle.psarc.sdat.orig"
    output = build / "Battle_safe_full.psarc.sdat"
    mapping = load_map(build)
    translations = {row["jp"]: row["ko"] for row in (
        json.loads(line) for line in (root / "battle_translation" / "battle_unique_draft.jsonl").read_text(encoding="utf-8").splitlines()
    )}
    parallel_reviews = load_parallel_review_overrides(root)
    master = [json.loads(line) for line in (root / "extract_bmd" / "master.jsonl").read_text(encoding="utf-8").splitlines()]
    source_file = source.open("rb")
    original_header = source_file.read(0x100)
    reader = SDATReader(source_file, 0)
    psarc = PSARC(reader)
    name_to_entry = {name: index + 1 for index, name in enumerate(psarc.manifest())}
    grouped = defaultdict(list)
    for row in master:
        grouped[name_to_entry[row["file"]]].append(row)

    modified, stats = {}, defaultdict(int)
    for entry, rows in grouped.items():
        original = psarc.read_entry(entry)
        bmd = BmdFile(original)
        replacements = {}
        for row in rows:
            stats["total"] += 1
            if row["idx"] >= len(bmd.records) or bmd.texts()[row["idx"]] != row["jp"]:
                stats["source_mismatch"] += 1; continue
            translated = parallel_reviews.get(
                row["jp"],
                BATTLE_REVIEW_OVERRIDES.get(
                    row["jp"],
                    BATTLE_OVERRIDES.get(row["jp"], translations[row["jp"]]),
                ),
            )
            translated = normalize_battle_text(translated)
            raw = prepare_dialogue(
                translated,
                mapping,
                row["jp"],
            )
            if raw is None:
                stats["skipped_unfit"] += 1; continue
            replacements[row["idx"]] = raw.decode("utf-8")
        if replacements:
            changed = bmd.replace_variable(replacements)
            modified[entry] = changed
            stats["candidate"] += len(replacements)
    raw_psarc = output.with_suffix(".psarc")
    rebuild_var(str(root / "BATTLE.psarc"), modified, str(raw_psarc))
    encode_sdat(str(raw_psarc), original_header, str(output))
    source_file.close()
    print(json.dumps({**stats, "modified_entries": len(modified), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
