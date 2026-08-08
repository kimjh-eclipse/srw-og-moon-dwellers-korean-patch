from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
load_table("_INLINE")[0]
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import enable_zopfli, rebuild
from sdat import SDATReader, parse_header
from sdat_encode import encode as encode_sdat


SOURCE_SHA256 = "c1174d684d7524f4bd791d84d4a7eba4b09e22b61406b53f8d3dbfa8bdfafbf9"
SOURCE_SIZE = 1_729_186_848
PLAIN_SIZE = 1_725_815_820

JP_GRANTEED = (
    load_table("_INLINE")[1]
)
JP_GO = load_table("_INLINE")[2]
JP_COUNTER = load_table("_INLINE")[3]
JP_ESELDA_SHORT = load_table('JP_ESELDA_SHORT')
JP_ESELDA_LONG = load_table('JP_ESELDA_LONG')

# Optional exact-location additions for later independently reviewed groups.
# Values are (expected Japanese source, reviewed Korean).
SPECIFIC_PATCHES: dict[tuple[str, int], tuple[str, str]] = {}
OUTPUT_STEM = "Battle_C117_manual_v3"
REPORT_NAME = "battle_c117_manual_v3_report.json"
REVIEW_GROUP = "manual_v3"
BASE_PSARC_OVERRIDE: Path | None = None
USE_ZOPFLI = False
INCLUDE_DEFAULT_TRANSLATIONS = True


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = Path(__file__).resolve().parent
    build = root / "korean_build_v5"
    source = root / "installed_backups" / "Battle.psarc.sdat.before_v5_20260726"
    base_psarc = BASE_PSARC_OVERRIDE or (build / "Battle_stable_C117_base.psarc")
    output_psarc = build / f"{OUTPUT_STEM}.psarc"
    output_sdat = build / f"{OUTPUT_STEM}.psarc.sdat"
    report_path = build / REPORT_NAME

    if USE_ZOPFLI:
        enable_zopfli()

    safety = load_module(root / "40_build_battle_c117_override.py", "safety")
    builder = load_module(root / "32_build_battle_safe_full.py", "builder")
    source_stat = source.stat()
    if (
        source_stat.st_size != SOURCE_SIZE
        or safety.sha256(source) != SOURCE_SHA256
    ):
        raise AssertionError("known-good C117 Battle source is absent or changed")
    source_header = source.read_bytes()[:0x100]
    if parse_header(source_header)["file_size"] != PLAIN_SIZE:
        raise AssertionError("known-good C117 logical size changed")
    if base_psarc.stat().st_size != PLAIN_SIZE:
        raise AssertionError("decoded C117 base PSARC is absent or changed")

    translations = (
        {
            JP_GRANTEED: builder.BATTLE_REVIEW_OVERRIDES[JP_GRANTEED],
            JP_GO: builder.BATTLE_REVIEW_OVERRIDES[JP_GO],
            JP_COUNTER: builder.BATTLE_REVIEW_OVERRIDES[JP_COUNTER],
            JP_ESELDA_SHORT: builder.BATTLE_REVIEW_OVERRIDES[JP_ESELDA_SHORT],
            JP_ESELDA_LONG: builder.BATTLE_REVIEW_OVERRIDES[JP_ESELDA_LONG],
        }
        if INCLUDE_DEFAULT_TRANSLATIONS
        else {}
    )
    mapping = builder.load_map(build)
    master = [
        json.loads(line)
        for line in (root / "extract_bmd" / "master.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    selected = [
        row
        for row in master
        if row["jp"] in translations
        or (row["file"], row["idx"]) in SPECIFIC_PATCHES
    ]
    for row in selected:
        key = (row["file"], row["idx"])
        if key in SPECIFIC_PATCHES and row["jp"] != SPECIFIC_PATCHES[key][0]:
            raise AssertionError(
                f"specific source mismatch at {row['file']}#{row['idx']}"
            )
    counts = defaultdict(int)
    for row in selected:
        if row["jp"] in translations:
            counts[row["jp"]] += 1
    expected_counts = {
        JP_GRANTEED: 1,
        JP_GO: 2,
        JP_COUNTER: 12,
        JP_ESELDA_SHORT: 1,
        JP_ESELDA_LONG: 1,
    }
    if INCLUDE_DEFAULT_TRANSLATIONS and dict(counts) != expected_counts:
        raise AssertionError(f"unexpected source occurrence counts: {dict(counts)}")

    base = PSARC(str(base_psarc))
    names = base.manifest()
    name_to_entry = {name: index + 1 for index, name in enumerate(names)}
    grouped = defaultdict(list)
    for row in selected:
        grouped[name_to_entry[row["file"]]].append(row)

    modified = {}
    replacement_report = []
    expected_readback = {}
    for entry, rows in grouped.items():
        original_entry = base.read_entry(entry)
        bmd = BmdFile(original_entry)
        replacements = {}
        for row in rows:
            jp = row["jp"]
            specific = SPECIFIC_PATCHES.get((row["file"], row["idx"]))
            ko = specific[1] if specific else translations[jp]
            if specific:
                raw = builder.encode(ko, mapping)
            elif jp == JP_GRANTEED:
                raw = builder.prepare_dialogue(
                    builder.normalize_battle_text(ko), mapping, jp
                )
            else:
                # These short commands/status messages are deliberately
                # unquoted.  This is both natural in the game's dialogue box
                # and comfortably inside the original fixed spans.
                raw = builder.encode(ko, mapping)
            if raw is None:
                raise AssertionError(f"font map cannot encode {ko!r}")
            index = row["idx"]
            span = bmd.records[index][1]
            size_with_nul = len(raw) + 1
            if size_with_nul > span:
                raise AssertionError(
                    f"{row['file']}#{index}: {size_with_nul} > {span}"
                )
            proxy = raw.decode("utf-8")
            replacements[index] = proxy
            expected_readback[(entry, index)] = proxy
            replacement_report.append(
                {
                    "entry": entry,
                    "file": row["file"],
                    "index": index,
                    "jp": jp,
                    "ko": ko,
                    "old_proxy": bmd.texts()[index],
                    "new_proxy": proxy,
                    "span": span,
                    "replacement_size_with_nul": size_with_nul,
                }
            )
        changed, truncated = bmd.replace(replacements)
        if truncated or len(changed) != len(original_entry):
            raise AssertionError(f"entry {entry}: truncated or changed BMD size")
        checked = BmdFile(changed, pool_start=bmd.pool_start)
        for index, proxy in replacements.items():
            if checked.texts()[index] != proxy:
                raise AssertionError(f"entry {entry}#{index}: local readback failed")
        modified[entry] = changed

    rebuilt_size = rebuild(str(base_psarc), modified, str(output_psarc))
    if rebuilt_size > PLAIN_SIZE:
        raise AssertionError(f"rebuilt PSARC exceeds C117: {rebuilt_size}")
    with output_psarc.open("ab") as stream:
        stream.write(b"\0" * (PLAIN_SIZE - rebuilt_size))

    encode_sdat(str(output_psarc), source_header, str(output_sdat))
    trailer_size = SOURCE_SIZE - output_sdat.stat().st_size
    if trailer_size < 0:
        raise AssertionError("encoded SDAT exceeds C117")
    with source.open("rb") as src:
        src.seek(-trailer_size, os.SEEK_END)
        trailer = src.read(trailer_size)
    with output_sdat.open("ab") as dst:
        dst.write(trailer)
    os.utime(output_sdat, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

    if output_sdat.stat().st_size != SOURCE_SIZE:
        raise AssertionError("physical SDAT size changed")
    if output_sdat.read_bytes()[:0x100] != source_header:
        raise AssertionError("SDAT header changed")

    built = PSARC(str(output_psarc))
    if (
        built.n != base.n
        or len(built.block_table) != len(base.block_table)
        or built.manifest() != names
    ):
        raise AssertionError("PSARC structure changed")
    if any(
        (old["block_idx"], old["orig_size"])
        != (new["block_idx"], new["orig_size"])
        for old, new in zip(base.entries, built.entries)
    ):
        raise AssertionError("entry index or logical size changed")

    changed_entries = [
        index
        for index in range(base.n)
        if base.read_entry(index) != built.read_entry(index)
    ]
    expected_entries = sorted(modified)
    if changed_entries != expected_entries:
        raise AssertionError(f"unexpected changed entries: {changed_entries}")

    bad_metadata, decoded_plain_sha256 = safety.verify_sdat_blocks_and_plain_hash(
        output_sdat
    )
    output_plain_sha256 = safety.sha256(output_psarc)
    if bad_metadata or decoded_plain_sha256 != output_plain_sha256:
        raise AssertionError("SDAT block hash or full decrypted readback failed")

    with output_sdat.open("rb") as encrypted:
        decoded = PSARC(SDATReader(encrypted, 0))
        readback_by_entry = defaultdict(dict)
        for (entry, index), proxy in expected_readback.items():
            readback_by_entry[entry][index] = proxy
        for entry, expected in readback_by_entry.items():
            check = BmdFile(decoded.read_entry(entry))
            texts = check.texts()
            for index, proxy in expected.items():
                if texts[index] != proxy:
                    raise AssertionError(
                        f"encrypted readback failed: {entry}#{index}"
                    )

    changed_block_table_indices = [
        index
        for index, (old, new) in enumerate(
            zip(base.block_table, built.block_table)
        )
        if old != new
    ]
    report = {
        "review_group": REVIEW_GROUP,
        "source_sha256": SOURCE_SHA256,
        "source_size": SOURCE_SIZE,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "source_header_sha256": hashlib.sha256(source_header).hexdigest(),
        "output": str(output_sdat),
        "output_sha256": safety.sha256(output_sdat),
        "output_size": output_sdat.stat().st_size,
        "output_mtime_ns": output_sdat.stat().st_mtime_ns,
        "output_header_sha256": hashlib.sha256(source_header).hexdigest(),
        "output_plain_sha256": output_plain_sha256,
        "decoded_plain_sha256": decoded_plain_sha256,
        "psarc_rebuilt_size_before_tail_padding": rebuilt_size,
        "psarc_tail_padding": PLAIN_SIZE - rebuilt_size,
        "sdat_trailer_size": trailer_size,
        "entry_count": base.n,
        "block_count": len(base.block_table),
        "changed_entries": changed_entries,
        "changed_block_table_indices": changed_block_table_indices,
        "invalid_sdat_block_hashes": bad_metadata,
        "replacement_count": len(replacement_report),
        "replacements": replacement_report,
        "checks": {
            "known_good_source_hash": True,
            "header_byte_identical": True,
            "physical_size_identical": True,
            "mtime_identical": output_sdat.stat().st_mtime_ns
            == source_stat.st_mtime_ns,
            "all_bmd_replacements_in_place_no_truncation": True,
            "only_selected_entries_changed": True,
            "all_sdat_block_hashes_valid": bad_metadata == 0,
            "full_decrypted_plaintext_matches": decoded_plain_sha256
            == output_plain_sha256,
            "encrypted_record_readback": True,
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
