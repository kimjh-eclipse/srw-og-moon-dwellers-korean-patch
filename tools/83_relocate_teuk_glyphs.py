#!/usr/bin/env python3
"""Relocate 트/특 proxies away from retail UI glyph cells."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
from pathlib import Path

from PIL import ImageFont

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
INSTALLED = Path(r"C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64\dev_hdd0\game\BLJS10335\USRDIR\PSARC")
ORIGINALS = ROOT / "original_backups"

SOURCES = {
    "Common": INSTALLED / "Common.psarc.sdat",
    "General2d": BUILD / "General2d_self_target_fixed_20260812.psarc.sdat",
    "Logic": BUILD / "Logic_skill_descriptions_fixed_20260812.psarc.sdat",
    "Battle": INSTALLED / "Battle.psarc.sdat",
}
ORIGINAL = {
    name: ORIGINALS / f"{name}.psarc.sdat.orig" for name in SOURCES
}
OUTPUTS = {
    name: BUILD / f"{name}_teuk_glyphs_relocated_20260812.psarc.sdat"
    for name in SOURCES
}
REPORT = BUILD / "teuk_glyphs_relocated_20260812_report.json"

# The retail UI uses the old codepoints/cells directly.  Korean translations
# must move to unused metrics and unused atlas cells.
MOVES = {
    # First two safe candidates immediately after the immutable V3 map.
    0xA010: {"hangul": "트", "new_cp": 0xA0D2, "old_slot": 3596, "new_slot": 3738},
    0xA011: {"hangul": "특", "new_cp": 0xA0D3, "old_slot": 3597, "new_slot": 3739},
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pad(path: Path, size: int) -> None:
    if path.stat().st_size > size:
        raise AssertionError(f"encoded SDAT grew: {path}")
    if path.stat().st_size < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - path.stat().st_size))


def load_font_builder():
    spec = importlib.util.spec_from_file_location("ogmd_font_builder", ROOT / "16_build_korean_font.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def copy_cell(builder, source: bytes, target: bytearray, slot: int) -> None:
    cell_x = slot % builder.PHYSICAL_CELLS_X
    cell_y = slot // builder.PHYSICAL_CELLS_X
    for local_by in range(builder.CELL_SIZE // 4):
        for local_bx in range(builder.CELL_SIZE // 4):
            block_x = cell_x * (builder.CELL_SIZE // 4) + local_bx
            block_y = cell_y * (builder.CELL_SIZE // 4) + local_by
            block_index = block_y * builder.BLOCKS_X + block_x
            offset = builder.TEXTURE_OFFSET + block_index * 16
            target[offset:offset + 16] = source[offset:offset + 16]


def relocate_entry(current: bytes, original: bytes) -> tuple[bytes, dict[str, object]]:
    data = bytearray(current)
    counts: dict[str, object] = {}
    for old_cp, info in MOVES.items():
        old = chr(old_cp).encode("utf-8")
        new = chr(info["new_cp"]).encode("utf-8")
        positions = []
        start = 0
        while True:
            pos = current.find(old, start)
            if pos < 0:
                break
            # Exact original matches are retail UI/control uses and must keep
            # the old codepoint.  Only translation-introduced uses move.
            if original[pos:pos + len(old)] != old:
                data[pos:pos + len(old)] = new
                positions.append(pos)
            start = pos + len(old)
        if positions:
            counts[info["hangul"]] = {
                "old_cp": f"U+{old_cp:04X}",
                "new_cp": f"U+{info['new_cp']:04X}",
                "relocated": len(positions),
                "retail_uses_preserved": current.count(old) - len(positions),
            }
    return bytes(data), counts


def build_common() -> dict[str, object]:
    source = SOURCES["Common"]
    original = ORIGINAL["Common"]
    output = OUTPUTS["Common"]
    sp = BUILD / "COMMON_teuk_source.psarc"
    op = BUILD / "COMMON_teuk_fixed.psarc"
    rp = BUILD / "COMMON_teuk_retail.psarc"
    sa = oa = candidate = None
    try:
        with source.open("rb") as s, sp.open("wb") as t:
            logical_size, _ = decrypt_stream(s, 0, t)
        with original.open("rb") as s, rp.open("wb") as t:
            decrypt_stream(s, 0, t)
        sa = PSARC(str(sp)); oa = PSARC(str(rp))
        current_font = bytearray(sa.read_entry(3))
        retail_font = oa.read_entry(3)
        builder = load_font_builder()
        face = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 28)
        changes = []
        for old_cp, info in MOVES.items():
            old_off = builder.metric_offset(current_font, old_cp)
            new_off = builder.metric_offset(current_font, info["new_cp"])
            if old_off is None or new_off is None:
                raise AssertionError("missing font metric")
            if builder.metric_slot(current_font, old_cp) != info["old_slot"]:
                raise AssertionError("old slot mismatch")
            if builder.metric_slot(retail_font, info["new_cp"]) != info["new_slot"]:
                raise AssertionError("new metric slot mismatch")
            # Restore both the metric and atlas pixels used by retail UI.
            current_font[old_off:old_off + 4] = retail_font[old_off:old_off + 4]
            copy_cell(builder, retail_font, current_font, info["old_slot"])
            # Install the Korean glyph in a new unused cell/metric.
            builder.inject_cell(current_font, info["new_slot"], builder.render_glyph(info["hangul"], face))
            # Preserve the retail coordinate bytes and change only advance.
            current_font[new_off:new_off + 4] = retail_font[new_off:new_off + 4]
            current_font[new_off:new_off + 2] = (22).to_bytes(2, "big")
            changes.append({
                "hangul": info["hangul"], "old_cp": f"U+{old_cp:04X}",
                "new_cp": f"U+{info['new_cp']:04X}",
                "old_slot_restored": info["old_slot"], "new_slot": info["new_slot"],
            })
        # Two newly rendered atlas cells can make one individual zlib block
        # slightly larger.  Common has ample padding across the complete font
        # entry, so redistribute only within the entry's original block span.
        fixed = rebuild_fixed_entry_spans(sp, {3: bytes(current_font)}, op)
        encode(str(op), source.read_bytes()[:0x100], str(output)); pad(output, source.stat().st_size)
        with output.open("rb") as stream:
            candidate = PSARC(SDATReader(stream, 0))
            if candidate.read_entry(3) != bytes(current_font):
                raise AssertionError("Common font verification failed")
        return {"changes": changes, "output": str(output), "output_sha256": sha(output), **fixed}
    finally:
        for obj in (sa, oa, candidate):
            if obj is not None:
                handle = getattr(obj, "f", None)
                if hasattr(handle, "close"):
                    handle.close()
        for p in (sp, op, rp):
            try:
                p.unlink(missing_ok=True)
            except PermissionError:
                pass


def build_text_archive(name: str) -> dict[str, object]:
    source, original, output = SOURCES[name], ORIGINAL[name], OUTPUTS[name]
    sp = BUILD / f"{name}_teuk_source.psarc"
    rp = BUILD / f"{name}_teuk_retail.psarc"
    op = BUILD / f"{name}_teuk_fixed.psarc"
    vp = BUILD / f"{name}_teuk_verify.psarc"
    sa = oa = va = None
    try:
        with source.open("rb") as s, sp.open("wb") as t:
            logical_size, _ = decrypt_stream(s, 0, t)
        with original.open("rb") as s, rp.open("wb") as t:
            decrypt_stream(s, 0, t)
        sa = PSARC(str(sp)); oa = PSARC(str(rp))
        if sa.n != oa.n:
            raise AssertionError(f"archive entry count mismatch: {name}")
        replacements: dict[int, bytes] = {}
        summaries: dict[int, dict[str, object]] = {}
        for index in range(sa.n):
            current = sa.read_entry(index)
            retail = oa.read_entry(index)
            changed, counts = relocate_entry(current, retail)
            if changed != current:
                replacements[index] = changed
                summaries[index] = counts
        if name == "General2d":
            fixed = rebuild_fixed_blocks(sp, replacements, op)
        else:
            fixed = rebuild_fixed_entry_spans(sp, replacements, op)
        if op.stat().st_size != logical_size:
            raise AssertionError(f"logical PSARC size changed: {name}")
        encode(str(op), source.read_bytes()[:0x100], str(output)); pad(output, source.stat().st_size)
        with output.open("rb") as s, vp.open("wb") as t:
            decrypt_stream(s, 0, t)
        va = PSARC(str(vp))
        mismatches = [
            i for i in range(sa.n)
            if va.read_entry(i) != replacements.get(i, sa.read_entry(i))
        ]
        if mismatches:
            raise AssertionError(f"verification mismatch {name}: {mismatches[:20]}")
        totals = {"트": 0, "특": 0}
        preserved = {"트": 0, "특": 0}
        for counts in summaries.values():
            for char, item in counts.items(): totals[char] += item["relocated"]
        for old_cp, info in MOVES.items():
            q = chr(old_cp).encode("utf-8")
            preserved[info["hangul"]] = sum(sa.read_entry(i).count(q) for i in range(sa.n)) - totals[info["hangul"]]
        return {
            "output": str(output), "output_sha256": sha(output),
            "changed_entries": len(replacements), "relocated": totals,
            "retail_uses_preserved": preserved, "semantic_mismatches": 0, **fixed,
        }
    finally:
        for obj in (sa, oa, va):
            if obj is not None:
                handle = getattr(obj, "f", None)
                if hasattr(handle, "close"):
                    handle.close()
        for p in (sp, rp, op, vp):
            try:
                p.unlink(missing_ok=True)
            except PermissionError:
                pass


def main() -> None:
    result = {"Common": build_common()}
    for name in ("General2d", "Logic", "Battle"):
        result[name] = build_text_archive(name)
    # Candidate timestamps must match retail originals before installation.
    for name, path in OUTPUTS.items():
        stat = ORIGINAL[name].stat()
        import os
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    report = {"moves": MOVES, "archives": result}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
