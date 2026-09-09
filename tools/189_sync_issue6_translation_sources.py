#!/usr/bin/env python3
"""Issue #6 최종 교정을 재빌드용 번역 소스에 동기화한다."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PATCH = load("ogmd_issue6_patch", "188_patch_issue6_20260909.py")

SPECIAL = {
    "（너무 갑작스러워…….@　저희가 도착하기 전에 보다의 문이 열리면……）":
        "（너무 갑작스러워……@　우리가 도착하기도 전에 보다의 문이 열리면……）",
    "「알겠다. 각 기에 전한다」": "「네. 각 기에 전하겠습니다」",
    "「기동부대 각 기는 방금 전투로 소모됐습니다.@　게다가 제몬 몰터까지@　발사당하면……」":
        "「기동부대 각 기는 방금 전투로 소모됐습니다.@　게다가 제몬 몰터까지@　발사하면……」",
}
SPECIAL_JP = {
    "（急過ぎる……。@　私達が辿り着く前にヴォーダの門が開放されたら……）":
        SPECIAL["（너무 갑작스러워…….@　저희가 도착하기 전에 보다의 문이 열리면……）"],
    "「機動部隊各機は、先程の戦闘で消耗しています。@　それに加え、ゼモン・モルターを@　撃たれでもしたら……」":
        SPECIAL["「기동부대 각 기는 방금 전투로 소모됐습니다.@　게다가 제몬 몰터까지@　발사당하면……」"],
}


def fix(text: str) -> str:
    return SPECIAL.get(text, PATCH.normalize_names(text))


def main() -> None:
    stats = {"tsv": 0, "jp2ko": 0, "battle": 0}
    for path in sorted((ROOT / "translated").glob("batch_*.tsv")):
        out = []
        changed = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                out.append(line)
                continue
            uid, ko = line.split("\t", 1)
            new = fix(ko)
            if new != ko:
                stats["tsv"] += 1
                changed = True
            out.append(uid + "\t" + new)
        if changed:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")

    path = ROOT / "jp2ko.json"
    mapping = json.loads(path.read_text(encoding="utf-8"))
    for jp, ko in list(mapping.items()):
        new = SPECIAL_JP.get(jp, fix(ko))
        if new != ko:
            mapping[jp] = new
            stats["jp2ko"] += 1
    path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")

    path = ROOT / "battle_translation" / "battle_unique_draft.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        new = PATCH.RAIO_LINES.get(row["jp"], fix(row["ko"]))
        if new != row["ko"]:
            row["ko"] = new
            row["source"] = "issue6-review"
            stats["battle"] += 1
        rows.append(row)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
