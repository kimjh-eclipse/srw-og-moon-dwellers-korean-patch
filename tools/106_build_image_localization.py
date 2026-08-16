#!/usr/bin/env python3
"""Pack localized raster assets into the final Korean OGMD archives."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zlib
from pathlib import Path

from psarc import PSARC
import psarc_write
import psarc_fixed_blocks
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "korean_build_v3"
ASSET_ROOT = ROOT / "image_localization" / "localized"
OUTPUT_ROOT = ROOT / "korean_build_v4_images"
REPORT_ROOT = OUTPUT_ROOT / "reports"

ARCHIVES = {
    "Common": {
        "source": SOURCE_ROOT / "Common_support_attack_advance_20260814.psarc.sdat",
        "retail": ROOT / "original_backups" / "Common.psarc.sdat.orig",
        "output": OUTPUT_ROOT / "Common_images_ko_20260815.psarc.sdat",
        "method": "fixed-entry-spans-fast",
    },
    "General2d": {
        "source": SOURCE_ROOT / "General2d_event_label_20260814.psarc.sdat",
        "retail": ROOT / "original_backups" / "General2d.psarc.sdat.orig",
        "output": OUTPUT_ROOT / "General2d_images_ko_20260815.psarc.sdat",
        "method": "fixed-entry-spans-fast",
    },
    "Logic": {
        "source": SOURCE_ROOT / "Logic_keyword_links_ko_20260815.psarc.sdat",
        "retail": ROOT / "original_backups" / "Logic.psarc.sdat.orig",
        "output": OUTPUT_ROOT / "Logic_images_ko_20260815.psarc.sdat",
        "method": "fixed-entry-spans-fast",
    },
    "Battle": {
        "source": SOURCE_ROOT / "Battle_compatable_kaiser_20260812.psarc.sdat",
        "retail": ROOT / "original_backups" / "Battle.psarc.sdat.orig",
        "output": OUTPUT_ROOT / "Battle_images_ko_20260815.psarc.sdat",
        "method": "fixed-blocks",
    },
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def fast_compress_blocks(data: bytes, block_size: int):
    sizes: list[int] = []
    blobs: list[bytes] = []
    for offset in range(0, len(data), block_size):
        chunk = data[offset : offset + block_size]
        candidates = [zlib.compress(chunk, level=9)]
        for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED):
            encoder = zlib.compressobj(
                level=9,
                method=zlib.DEFLATED,
                wbits=zlib.MAX_WBITS,
                memLevel=9,
                strategy=strategy,
            )
            candidates.append(encoder.compress(chunk) + encoder.flush())
        compressed = min(candidates, key=len)
        if len(compressed) < len(chunk):
            sizes.append(len(compressed))
            blobs.append(compressed)
        else:
            sizes.append(0 if len(chunk) == block_size else len(chunk))
            blobs.append(chunk)
    return sizes, blobs


def fast_compress_chunk(chunk: bytes) -> bytes:
    candidates = [zlib.compress(chunk, level=9)]
    for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED):
        encoder = zlib.compressobj(
            level=9,
            method=zlib.DEFLATED,
            wbits=zlib.MAX_WBITS,
            memLevel=9,
            strategy=strategy,
        )
        candidates.append(encoder.compress(chunk) + encoder.flush())
    return min(candidates, key=len)


def load_replacements(archive_name: str, archive: PSARC) -> tuple[dict[int, bytes], dict[int, str]]:
    names = archive.manifest()
    indices = {name: entry for entry, name in enumerate(names, 1)}
    replacements: dict[int, bytes] = {}
    paths: dict[int, str] = {}
    base = ASSET_ROOT / archive_name
    for asset in sorted(base.rglob("*.dds")):
        game_path = "/" + asset.relative_to(base).as_posix()
        if game_path not in indices:
            raise KeyError(f"asset not found in {archive_name}: {game_path}")
        entry = indices[game_path]
        data = asset.read_bytes()
        expected = archive.entries[entry]["orig_size"]
        if len(data) != expected:
            raise ValueError(f"entry size changed: {game_path} {len(data)} != {expected}")
        replacements[entry] = data
        paths[entry] = game_path
    return replacements, paths


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise ValueError(f"archive overflow: {path.name} {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def build_one(name: str, config: dict) -> dict:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    source: Path = config["source"]
    output: Path = config["output"]
    source_plain = OUTPUT_ROOT / f"_{name.lower()}_image_source.psarc"
    output_plain = OUTPUT_ROOT / f"_{name.lower()}_image_output.psarc"
    archive = candidate = None
    try:
        with source.open("rb") as encrypted, source_plain.open("wb") as plain:
            logical_size, _ = decrypt_stream(encrypted, 0, plain)
        archive = PSARC(str(source_plain))
        replacements, paths = load_replacements(name, archive)
        print(f"{name}: replacements={len(replacements)} logical_size={logical_size:,}", flush=True)

        if config["method"] == "fixed-blocks":
            pack_report = psarc_fixed_blocks.rebuild_fixed_blocks(source_plain, replacements, output_plain)
        elif config["method"] == "fixed-blocks-fast":
            original_compressor = psarc_fixed_blocks.compress_blocks
            psarc_fixed_blocks.compress_blocks = fast_compress_blocks
            try:
                pack_report = psarc_fixed_blocks.rebuild_fixed_blocks(source_plain, replacements, output_plain)
            finally:
                psarc_fixed_blocks.compress_blocks = original_compressor
        elif config["method"] == "fixed-entry-spans-fast":
            pack_report = rebuild_fixed_entry_spans(
                source_plain, replacements, output_plain, compressor=fast_compress_chunk
            )
        elif config["method"] == "fixed-spans":
            pack_report = rebuild_fixed_entry_spans(source_plain, replacements, output_plain)
        else:
            original_compressor = psarc_write.compress_blocks
            psarc_write.compress_blocks = fast_compress_blocks
            try:
                rebuilt_size = psarc_write.rebuild(str(source_plain), replacements, str(output_plain))
            finally:
                psarc_write.compress_blocks = original_compressor
            pack_report = {
                "rebuilt_plain_size_before_padding": rebuilt_size,
                "plain_padding_bytes": logical_size - rebuilt_size,
                "entry_offsets_identical": False,
            }
            pad(output_plain, logical_size)

        encode(str(output_plain), source.read_bytes()[:0x100], str(output))
        pad(output, source.stat().st_size)

        with output.open("rb") as encrypted:
            candidate = PSARC(SDATReader(encrypted, 0))
            if candidate.manifest() != archive.manifest():
                raise AssertionError(f"{name}: manifest changed")
            for entry, expected in replacements.items():
                if candidate.read_entry(entry) != expected:
                    raise AssertionError(f"{name}: readback mismatch {paths[entry]}")

        retail_stat = config["retail"].stat()
        os.utime(output, ns=(retail_stat.st_atime_ns, retail_stat.st_mtime_ns))
        report = {
            "archive": name,
            "source": str(source),
            "source_sha256": digest(source),
            "output": str(output),
            "output_sha256": digest(output),
            "size": output.stat().st_size,
            "localized_entries": len(replacements),
            "localized_paths": [paths[index] for index in sorted(paths)],
            "manifest_identical": True,
            "localized_readback_mismatches": 0,
            **pack_report,
        }
        report_path = REPORT_ROOT / f"{name.lower()}_images_ko_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("archive", "output_sha256", "size", "localized_entries")}, ensure_ascii=False), flush=True)
        return report
    finally:
        for value in (archive, candidate):
            if value is not None and hasattr(value.f, "close"):
                value.f.close()
        source_plain.unlink(missing_ok=True)
        output_plain.unlink(missing_ok=True)


def main() -> None:
    selected = sys.argv[1:] or list(ARCHIVES)
    unknown = [name for name in selected if name not in ARCHIVES]
    if unknown:
        raise SystemExit(f"unknown archives: {unknown}")
    for name in selected:
        build_one(name, ARCHIVES[name])
    reports = []
    for name in ARCHIVES:
        report_path = REPORT_ROOT / f"{name.lower()}_images_ko_report.json"
        if report_path.exists():
            reports.append(json.loads(report_path.read_text(encoding="utf-8")))
    summary = {
        "date": "2026-08-15",
        "localized_images": sum(report["localized_entries"] for report in reports),
        "archives": reports,
    }
    (OUTPUT_ROOT / "image_localization_build_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"complete localized_images={summary['localized_images']}")


if __name__ == "__main__":
    main()
