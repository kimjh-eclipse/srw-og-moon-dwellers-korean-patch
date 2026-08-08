#!/usr/bin/env python3
"""Replace PSARC entries while preserving every entry's physical span."""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

from psarc import PSARC
from psarc_write import be_n, block_byte_positions, entry_nblocks


def rebuild_fixed_entry_spans(source: Path, modified: dict[int, bytes], output: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).with_name("vendor")))
    from zopfli.zlib import compress

    archive = PSARC(str(source))
    raw = bytearray(source.read_bytes())
    positions = block_byte_positions(archive)
    new_table = list(archive.block_table)
    changed_blocks = 0
    redistributed_entries = 0
    padding_bytes = 0

    for entry, new_data in sorted(modified.items()):
        info = archive.entries[entry]
        if len(new_data) != info["orig_size"]:
            raise ValueError(f"entry {entry} size changed")
        old_data = archive.read_entry(entry)
        count = entry_nblocks(archive, entry)
        first = info["block_idx"]
        capacities = [archive.block_table[first + i] or archive.block_size for i in range(count)]
        span_start = positions[first][0]
        span_size = sum(capacities)
        blobs: list[bytearray] = []
        changed: list[int] = []

        for local in range(count):
            start = local * archive.block_size
            old_chunk = old_data[start : start + archive.block_size]
            new_chunk = new_data[start : start + archive.block_size]
            block_index = first + local
            physical_offset, _ = positions[block_index]
            if old_chunk == new_chunk:
                blobs.append(bytearray(raw[physical_offset : physical_offset + capacities[local]]))
                continue
            candidate = compress(new_chunk, numiterations=5)
            if len(candidate) >= len(new_chunk):
                candidate = new_chunk
            if candidate[:1] == b"\x78" and zlib.decompress(candidate) != new_chunk:
                raise AssertionError(f"entry {entry} block {local} compression mismatch")
            blobs.append(bytearray(candidate))
            changed.append(local)
            changed_blocks += 1

        spare = span_size - sum(len(blob) for blob in blobs)
        if spare < 0:
            raise ValueError(f"entry {entry} span overflow by {-spare} bytes")
        original_changed_sizes = [capacities[i] for i in changed]
        for local in reversed(changed):
            room = archive.block_size - len(blobs[local])
            add = min(spare, room)
            if add:
                blobs[local].extend(b"\0" * add)
                spare -= add
                padding_bytes += add
            if not spare:
                break
        if spare:
            raise ValueError(f"entry {entry} cannot place {spare} padding bytes")

        for local in changed:
            size = len(blobs[local])
            if size > archive.block_size:
                raise AssertionError("block physical size exceeds block size")
            new_table[first + local] = 0 if size == archive.block_size else size
        if [new_table[first + i] or archive.block_size for i in changed] != original_changed_sizes:
            redistributed_entries += 1

        packed = b"".join(bytes(blob) for blob in blobs)
        if len(packed) != span_size:
            raise AssertionError(f"entry {entry} span size changed")
        raw[span_start : span_start + span_size] = packed

    table_offset = 32 + archive.n * archive.ent_size
    encoded_table = b"".join(be_n(value, archive.bw) for value in new_table)
    raw[table_offset : table_offset + len(encoded_table)] = encoded_table
    output.write_bytes(raw)

    check = PSARC(str(output))
    if output.stat().st_size != source.stat().st_size:
        raise AssertionError("PSARC size changed")
    for entry, expected in modified.items():
        if check.read_entry(entry) != expected:
            raise AssertionError(f"entry {entry} readback mismatch")
    return {
        "changed_blocks": changed_blocks,
        "redistributed_entries": redistributed_entries,
        "zlib_padding_bytes": padding_bytes,
        "block_overflows": 0,
        "entry_offsets_identical": True,
        "psarc_size_identical": True,
    }
