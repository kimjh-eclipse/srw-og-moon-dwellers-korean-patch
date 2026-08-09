#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a size-preserving Battle dialogue PoC without a huge plain PSARC."""

from __future__ import annotations

import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import csv
import hashlib
import json
import struct
import sys
from pathlib import Path

from Crypto.Cipher import AES

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import be_n, block_byte_positions, compress_blocks, entry_nblocks
from sdat import EDAT_KEY_1, SDAT_KEY, SDATReader, parse_header
from sdat_encode import forge_metadata


TARGET_FILE = "/Dat/Battle/Message/@Ja/0118_ja.bmd"
TARGET_INDEX = 5
TARGET_JP = load_table('TARGET_JP')
TARGET_KO = load_table('TARGET_KO')


def load_proxy_map(build: Path) -> dict[str, str]:
    result = {}
    for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
        path = build / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                result[row["hangul"]] = row["proxy"]
    return result


def proxy_text(text: str, mapping: dict[str, str]) -> str:
    output = "".join(mapping.get(ch, ch) for ch in text)
    missing = [
        ch
        for ch in output
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F
    ]
    if missing:
        raise ValueError(f"missing Korean proxies: {sorted(set(missing))}")
    return output


def encode_chunks(
    chunks,
    plain_size: int,
    original_header: bytes,
    output_path: Path,
) -> None:
    h = parse_header(original_header)
    block_size = h["block_size"]
    dev = h["dev_hash"]
    digest = h["digest"]
    crypt_key = bytes(a ^ b for a, b in zip(dev, SDAT_KEY))
    total = (plain_size + block_size - 1) // block_size
    header = bytearray(original_header)
    header[0x88:0x90] = struct.pack(">Q", plain_size)

    pending = bytearray()
    written_plain = 0
    block_number = 0
    with output_path.open("wb") as output:
        output.write(header)
        for chunk in chunks:
            pending.extend(chunk)
            while len(pending) >= block_size:
                block = bytes(pending[:block_size])
                del pending[:block_size]
                block_key = dev[:12] + struct.pack(">I", block_number)
                key_result = AES.new(
                    crypt_key, AES.MODE_ECB
                ).encrypt(block_key)
                key_final = AES.new(
                    EDAT_KEY_1, AES.MODE_ECB
                ).decrypt(key_result)
                cipher = AES.new(
                    key_final, AES.MODE_CBC, digest
                ).encrypt(block)
                output.write(
                    forge_metadata(cipher, crypt_key, dev, block_number)
                )
                output.write(cipher)
                written_plain += len(block)
                block_number += 1
                if block_number % 10000 == 0:
                    print(
                        f"encoded {block_number}/{total} SDAT blocks",
                        flush=True,
                    )
        if pending:
            length = len(pending)
            padded = bytes(pending) + b"\0" * ((-length) & 15)
            block_key = dev[:12] + struct.pack(">I", block_number)
            key_result = AES.new(crypt_key, AES.MODE_ECB).encrypt(block_key)
            key_final = AES.new(EDAT_KEY_1, AES.MODE_ECB).decrypt(key_result)
            cipher = AES.new(key_final, AES.MODE_CBC, digest).encrypt(padded)
            output.write(
                forge_metadata(cipher, crypt_key, dev, block_number)
            )
            output.write(cipher)
            written_plain += length
            block_number += 1
    if written_plain != plain_size or block_number != total:
        raise AssertionError(
            f"stream size mismatch: {written_plain}/{plain_size}, "
            f"blocks {block_number}/{total}"
        )


def main() -> None:
    root = Path("work_ogmd")
    build = root / "korean_build_v3"
    installed_sdat = Path(config.game_file("Battle.psarc.sdat"))
    backup_sdat = root / "original_backups" / "Battle.psarc.sdat.orig"
    source_sdat = backup_sdat if backup_sdat.exists() else installed_sdat
    output_sdat = build / "Battle_dialogue_poc.psarc.sdat"
    mapping = load_proxy_map(build)

    source_file = source_sdat.open("rb")
    original_header = source_file.read(0x100)
    reader = SDATReader(source_file, 0)
    psarc = PSARC(reader)
    names = psarc.manifest()
    entry = names.index(TARGET_FILE) + 1
    original_entry = psarc.read_entry(entry)
    bmd = BmdFile(original_entry)
    if bmd.texts()[TARGET_INDEX] != TARGET_JP:
        raise AssertionError(
            f"unexpected source: {bmd.texts()[TARGET_INDEX]!r}"
        )
    encoded_ko = proxy_text(TARGET_KO, mapping)
    modified_entry, truncated = bmd.replace({TARGET_INDEX: encoded_ko})
    if truncated:
        raise AssertionError("Battle PoC translation was truncated")

    positions = block_byte_positions(psarc)
    new_csize = list(psarc.block_table)
    changed_blobs = {}
    psarc_entry = psarc.entries[entry]
    block_index = psarc_entry["block_idx"]
    block_count = entry_nblocks(psarc, entry)
    for local_block in range(block_count):
        start = local_block * psarc.block_size
        old_chunk = original_entry[start : start + psarc.block_size]
        new_chunk = modified_entry[start : start + psarc.block_size]
        if old_chunk == new_chunk:
            continue
        csizes, blobs = compress_blocks(new_chunk, psarc.block_size)
        changed_blobs[block_index + local_block] = blobs[0]
        new_csize[block_index + local_block] = csizes[0]

    data_start = psarc.toc_len
    block_offsets = []
    offset = data_start
    for block, csize in enumerate(new_csize):
        block_offsets.append(offset)
        if block in changed_blobs:
            offset += len(changed_blobs[block])
        else:
            _old_offset, old_csize = positions[block]
            offset += old_csize if old_csize else psarc.block_size
    rebuilt_size = offset
    if rebuilt_size > reader.fs:
        raise ValueError(
            f"rebuilt PSARC exceeds original: {rebuilt_size} > {reader.fs}"
        )

    reader.seek(0)
    header = reader.read(32)
    toc = bytearray()
    for item in psarc.entries:
        toc += item["md5"]
        toc += struct.pack(">I", item["block_idx"])
        toc += be_n(item["orig_size"], 5)
        toc += be_n(block_offsets[item["block_idx"]], 5)
    block_table = b"".join(be_n(size, psarc.bw) for size in new_csize)
    body = header + bytes(toc) + block_table
    if len(body) != data_start:
        raise AssertionError(f"TOC size mismatch: {len(body)} != {data_start}")

    def rebuilt_chunks():
        yield body
        for block in range(len(new_csize)):
            if block in changed_blobs:
                yield changed_blobs[block]
            else:
                old_offset, old_csize = positions[block]
                size = old_csize if old_csize else psarc.block_size
                reader.seek(old_offset)
                yield reader.read(size)
        if rebuilt_size < reader.fs:
            yield b"\0" * (reader.fs - rebuilt_size)

    encode_chunks(rebuilt_chunks(), reader.fs, original_header, output_sdat)
    source_file.close()
    source_size = source_sdat.stat().st_size
    output_size = output_sdat.stat().st_size
    if output_size > source_size:
        raise ValueError(
            f"encoded SDAT exceeds original: {output_size} > {source_size}"
        )
    if output_size < source_size:
        with output_sdat.open("ab") as stream:
            stream.write(b"\0" * (source_size - output_size))

    with output_sdat.open("rb") as stream:
        check_psarc = PSARC(SDATReader(stream, 0))
        check_bmd = BmdFile(check_psarc.read_entry(entry))
        actual = check_bmd.texts()[TARGET_INDEX]
    if actual != encoded_ko:
        raise AssertionError(f"readback mismatch: {actual!r}")
    digest = hashlib.sha256()
    with output_sdat.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    print(json.dumps(
        {
            "entry": entry,
            "file": TARGET_FILE,
            "index": TARGET_INDEX,
            "jp": TARGET_JP,
            "ko": TARGET_KO,
            "changed_blocks": len(changed_blobs),
            "plain_size": reader.fs,
            "rebuilt_size_before_padding": rebuilt_size,
            "sdat_size": output_sdat.stat().st_size,
            "sha256": digest.hexdigest(),
        },
        ensure_ascii=True,
        indent=2,
    ))


if __name__ == "__main__":
    main()
