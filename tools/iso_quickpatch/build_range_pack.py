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
        # Startup warning, title logo, scenario title cards, and the five
        # Archive story texts (246 paragraphs). Shared/animated UI images stay out.
        "target": ROOT / "korean_build_v3/Common_archive_ko_20260910.psarc.sdat",
        "source_hash": "99B298B3BBE126647582A8B6201513B5E80E2B2F06BF0D5BB1F0D87D0D2093BB",
        "target_hash": "52FFAF183FD89A2A0967A492CA369E6131CA121E403EC1E0E4FB941633B90373",
    },
    {
        "name": "General2d",
        "iso_path": "PS3_GAME/USRDIR/PSARC/GENERAL2D_PSARC.SDAT",
        "source": ROOT / "original_backups/General2d.psarc.sdat.orig",
        # General2d/tex_06.dds image localization is intentionally excluded.
        # It is a shared UI glyph atlas and corrupted the level-up display.
        "target": ROOT / "korean_build_v3/General2d_archive_ko_20260910.psarc.sdat",
        "source_hash": "04C3D1DA43BBE58622FE89499C08A2525CD5AB78C30B830A0D1781ED59F16667",
        "target_hash": "6BCB01A3D66FE668ECA2BF5167D9552DBD1D6F6DB1B0A24083FD40DA2D14AD47",
    },
    {
        "name": "Logic",
        "iso_path": "PS3_GAME/USRDIR/PSARC/LOGIC_PSARC.SDAT",
        "source": ROOT / "original_backups/Logic.psarc.sdat.orig",
        # Text-only archive: scenario titles, issue #6 name/dialogue fixes,
        # 2026-09-10 line-wrap pass, the Archive REPORT dialog strings, and
        # the 2026-09-12 guidance pass (15 titles + 15 body images).
        "target": ROOT / "korean_build_v3/Logic_guidance_full_ko_20260912.psarc.sdat",
        "source_hash": "AF453B395D358FAB79740310BBA03F400A54F3D86CC6A82FD0A504FF25F5F181",
        "target_hash": "A2446B21BB01FE32375BC7F337BCDA0E8C2B76083E8681C05ED4B7F50F6F0E28",
    },
    {
        "name": "Battle",
        "iso_path": "PS3_GAME/USRDIR/PSARC/BATTLE_PSARC.SDAT",
        "source": ROOT / "original_backups/Battle.psarc.sdat.orig",
        # Battle/cosl.dds: the shared HUD atlas. A whole-file replacement once hid
        # unit names and HP/EN; 173 repaints only the 9 attack-type label boxes.
        # 2026-09-12: BMD dialogue references repaired (258_repair_battle_references).
        "target": ROOT / "korean_build_v3/battle_refs_20260912/Battle.psarc.sdat",
        "source_hash": "2C5CA16F75FCE3725E97977F79CD281FD52BF78BC67C9232228E37AFF894A844",
        "target_hash": "E7F07D0CED655852CEFD144679829ED3EAEFFF6C06A232D861E1514ACADA66B3",
    },
    {
        "name": "ParamSfo",
        "iso_path": "PS3_GAME/PARAM.SFO",
        "source": ROOT / "original_backups/PARAM.SFO.orig",
        # Game list title only. TITLE_ID, APP_VER and every other field stay put.
        "target": ROOT / "korean_build_v3/PARAM_SFO_ko_20260910.bin",
        "source_hash": "0A876ACFABB16CEAA017EDD51A700079678AA8E61C0B7AEFE0B59CB19B59FF22",
        "target_hash": "B7ABDFE7FED52FB9EEEDDE02FBD33475A449C20B4EE6099E59BC025E1F32DE54",
    },
    {
        "name": "Icon0",
        "iso_path": "PS3_GAME/ICON0.PNG",
        "source": ROOT / "original_backups/ICON0.PNG.orig",
        # Korean game list icon, zero-padded to the retail slot size.
        # PNG readers stop at IEND, so the trailing padding is inert.
        "target": ROOT / "korean_build_v3/ICON0_PNG_ko_20260910.bin",
        "source_hash": "9B2E67DC606CEF3CD269E13DDA425445820A65F034DE4B3BC000435EA0B9B136",
        "target_hash": "0B038E45343B203DE00D1323247FD5AFFFF3AB61AF35A8206010EA5601948A00",
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
