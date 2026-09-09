#!/usr/bin/env python3
"""GitHub issue #6 대상 문자열을 소매판 원문과 최신 한글 아카이브에서 대조한다."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader
from bmd_rebuild import BmdFile

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
ORIGINALS = ROOT / "original_backups"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_issue6_prev", "163_patch_reports_20260824.py")
decode_proxy = PREV.decode_proxy

TOKENS = (
    "ヘルルーガ", "グ＝ランドン", "グ・ランドン", "グ=ランドン",
    "フー＝ルー", "フー・ルー", "ゴモウドッカ", "ゴライクンル",
    "ダイライオー", "雷鳳", "イング", "ヴォーダの門", "ゼモン・モルター",
)


def fields(data: bytes):
    pos = 0
    for raw in data.split(b"\0"):
        if raw:
            yield pos, raw
        pos += len(raw) + 1


def current_field(data: bytes, pos: int) -> bytes:
    end = data.find(b"\0", pos)
    return data[pos:] if end < 0 else data[pos:end]


def audit_logic(korean_path: Path) -> None:
    rows = []
    master = ROOT / "extract_all" / "master_all.jsonl"
    for line in master.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["psarc"] != "LOGIC":
            continue
        hits = [token for token in TOKENS if token in row["text"]]
        if hits:
            row["hits"] = hits
            rows.append(row)
    by_entry: dict[int, list[dict]] = {}
    for row in rows:
        by_entry.setdefault(row["entry"], []).append(row)
    with korean_path.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        print("\n## Logic")
        for entry, entry_rows in by_entry.items():
            current = archive.read_entry(entry)
            for row in entry_rows:
                now_raw = current_field(current, row["off"])
                now = decode_proxy(now_raw)
                if now is None:
                    now = now_raw.decode("utf-8", "replace")
                print(f"{entry}\t0x{row['off']:X}\t{row['file']}\t{','.join(row['hits'])}")
                print(f"  JP={row['text']}")
                print(f"  KO={now}")


def audit_battle(korean_path: Path) -> None:
    draft = [json.loads(line) for line in
             (ROOT / "battle_translation" / "battle_unique_draft.jsonl").read_text(encoding="utf-8").splitlines()]
    target_uids = {
        row["uid"] for row in draft
        if any(token in row["jp"] for token in TOKENS)
    }
    rows = []
    master = ROOT / "extract_bmd" / "master.jsonl"
    unique_ids: dict[str, int] = {}
    for line in master.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["jp"] not in unique_ids:
            unique_ids[row["jp"]] = len(unique_ids)
        uid = unique_ids[row["jp"]]
        if uid in target_uids:
            row["uid"] = uid
            row["source_jp"] = draft[uid]["jp"]
            rows.append(row)
    if len(unique_ids) != len(draft):
        raise AssertionError(f"BMD 고유 문자열 수 불일치: {len(unique_ids)} != {len(draft)}")
    by_file: dict[str, list[dict]] = {}
    for row in rows:
        by_file.setdefault(row["file"], []).append(row)
    with korean_path.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        lookup = {name: index + 1 for index, name in enumerate(archive.manifest())}
        print("\n## Battle")
        for name, file_rows in by_file.items():
            bmd = BmdFile(archive.read_entry(lookup[name]))
            texts = bmd.texts()
            for row in file_rows:
                raw = texts[row["idx"]].encode("utf-8")
                now = decode_proxy(raw)
                if now is None:
                    now = texts[row["idx"]]
                print(f"{lookup[name]}\t{row['idx']}\tuid={row['uid']}\t{name}")
                print(f"  JP={row['source_jp']}")
                print(f"  KO={now}")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    audit_logic(BUILD / "Logic_ending_key_ko_20260906.psarc.sdat")
    audit_battle(BUILD / "Battle_hud_labels_ko_20260906.psarc.sdat")


if __name__ == "__main__":
    main()
