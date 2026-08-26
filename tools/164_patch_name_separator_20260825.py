#!/usr/bin/env python3
"""이름 사이 구분자 '=' 를 공백으로 바꾼다 (2026-08-25).

원본 일본어는 성과 이름을 전각 등호로 잇는다 (アル＝ヴァン).
한국어판은 이 표기를 그대로 옮겨 '알=반' 처럼 나오는데, 사용자 지시에 따라
공백으로 바꾼다.

'=' 1바이트 -> 공백 1바이트, '＝' 3바이트 -> 전각공백 3바이트로
**바이트 길이가 전혀 변하지 않는** 치환이라 컨테이너 종류(FIXH/LDBI/LOGO/
bmd/wtd)와 무관하게 안전하다. 길이 필드도 오프셋 테이블도 손댈 필요가 없다.
"""
from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
REPORT = BUILD / "name_separator_20260825_report.json"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_names", "163_patch_reports_20260824.py")
decode_proxy = PREV.decode_proxy
iter_chunks = PREV.iter_chunks
digest = PREV.digest
restore_retail_time = PREV.restore_retail_time
BASE = PREV.BASE

# 처리 대상: (아카이브 이름, 직전 산출물, 새 산출물, 소매판 원본 파일명)
TARGETS = [
    ("General2d",
     BUILD / "General2d_reports_ko_20260824.psarc.sdat",
     BUILD / "General2d_names_ko_20260825.psarc.sdat",
     "General2d.psarc.sdat.orig"),
    ("Logic",
     BUILD / "Logic_reports_ko_20260824.psarc.sdat",
     BUILD / "Logic_names_ko_20260825.psarc.sdat",
     "Logic.psarc.sdat.orig"),
    ("Battle",
     BUILD / "Battle_reports_ko_20260824.psarc.sdat",
     BUILD / "Battle_names_ko_20260825.psarc.sdat",
     "Battle.psarc.sdat.orig"),
    ("Common",
     BUILD / "Common_runtime_followups_ko_20260819.psarc.sdat",
     BUILD / "Common_names_ko_20260825.psarc.sdat",
     "Common.psarc.sdat.orig"),
]

# .pssg/.bn2/.dds 같은 바이너리는 우연히 한글로 디코드되는 구간이 있어
# 텍스트 컨테이너로만 대상을 좁힌다.
TEXT_SUFFIX = (".dat", ".bin", ".bmd", ".wtd")

HANGUL = r"[가-힣]"
# 한글과 한글 사이에 낀 등호만 바꾼다. 수식이나 키가이드의 '=' 는 건드리지 않는다.
PATTERN = re.compile(f"(?<={HANGUL})[=＝](?={HANGUL})")
SWAP = {"=": " ", "＝": "　"}


def patch_entry(data: bytes, names: Counter) -> bytes | None:
    """조각 단위로 디코드해 이름 구분자만 치환. 길이는 그대로 유지한다."""
    buffer = bytearray(data)
    changed = False
    for pos, chunk, _width in iter_chunks(data):
        decoded = decode_proxy(chunk)
        if decoded is None or ("=" not in decoded and "＝" not in decoded):
            continue
        matches = list(PATTERN.finditer(decoded))
        if not matches:
            continue
        # 디코드 문자열과 원본 문자열은 문자 수가 같다(프록시 1:1 역매핑).
        # 바이트 폭은 다르므로 위치는 반드시 원본 문자열 기준으로 잡는다.
        raw_text = chunk.decode("utf-8")
        offsets = []
        cursor = 0
        for char in raw_text:
            offsets.append(cursor)
            cursor += len(char.encode("utf-8"))
        for match in matches:
            index = match.start()
            byte_at = pos + offsets[index]
            source = raw_text[index]
            target = SWAP[source]
            old_bytes = source.encode("utf-8")
            new_bytes = target.encode("utf-8")
            assert len(old_bytes) == len(new_bytes)
            if bytes(buffer[byte_at:byte_at + len(old_bytes)]) != old_bytes:
                raise AssertionError(f"바이트 위치 어긋남 at 0x{byte_at:X}")
            buffer[byte_at:byte_at + len(new_bytes)] = new_bytes
            changed = True
            names[decoded[max(0, index - 4):index + 5]] += 1
    return bytes(buffer) if changed else None


def process(tag: str, source: Path, output: Path, retail: str) -> dict:
    plain = BUILD / f"_names_{tag}_source.psarc"
    with source.open("rb") as stream, plain.open("wb") as target:
        logical_size, _ = decrypt_stream(stream, 0, target)

    names: Counter = Counter()
    modified: dict[int, bytes] = {}
    archive = PSARC(str(plain))
    try:
        manifest = archive.manifest()
        for entry in range(1, archive.n):
            name = manifest[entry - 1] if entry - 1 < len(manifest) else ""
            if not name.lower().endswith(TEXT_SUFFIX):
                continue
            try:
                data = archive.read_entry(entry)
            except Exception:
                continue
            if b"=" not in data and "＝".encode("utf-8") not in data:
                continue
            patched = patch_entry(data, names)
            if patched is not None:
                if len(patched) != len(data):
                    raise AssertionError(f"{tag} entry {entry}: 길이 변화")
                modified[entry] = patched
    finally:
        archive.f.close()

    if not modified:
        plain.unlink(missing_ok=True)
        return {"entries": [], "count": 0, "sha256": None, "names": {}}

    out_plain = BUILD / (plain.stem + "_out.psarc")
    try:
        pack = rebuild_fixed_entry_spans(plain, modified, out_plain)
    except ValueError:
        pack = rebuild_fixed_entry_spans(plain, modified, out_plain,
                                         recompress_all=True)
    if out_plain.stat().st_size != logical_size:
        raise AssertionError(f"{tag}: 논리 크기 변화")
    encode(str(out_plain), source.read_bytes()[:0x100], str(output))
    BASE.pad_file(output, source.stat().st_size)
    with output.open("rb") as stream:
        rebuilt = PSARC(SDATReader(stream, 0))
        for entry, expected in modified.items():
            if rebuilt.read_entry(entry) != expected:
                raise AssertionError(f"{tag}: entry {entry} 재읽기 불일치")
    restore_retail_time(output, retail)
    for temporary in (plain, out_plain):
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            pass
    return {
        "entries": sorted(modified),
        "count": sum(names.values()),
        "pack": pack,
        "sha256": digest(output),
        "names": dict(names.most_common()),
    }


def main() -> None:
    result = {}
    for tag, source, output, retail in TARGETS:
        if not source.exists():
            raise FileNotFoundError(source)
        result[tag] = process(tag, source, output, retail)
        info = result[tag]
        print(f"{tag}: {info['count']}건 / 엔트리 {len(info['entries'])}개 "
              f"sha256={info['sha256']}")
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(json.dumps({k: {"count": v["count"], "sha256": v["sha256"]}
                      for k, v in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
