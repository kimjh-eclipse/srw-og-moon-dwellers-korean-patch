from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psarc import PSARC
from sdat import SDATReader


ROOT = Path(rconfig.WORK_ROOT)
GAME = Path(rconfig.require('GAME_DIR'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


reverse: dict[str, str] = {}
for name in ("korean_font_map.tsv", "compact_aliases.tsv"):
    with (ROOT / "korean_build_v3" / name).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            reverse[row["proxy"]] = row["hangul"]


def decode(raw: bytes) -> str:
    text = raw.split(b"\0", 1)[0].decode("utf-8")
    return "".join(reverse.get(char, char) for char in text)


logic_path = GAME / "Logic.psarc.sdat"
with logic_path.open("rb") as stream:
    logic = PSARC(SDATReader(stream, 0))
    logic_entries = {entry: logic.read_entry(entry) for entry in (3, 4, 28)}

records = []
for line in (ROOT / "extract" / "master.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if Path(row.get("file", "")).name in {
        "ACEBonusData.dat",
        "AceFullTuneBonusData.dat",
        "Temp_AceFullTuneBonusData.dat",
    }:
        raw = logic_entries[int(row["entry"])][int(row["off"]):int(row["off"]) + int(row["blen"])]
        records.append((int(row["uid"]), decode(raw)))

texts = [text for _, text in records]
uid_texts: dict[int, list[str]] = {}
for uid, text in records:
    uid_texts.setdefault(uid, []).append(text)

general_path = GAME / "General2d.psarc.sdat"
with general_path.open("rb") as stream:
    general_raw = PSARC(SDATReader(stream, 0)).read_entry(3751)
general_text = "".join(reverse.get(char, char) for char in general_raw.decode("utf-8", errors="ignore"))

candidate_hashes = {
    "Common.psarc.sdat": sha(ROOT / "release_20260728_verified" / "Common.psarc.sdat"),
    "General2d.psarc.sdat": sha(ROOT / "korean_build_v3" / "General2d_menu_all_ui14_bootsafe_terrain_next_20260808.psarc.sdat"),
    "Logic.psarc.sdat": sha(ROOT / "korean_build_v3" / "Logic_ace_final_ui7_20260808.psarc.sdat"),
}
installed_hashes = {name: sha(GAME / name) for name in candidate_hashes}

result = {
    "hash_match": {name: installed_hashes[name] == candidate_hashes[name] for name in candidate_hashes},
    "installed_hashes": installed_hashes,
    "logic": {
        "records": len(records),
        "empty": sum(not text.strip() for text in texts),
        "kana_remaining": sum(bool(re.search(r"[\u3040-\u30ff]", text)) for text in texts),
        "bad_phrase_counts": {
            phrase: sum(phrase in text for text in texts)
            for phrase in ("하지만, 우리는", "크리티컬률 보정치", "명중보정", "지휘+", "(웃음)")
        },
        "uid_321": uid_texts.get(321),
        "uid_5742": uid_texts.get(5742),
    },
    "general2d": {
        "special_skill_long": general_text.count("특수스킬"),
        "special_skill_short": general_text.count("특수기"),
        "terrain_icons": {str(i): general_raw.count(f"<I={i}>".encode()) for i in range(223, 227)},
        "option_records_blank": {
            str(offset): not general_raw[offset + 4:offset + 4 + int.from_bytes(general_raw[offset:offset + 4], "big")].rstrip(b"\0")
            for offset in (675788, 675952, 1188640, 1188760, 1188880, 1189000)
        },
    },
}
print(json.dumps(result, ensure_ascii=False, indent=2))
