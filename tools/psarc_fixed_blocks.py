#!/usr/bin/env python3
"""Replace PSARC blocks without changing the TOC, block table, or offsets."""

from __future__ import annotations

import zlib
from pathlib import Path

from psarc import PSARC
from psarc_write import block_byte_positions, compress_blocks, enable_zopfli, entry_nblocks


def rebuild_fixed_blocks(source: str | Path, modified: dict[int, bytes], output: str | Path) -> dict:
    """Recompress changed blocks into their existing physical byte spans.

    A shorter zlib stream is padded after its end marker.  zlib permits
    trailing bytes, while keeping the PSARC block table and every later entry
    offset byte-identical to the boot-tested source archive.
    """

    source = Path(source)
    output = Path(output)
    archive = PSARC(str(source))
    raw = bytearray(source.read_bytes())
    positions = block_byte_positions(archive)
    enable_zopfli()

    changed_blocks = 0
    padded_bytes = 0
    overflows = []
    for entry, new_data in sorted(modified.items()):
        info = archive.entries[entry]
        if len(new_data) != info["orig_size"]:
            raise ValueError(
                f"entry {entry} size changed: {len(new_data)} != {info['orig_size']}"
            )
        old_data = archive.read_entry(entry)
        block_count = entry_nblocks(archive, entry)
        for local in range(block_count):
            start = local * archive.block_size
            new_chunk = new_data[start : start + archive.block_size]
            old_chunk = old_data[start : start + archive.block_size]
            if new_chunk == old_chunk:
                continue
            block_index = info["block_idx"] + local
            physical_offset, table_size = positions[block_index]
            physical_size = table_size if table_size else archive.block_size

            if table_size == 0:
                blob = new_chunk
            else:
                sizes, blobs = compress_blocks(new_chunk, archive.block_size)
                blob = blobs[0]
                if sizes[0] == 0:
                    blob = new_chunk
            if len(blob) > physical_size:
                overflows.append(
                    {
                        "entry": entry,
                        "local_block": local,
                        "block_index": block_index,
                        "capacity": physical_size,
                        "compressed": len(blob),
                        "overflow": len(blob) - physical_size,
                    }
                )
                continue

            if table_size:
                decoded = zlib.decompress(blob)
                if decoded != new_chunk:
                    raise AssertionError(f"compressed block {block_index} readback mismatch")
            padding = physical_size - len(blob)
            raw[physical_offset : physical_offset + physical_size] = blob + b"\0" * padding
            changed_blocks += 1
            padded_bytes += padding

    if overflows:
        details = ", ".join(
            f"entry {row['entry']} block {row['local_block']} +{row['overflow']}"
            for row in overflows
        )
        raise ValueError(f"fixed PSARC block overflow: {details}")

    output.write_bytes(raw)
    if output.stat().st_size != source.stat().st_size:
        raise AssertionError("fixed-block PSARC size changed")

    check = PSARC(str(output))
    if check.toc_len != archive.toc_len or check.block_table != archive.block_table:
        raise AssertionError("PSARC TOC or block table changed")
    for entry, expected in modified.items():
        if check.read_entry(entry) != expected:
            raise AssertionError(f"entry {entry} fixed-block readback mismatch")
    return {
        "changed_blocks": changed_blocks,
        "zlib_padding_bytes": padded_bytes,
        "block_overflows": 0,
        "toc_identical": True,
        "block_table_identical": True,
        "psarc_size_identical": True,
    }

