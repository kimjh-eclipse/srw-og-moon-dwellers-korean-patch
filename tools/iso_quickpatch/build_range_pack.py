"""Build the OGMD in-place ISO range patch resource.

The output contains only replacement ranges.  Nearby differences separated by at
most MERGE_GAP bytes are merged so the runtime does fewer memory-copy calls.
"""

from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import numpy as np


MAGIC = b"OGMDRNG1"
VERSION = 1
MERGE_GAP = 16
CHUNK_SIZE = 16 * 1024 * 1024

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parent / "OGMD_ISO_ranges.bin"

FILES = (
    {
        "name": "Common",
        "iso_path": "PS3_GAME/USRDIR/PSARC/COMMON_PSARC.SDAT",
        "source": ROOT / "original_backups/Common.psarc.sdat.orig",
        # Keep only the startup warning, title logo, and scenario title cards.
        # Shared/animated UI image replacements remain intentionally excluded.
        "target": ROOT / "korean_build_v3/Common_runtime_followups_ko_20260819.psarc.sdat",
        "source_hash": "99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB",
        "target_hash": "16C45C456DA86DD17B5C05BD8735433873C37503984C1C58A96C613FDA5CD2B2",
    },
    {
        "name": "General2d",
        "iso_path": "PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT",
        "source": ROOT / "original_backups/General2d.psarc.sdat.orig",
        # General2d/tex_06.dds image localization is intentionally excluded.
        # It is a shared UI glyph atlas and corrupted the level-up display.
        "target": ROOT / "korean_build_v3/General2d_name_followups_ko_20260822.psarc.sdat",
        "source_hash": "04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667",
        "target_hash": "29EC56DB773F1ADD358D883ECC522AC28FACC2BEC124F947B28FCBA280282D1E",
    },
    {
        "name": "Logic",
        "iso_path": "PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT",
        "source": ROOT / "original_backups/Logic.psarc.sdat.orig",
        # Logic image replacements are retired; use the text-only archive.
        # Includes all localized scenario titles plus the full location-card
        # audit that replaces visible U+3000 separators with normal spaces.
        "target": ROOT / "korean_build_v3/Logic_character_names_ko_20260822.psarc.sdat",
        "source_hash": "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
        "target_hash": "3CB73CD83E946070995A0EA4529F7C3BF2CB101B9FD24C3D36E38719360B079F",
    },
    {
        "name": "Battle",
        "iso_path": "PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT",
        "source": ROOT / "original_backups/Battle.psarc.sdat.orig",
        # Battle/cosl.dds image localization is intentionally excluded.
        # It is a shared HUD atlas and hid unit names plus HP/EN at runtime.
        "target": ROOT / "korean_build_v3/Battle_character_names_ko_20260822.psarc.sdat",
        "source_hash": "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
        "target_hash": "B5CB66BBA32BBF066E4846886E5394FF42C6789B814B9F1282A374E4DDA4113E",
    },
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        while True:
            data = stream.read(CHUNK_SIZE)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest().upper()


def find_ranges(source: Path, target: Path) -> list[tuple[int, int]]:
    if source.stat().st_size != target.stat().st_size:
        raise ValueError(f"size mismatch: {source} / {target}")

    positions: list[np.ndarray] = []
    offset = 0
    with source.open("rb", buffering=0) as left, target.open("rb", buffering=0) as right:
        while offset < source.stat().st_size:
            old = left.read(min(CHUNK_SIZE, source.stat().st_size - offset))
            new = right.read(len(old))
            changed = np.flatnonzero(
                np.frombuffer(old, dtype=np.uint8) != np.frombuffer(new, dtype=np.uint8)
            )
            if changed.size:
                positions.append(changed.astype(np.int64) + offset)
            offset += len(old)

    if not positions:
        return []

    all_positions = np.concatenate(positions)
    cuts = np.flatnonzero(np.diff(all_positions) > MERGE_GAP + 1)
    starts = np.r_[0, cuts + 1]
    ends = np.r_[cuts, len(all_positions) - 1]
    return [
        (int(all_positions[start]), int(all_positions[end] - all_positions[start] + 1))
        for start, end in zip(starts, ends)
    ]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    totals = {"ranges": 0, "payload": 0}

    with temporary.open("wb", buffering=1024 * 1024) as output:
        output.write(MAGIC)
        output.write(struct.pack("<II", VERSION, len(FILES)))

        for spec in FILES:
            source = Path(spec["source"])
            target = Path(spec["target"])
            source_hash = file_hash(source)
            target_hash = file_hash(target)
            if source_hash != spec["source_hash"]:
                raise ValueError(f"{spec['name']} source hash mismatch: {source_hash}")
            if target_hash != spec["target_hash"]:
                raise ValueError(f"{spec['name']} target hash mismatch: {target_hash}")

            ranges = find_ranges(source, target)
            encoded_path = spec["iso_path"].encode("utf-8")
            output.write(struct.pack("<H", len(encoded_path)))
            output.write(encoded_path)
            output.write(struct.pack("<Q", source.stat().st_size))
            output.write(bytes.fromhex(source_hash))
            output.write(bytes.fromhex(target_hash))
            output.write(struct.pack("<I", len(ranges)))

            payload = 0
            with target.open("rb", buffering=0) as target_stream:
                for offset, length in ranges:
                    target_stream.seek(offset)
                    data = target_stream.read(length)
                    if len(data) != length:
                        raise IOError(f"short target read: {spec['name']} @ {offset}")
                    output.write(struct.pack("<QI", offset, length))
                    output.write(data)
                    payload += length

            totals["ranges"] += len(ranges)
            totals["payload"] += payload
            print(
                f"{spec['name']}: {len(ranges):,} ranges, "
                f"{payload:,} payload bytes, hashes OK"
            )

        output.flush()
        os.fsync(output.fileno())

    temporary.replace(OUTPUT)
    print(f"TOTAL: {totals['ranges']:,} ranges, {totals['payload']:,} payload bytes")
    print(f"PACK: {OUTPUT.stat().st_size:,} bytes")
    print(f"SHA256: {file_hash(OUTPUT)}")


if __name__ == "__main__":
    main()
