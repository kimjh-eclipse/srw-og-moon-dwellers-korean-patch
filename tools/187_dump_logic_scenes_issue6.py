#!/usr/bin/env python3
"""Issue #6의 35~38화 인터미션 문자열을 최신 Logic에서 덤프한다."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from psarc import PSARC
from sdat import SDATReader

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_issue6_ko_20260909.psarc.sdat"
OUTPUT = ROOT / "issue6_logic_scenes_verify.jsonl"
FILES = {f"/Dat/logic/talk/ls{n:03d}.bin" for n in range(35, 39)}


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


decode_proxy = load("ogmd_issue6_prev", "163_patch_reports_20260824.py").decode_proxy


def field(data: bytes, offset: int) -> bytes:
    end = data.find(b"\0", offset)
    return data[offset:] if end < 0 else data[offset:end]


def main() -> None:
    rows = []
    for line in (ROOT / "extract_all" / "master_all.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["psarc"] == "LOGIC" and row["file"] in FILES:
            rows.append(row)
    by_entry: dict[int, list[dict]] = {}
    for row in rows:
        by_entry.setdefault(row["entry"], []).append(row)
    output = []
    with SOURCE.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, entry_rows in by_entry.items():
            data = archive.read_entry(entry)
            for row in entry_rows:
                raw = field(data, row["off"])
                ko = decode_proxy(raw)
                if ko is None:
                    ko = raw.decode("utf-8", "replace")
                output.append({"entry": entry, "file": row["file"], "off": row["off"],
                               "jp": row["text"], "ko": ko})
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    print(f"{len(output)}건 -> {OUTPUT}")


if __name__ == "__main__":
    main()
