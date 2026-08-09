#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the single reviewed Granteed battle line on the known-good C117 SDAT.

This builder deliberately does not install anything.  It preserves the BMD
record span, the PSARC logical size, the SDAT header, the physical SDAT size,
and the source timestamp.  It aborts unless the exact known-good C117 source
is present.
"""
from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import rebuild
from sdat import SDATReader, SDAT_KEY, decrypt_stream, parse_header
from sdat_encode import encode as encode_sdat, forge_metadata


SOURCE_SHA256 = "c1174d684d7524f4bd791d84d4a7eba4b09e22b61406b53f8d3dbfa8bdfafbf9"
SOURCE_SIZE = 1_729_186_848
PLAIN_SIZE = 1_725_815_820
TARGET_FILE = "/Dat/Battle/Message/@Ja/0118_ja.bmd"
TARGET_INDEX = 8
TARGET_JP_PREFIX = load_table('TARGET_JP_PREFIX')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_translation_builder(root: Path):
    path = root / "32_build_battle_safe_full.py"
    spec = importlib.util.spec_from_file_location("battle_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def psarc_data_end(archive: PSARC) -> int:
    return archive.toc_len + sum(
        size if size else archive.block_size for size in archive.block_table
    )


def verify_sdat_blocks_and_plain_hash(path: Path) -> tuple[int, str]:
    """Validate every canonical C117 block hash and hash decrypted plaintext."""
    with path.open("rb") as stream:
        header = stream.read(0x100)
        info = parse_header(header)
        block_size = info["block_size"]
        file_size = info["file_size"]
        total = (file_size + block_size - 1) // block_size
        crypt_key = bytes(
            left ^ right for left, right in zip(info["dev_hash"], SDAT_KEY)
        )
        bad_metadata = 0
        for number in range(total):
            metadata = stream.read(0x20)
            if number == total - 1:
                plain_length = file_size - block_size * (total - 1)
                cipher_length = (plain_length + 15) & ~15
            else:
                cipher_length = block_size
            cipher = stream.read(cipher_length)
            expected = forge_metadata(
                cipher, crypt_key, info["dev_hash"], number
            )
            bad_metadata += metadata != expected

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        reader = SDATReader(stream, 0)
        while True:
            chunk = reader.read(8 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return bad_metadata, digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    build = root / "korean_build_v5"
    source = root / "installed_backups" / "Battle.psarc.sdat.before_v5_20260726"
    base_psarc = build / "Battle_stable_C117_base.psarc"
    output_psarc = build / "Battle_C117_granteed_override.psarc"
    output_sdat = build / "Battle_C117_granteed_override.psarc.sdat"
    report_path = build / "battle_c117_granteed_override_report.json"

    source_stat = source.stat()
    if source_stat.st_size != SOURCE_SIZE or sha256(source) != SOURCE_SHA256:
        raise AssertionError("known-good C117 Battle source is absent or changed")
    source_header = source.read_bytes()[:0x100]
    header_info = parse_header(source_header)
    if header_info["file_size"] != PLAIN_SIZE:
        raise AssertionError(f"unexpected source logical size: {header_info['file_size']}")

    if not base_psarc.exists() or base_psarc.stat().st_size != PLAIN_SIZE:
        with source.open("rb") as src, base_psarc.open("wb") as dst:
            written, _ = decrypt_stream(src, 0, dst)
        if written != PLAIN_SIZE:
            raise AssertionError(f"decoded {written}, expected {PLAIN_SIZE}")

    builder = load_translation_builder(root)
    target_jp = next(
        key
        for key in builder.BATTLE_REVIEW_OVERRIDES
        if key.startswith(TARGET_JP_PREFIX)
    )
    target_ko = builder.BATTLE_REVIEW_OVERRIDES[target_jp]
    mapping = builder.load_map(build)
    prepared = builder.prepare_dialogue(
        builder.normalize_battle_text(target_ko), mapping, target_jp
    )
    if prepared is None:
        raise AssertionError("reviewed line cannot be represented by the V5 font map")
    prepared_text = prepared.decode("utf-8")

    base = PSARC(str(base_psarc))
    names = base.manifest()
    target_entry = names.index(TARGET_FILE) + 1
    original_entry = base.read_entry(target_entry)
    bmd = BmdFile(original_entry)
    if TARGET_INDEX >= len(bmd.records):
        raise AssertionError("target BMD record index is absent")
    old_text = bmd.texts()[TARGET_INDEX]
    span = bmd.records[TARGET_INDEX][1]
    prepared_size = len(prepared) + 1
    if prepared_size > span:
        raise AssertionError(
            f"reviewed line does not fit in-place: {prepared_size} > {span}"
        )
    changed_entry, truncated = bmd.replace({TARGET_INDEX: prepared_text})
    if truncated or len(changed_entry) != len(original_entry):
        raise AssertionError("in-place BMD replacement changed size or truncated")
    check_bmd = BmdFile(changed_entry, pool_start=bmd.pool_start)
    if check_bmd.texts()[TARGET_INDEX] != prepared_text:
        raise AssertionError("BMD replacement readback mismatch")

    rebuilt_size = rebuild(
        str(base_psarc), {target_entry: changed_entry}, str(output_psarc)
    )
    if rebuilt_size > PLAIN_SIZE:
        raise AssertionError(
            f"rebuilt PSARC exceeds source budget: {rebuilt_size} > {PLAIN_SIZE}"
        )
    # PSARC readers use TOC entry sizes and offsets; bytes after the final
    # entry are ignored.  Restore the source logical length without altering
    # any archive address or compressed stream.
    with output_psarc.open("ab") as stream:
        stream.write(b"\0" * (PLAIN_SIZE - rebuilt_size))
    if output_psarc.stat().st_size != PLAIN_SIZE:
        raise AssertionError("PSARC logical size preservation failed")

    encode_sdat(str(output_psarc), source_header, str(output_sdat))
    encoded_size = output_sdat.stat().st_size
    if encoded_size > SOURCE_SIZE:
        raise AssertionError(f"encoded SDAT exceeds source size: {encoded_size}")
    # The retail container carries a 16-byte trailer outside the block layout.
    # C117's accepted trailer is all zero; copy it verbatim.
    trailer_size = SOURCE_SIZE - encoded_size
    with source.open("rb") as src:
        src.seek(-trailer_size, os.SEEK_END)
        trailer = src.read(trailer_size)
    with output_sdat.open("ab") as dst:
        dst.write(trailer)
    os.utime(
        output_sdat,
        ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
    )

    out_header = output_sdat.read_bytes()[:0x100]
    if out_header != source_header:
        raise AssertionError("SDAT header changed")
    if output_sdat.stat().st_size != SOURCE_SIZE:
        raise AssertionError("physical SDAT size changed")

    # Full encrypted-container readback and PSARC structural validation.
    with output_sdat.open("rb") as encrypted:
        reader = SDATReader(encrypted, 0)
        decoded = PSARC(reader)
        if (
            decoded.n != base.n
            or decoded.block_size != base.block_size
            or decoded.manifest() != names
        ):
            raise AssertionError("PSARC structure or manifest changed")
        decoded_entry = decoded.read_entry(target_entry)
        decoded_bmd = BmdFile(decoded_entry, pool_start=bmd.pool_start)
        if decoded_bmd.texts()[TARGET_INDEX] != prepared_text:
            raise AssertionError("encrypted SDAT target readback mismatch")
        if len(decoded_entry) != len(original_entry):
            raise AssertionError("target entry size changed")

    built = PSARC(str(output_psarc))
    if len(built.block_table) != len(base.block_table):
        raise AssertionError("PSARC block count changed")
    if any(
        (old["block_idx"], old["orig_size"])
        != (new["block_idx"], new["orig_size"])
        for old, new in zip(base.entries, built.entries)
    ):
        raise AssertionError("entry block index or logical size changed")
    changed_entries = []
    for index in range(base.n):
        if base.read_entry(index) != built.read_entry(index):
            changed_entries.append(index)
    if changed_entries != [target_entry]:
        raise AssertionError(f"unexpected changed entries: {changed_entries}")

    bad_block_metadata, decoded_plain_sha256 = verify_sdat_blocks_and_plain_hash(
        output_sdat
    )
    output_plain_sha256 = sha256(output_psarc)
    if bad_block_metadata:
        raise AssertionError(f"{bad_block_metadata} invalid SDAT block hashes")
    if decoded_plain_sha256 != output_plain_sha256:
        raise AssertionError("full SDAT decrypted readback differs from output PSARC")

    changed_block_table_indices = [
        index
        for index, (old, new) in enumerate(
            zip(base.block_table, built.block_table)
        )
        if old != new
    ]
    changed_entry_offsets = [
        index
        for index, (old, new) in enumerate(zip(base.entries, built.entries))
        if old["offset"] != new["offset"]
    ]

    report = {
        "source": str(source),
        "source_sha256": SOURCE_SHA256,
        "source_size": SOURCE_SIZE,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "source_header_sha256": hashlib.sha256(source_header).hexdigest(),
        "base_plain_sha256": sha256(base_psarc),
        "output": str(output_sdat),
        "output_sha256": sha256(output_sdat),
        "output_size": output_sdat.stat().st_size,
        "output_mtime_ns": output_sdat.stat().st_mtime_ns,
        "output_header_sha256": hashlib.sha256(out_header).hexdigest(),
        "output_plain_sha256": output_plain_sha256,
        "decoded_plain_sha256": decoded_plain_sha256,
        "psarc_rebuilt_size_before_tail_padding": rebuilt_size,
        "psarc_tail_padding": PLAIN_SIZE - rebuilt_size,
        "base_psarc_data_end": psarc_data_end(base),
        "output_psarc_data_end": psarc_data_end(built),
        "sdat_trailer_size": trailer_size,
        "entry_count": base.n,
        "block_count": len(base.block_table),
        "changed_entries": changed_entries,
        "changed_block_table_indices": changed_block_table_indices,
        "changed_entry_offset_count": len(changed_entry_offsets),
        "invalid_sdat_block_hashes": bad_block_metadata,
        "target_entry": target_entry,
        "target_file": TARGET_FILE,
        "target_index": TARGET_INDEX,
        "target_span": span,
        "replacement_size_with_nul": prepared_size,
        "old_proxy_text": old_text,
        "new_korean_text": target_ko,
        "new_proxy_text": prepared_text,
        "checks": {
            "known_good_source_hash": True,
            "header_byte_identical": True,
            "physical_size_identical": True,
            "mtime_identical": output_sdat.stat().st_mtime_ns
            == source_stat.st_mtime_ns,
            "bmd_in_place_no_truncation": True,
            "psarc_structure_readback": True,
            "encrypted_target_readback": True,
            "only_target_entry_changed": changed_entries == [target_entry],
            "all_sdat_block_hashes_valid": bad_block_metadata == 0,
            "full_decrypted_plaintext_matches": decoded_plain_sha256
            == output_plain_sha256,
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
