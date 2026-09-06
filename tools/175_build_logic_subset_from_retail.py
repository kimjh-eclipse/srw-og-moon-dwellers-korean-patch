#!/usr/bin/env python3
"""엔딩 프리징 분기 실험용: 소매판 Logic 을 밑바탕으로 한글 변경 엔트리의 부분집합만 얹어 재패킹 (2026-09-06).

왜 필요한가
  한글 정본(Logic_names_ko_20260825)에서 특정 엔트리를 소매판으로 "되돌리는" 방식은
  한글본이 더 작게 압축된 엔트리(BGMData, KeyGuideData, PilotDictionaryData)에서
  블록 용량이 줄어 있어 스팬 초과로 실패한다. 리빌더는 블록을 키우지 않는다.
  반대로 소매판을 밑바탕으로 두고 `psarc_write.rebuild_var` 로 전체 재패킹하면
  블록 표를 다시 계산하므로 임의의 부분집합을 만들 수 있다.

사용
  python 175_build_logic_subset_from_retail.py <tag> --exclude 6 13
      한글 변경 엔트리 전부를 얹되 6, 13 은 소매판으로 둔다
  python 175_build_logic_subset_from_retail.py <tag> --only 397 398 27
      나열한 엔트리만 한글, 나머지는 소매판
  python 175_build_logic_subset_from_retail.py <tag> --range-half A|B
      변경 엔트리를 인덱스 순으로 반분해 A/B 절반만 한글

출력: korean_build_v3/Logic_rb_<tag>.psarc.sdat  (크기 = 소매판 SDAT 크기)
검증: 제외 엔트리 == 소매판, 포함 엔트리 == 한글본, 그 외 == 소매판(== 한글본)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from psarc import PSARC
from psarc_write import enable_zopfli, rebuild_var
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

# 한글 정본은 Zopfli 로 맞춰져 있다. 일반 zlib 로 재패킹하면 소매판 SDAT 크기를 넘는다.
enable_zopfli()

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
RETAIL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
KOREAN = BUILD / "Logic_names_ko_20260825.psarc.sdat"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_163_rb", "163_patch_reports_20260824.py")
BASE, restore_retail_time = PREV.BASE, PREV.restore_retail_time


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--exclude", nargs="+", type=int)
    g.add_argument("--only", nargs="+", type=int)
    g.add_argument("--range-half", choices=["A", "B"])
    args = ap.parse_args()

    with RETAIL.open("rb") as rs, KOREAN.open("rb") as ks:
        R, K = PSARC(SDATReader(rs, 0)), PSARC(SDATReader(ks, 0))
        manifest = R.manifest()
        changed = [e for e in range(1, R.n) if R.read_entry(e) != K.read_entry(e)]
        if args.exclude is not None:
            keep = [e for e in changed if e not in set(args.exclude)]
        elif args.only is not None:
            keep = [e for e in changed if e in set(args.only)]
        else:
            half = len(changed) // 2
            keep = changed[:half] if args.range_half == "A" else changed[half:]
        korean = {e: K.read_entry(e) for e in keep}
    excluded = [e for e in changed if e not in korean]
    print(f"변경 엔트리 {len(changed)}개 중 한글 유지 {len(keep)}개, 소매판 유지 {len(excluded)}개")
    print("  소매판 유지:", [(e, manifest[e - 1].split('/')[-1]) for e in excluded][:12], "..." if len(excluded) > 12 else "")

    retail_plain = BUILD / f"_rb_{args.tag}_retail.psarc"
    out_plain = BUILD / f"_rb_{args.tag}_out.psarc"
    output = BUILD / f"Logic_rb_{args.tag}.psarc.sdat"
    try:
        with RETAIL.open("rb") as stream, retail_plain.open("wb") as target:
            decrypt_stream(stream, 0, target)
        rebuild_var(str(retail_plain), korean, str(out_plain))
        encode(str(out_plain), RETAIL.read_bytes()[:0x100], str(output))
        if output.stat().st_size > RETAIL.stat().st_size:
            raise AssertionError(f"결과 {output.stat().st_size:,}B > 소매판 {RETAIL.stat().st_size:,}B")
        BASE.pad_file(output, RETAIL.stat().st_size)
        restore_retail_time(output, "Logic.psarc.sdat.orig")
        # 검증
        with output.open("rb") as os_, RETAIL.open("rb") as rs, KOREAN.open("rb") as ks:
            O, R, K = PSARC(SDATReader(os_, 0)), PSARC(SDATReader(rs, 0)), PSARC(SDATReader(ks, 0))
            assert O.n == R.n and O.manifest() == manifest, "매니페스트 변화"
            bad = []
            for e in range(1, O.n):
                want = K.read_entry(e) if e in korean else R.read_entry(e)
                if O.read_entry(e) != want:
                    bad.append(e)
            if bad:
                raise AssertionError(f"재읽기 불일치 엔트리 {bad[:10]}")
    finally:
        for tmp in (retail_plain, out_plain):
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    digest = sha256(output)
    report = {"tag": args.tag, "korean_entries": keep, "retail_entries": excluded,
              "retail_names": [manifest[e - 1] for e in excluded], "sha256": digest,
              "size": output.stat().st_size}
    (BUILD / f"Logic_rb_{args.tag}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"출력 {output.name}  {output.stat().st_size:,}B  sha256={digest}")
    print("재읽기 검증: 전 엔트리 일치")


if __name__ == "__main__":
    main()
