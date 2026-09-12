"""Repair proven BMD pointer/metadata corruption, retaining release translations."""
import hashlib
import json
import re
import struct
from pathlib import Path
from bmd_rebuild import BmdFile
from psarc import PSARC
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'korean_build_v3'
SOURCE = BUILD / 'Battle_issue6_ko_20260909.psarc.sdat'
RETAIL = ROOT / 'original_backups/Battle.psarc.sdat.orig'
OUT = BUILD / 'battle_refs_20260912'
SCAN = re.compile(rb'(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3})+')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest().upper()

def legacy_pool(data):
    for m in SCAN.finditer(data):
        t = m.group().decode('utf-8')
        if len(t) >= 3 and any(ord(c) > 0x2000 for c in t):
            return m.start()
    raise ValueError('No legacy string pool')

def layout(data):
    assert data[:2] == b'\x03\x00'
    a, b, count = struct.unpack_from('>HHH', data, 2)
    start = 8 + a * 12 + b * 20
    base = start + count * 20
    assert base <= len(data)
    return base, [start + i * 20 + 16 for i in range(count)]

def repair(original, current):
    base, pointers = layout(original)
    assert layout(current) == (base, pointers)
    old_start = legacy_pool(original)
    old = BmdFile(original, pool_start=old_start)
    new = BmdFile(current, pool_start=old_start)
    assert len(old.records) == len(new.records)
    assert 0 <= base - old_start <= 2
    old_offsets = [p - base for p, _, _ in old.records]
    old_offsets[0] = 0
    by_offset = dict(zip(old_offsets, range(len(old.records))))
    values = [struct.unpack_from('>I', original, p)[0] for p in pointers]
    assert set(values) - {0xFFFFFFFF} == set(by_offset)
    # Prove every non-pointer header change is a collateral offset remap.
    wrong_map = {p-old_start:q-old_start for (p,_,_),(q,_,_) in zip(old.records,new.records)}
    collateral = 0
    for p in range(0, base, 4):
        if p in pointers or original[p:p+4] == current[p:p+4]:
            continue
        before, after = struct.unpack_from('>I', original, p)[0], struct.unpack_from('>I', current, p)[0]
        assert wrong_map.get(before) == after, (p, before, after)
        collateral += 1
    end = new.records[-1][0] + new.records[-1][1]
    assert not any(current[end:]), 'Unexpected nonzero footer'
    pool = current[old_start:end]
    assert base + len(pool) <= len(current)
    fixed = bytearray(original[:base] + pool)
    fixed.extend(b'\0' * (len(current) - len(fixed)))
    changed_pointers = 0
    blank_before = 0
    for p, value in zip(pointers, values):
        if value == 0xFFFFFFFF:
            continue
        record = new.records[by_offset[value]]
        rel = record[0] - old_start
        previous = struct.unpack_from('>I', current, p)[0]
        changed_pointers += previous != rel
        old_at = base + previous
        blank_before += old_at >= len(current) or current[old_at] == 0
        struct.pack_into('>I', fixed, p, rel)
        at = base + rel
        raw = bytes(fixed[at:fixed.index(0, at)])
        assert raw == record[2].encode('utf-8')
    parsed = BmdFile(fixed, pool_start=base)
    assert parsed.texts() == new.texts(), 'Translation text changed'
    assert len(fixed) == len(current)
    return bytes(fixed), dict(strings=len(new.records), references=len(values),
        parser_shift=base-old_start, changed_pointers=changed_pointers,
        restored_metadata_words=collateral, blank_references_before=blank_before)

def main():
    assert sha(SOURCE) == 'F1AC61F80B70BC0E85B5ABB15DC82E2AF55E6A16084DD8C438FC7AA5B2A02E6E'
    OUT.mkdir(exist_ok=True)
    changes, rows = {}, []
    with SOURCE.open('rb') as f, RETAIL.open('rb') as g:
        source, retail = PSARC(SDATReader(f, 0)), PSARC(SDATReader(g, 0))
        assert source.manifest() == retail.manifest()
        for i, name in enumerate(source.manifest(), 1):
            if not name.startswith('/Dat/Battle/Message/') or not name.endswith('.bmd'):
                continue
            current = source.read_entry(i)
            fixed, info = repair(retail.read_entry(i), current)
            if fixed != current:
                changes[i] = fixed
            rows.append(dict(entry=i, name=name, changed=fixed != current, **info))
    totals = {key: sum(r[key] for r in rows) for key in ('strings','references','changed_pointers','restored_metadata_words','blank_references_before')}
    report = dict(source=str(SOURCE), source_sha256=sha(SOURCE), entries=len(rows), changed_entries=len(changes), totals=totals, files=rows, installed=False, runtime_verified=False)
    (OUT / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(totals), 'Changed BMDs', len(changes), flush=True)
    plain, packed, target = OUT/'source.psarc', OUT/'fixed.psarc', OUT/'Battle.psarc.sdat'
    with SOURCE.open('rb') as f:
        header = f.read(256)
    with SOURCE.open('rb') as f, plain.open('wb') as w:
        size, _ = decrypt_stream(f, 0, w)
    print('Repack changed BMDs only', flush=True)
    rebuild_fixed_entry_spans(plain, changes, packed)
    assert packed.stat().st_size == size
    print('Encode SDAT', flush=True)
    encode(str(packed), header, str(target))
    assert target.stat().st_size <= SOURCE.stat().st_size
    with target.open('ab') as f:
        f.write(b'\0' * (SOURCE.stat().st_size-target.stat().st_size))
    print('Verify every archive entry', flush=True)
    with SOURCE.open('rb') as f, target.open('rb') as g:
        a, b = PSARC(SDATReader(f,0)), PSARC(SDATReader(g,0))
        assert a.manifest() == b.manifest()
        for i in range(a.n):
            assert b.read_entry(i) == changes.get(i, a.read_entry(i)), i
    report.update(candidate=str(target), sha256=sha(target), all_entries_verified=True, translation_bytes_preserved=True)
    (OUT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(report['sha256'], flush=True)
    plain.unlink()
    packed.unlink()

if __name__ == '__main__':
    main()
