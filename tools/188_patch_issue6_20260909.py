#!/usr/bin/env python3
"""GitHub issue #6: 인명 통일, 35~38화 문장/말투, 라이오 전투대사를 수정한다."""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from bmd_rebuild import BmdFile
from psarc import PSARC
from psarc_write import enable_zopfli, rebuild_var
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE_LOGIC = BUILD / "Logic_ending_key_ko_20260906.psarc.sdat"
SOURCE_BATTLE = BUILD / "Battle_hud_labels_ko_20260906.psarc.sdat"
OUTPUT_LOGIC = BUILD / "Logic_issue6_ko_20260909.psarc.sdat"
OUTPUT_BATTLE = BUILD / "Battle_issue6_ko_20260909.psarc.sdat"
REPORT = BUILD / "issue6_20260909_report.json"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREV = load("ogmd_issue6_prev", "163_patch_reports_20260824.py")
proxy = PREV.proxy
decode_proxy = PREV.decode_proxy
finish = PREV.finish
digest = PREV.digest
restore_retail_time = PREV.restore_retail_time
BASE = PREV.BASE
enable_zopfli()

JP_NAME_TOKENS = (
    "ヘルルーガ", "グ＝ランドン", "フー＝ルー", "ゴモウドッカ",
    "ゴライクンル", "イング",
)

SPECIAL_LOGIC = {
    ("/Dat/logic/talk/ls035.bin", 0x692C): "「네」",
    ("/Dat/logic/talk/ls035.bin", 0x7146):
        "（너무 갑작스러워……@　우리가 도착하기도 전에 보다의 문이 열리면……）",
    ("/Dat/logic/talk/ls037.bin", 0x2EB3):
        "「네. 각 기에 전하겠습니다」",
    ("/Dat/logic/talk/ls038.bin", 0x1AF6):
        "「기동부대 각 기는 방금 전투로 소모됐습니다.@　게다가 제몬 몰터까지@　발사하면……」",
}

RAIO_LINES = {
    "「雷鳳をバックアップ」": "라이오를 지원한다",
    "G!「やるぞ、雷鳳……！」": "G!「간다, 라이오……!」",
    "「雷鳳！　お前に全てを懸ける！」": "「라이오!　네게 모든 것을 건다!」",
    "「行くぞ、雷鳳！　俺達の戦いの時だ！」": "「가자, 라이오!　우리들의 싸움이 시작된다!」",
    "「雷鳳！　奴をぶっ潰すぞ！」": "「라이오!　녀석을 박살 내자!」",
    "「雷鳳に、俺の魂を重ねる！」": "「라이오에 내 혼을 싣는다!」",
    "「気合は十分……！　それを雷鳳でぶつける！」": "「기합은 충분해……!　라이오로 부딪친다!」",
    "「ラフトクランズの速さを超えるぞ、雷鳳！」": "「라프트크란즈의 속도를 뛰어넘자, 라이오!」",
    "「ヘルルーガ！/　お前の野望は、俺と雷鳳が蹴り砕く！」":
        "「헬루가!/　네 야망은 나와 라이오가 걷어차 부숴 주마!」",
    "「やるぞ！　雷鳳で竜退治だ！」": "「해보자!　라이오로 용 퇴치다!」",
    "「やるぞ、雷鳳！　悪霊退治だ！」": "「가자, 라이오!　악령 퇴치다!」",
    "「カーナだろうと雷鳳を止められるものか！」": "「카나라도 라이오를 막을 순 없어!」",
    "「ミナキの……俺の雷鳳は、まだ戦える！」": "「미나키의…… 내 라이오는 아직 싸울 수 있어!」",
    "「踏ん張れ、雷鳳……！　ここが勝負所だ！」": "「버텨라, 라이오……!　지금이 승부처다!」",
    "「俺の闘志も雷鳳も、まだ死んじゃいない！」": "「내 투지도 라이오도 아직 죽지 않았어!」",
    "「スカルナイト！/　俺と雷鳳を倒したいのなら全力で来い！」":
        "「스컬 나이트!/　나와 라이오를 쓰러뜨리고 싶다면 전력으로 덤벼라!」",
    "「雷鳳の痛みは俺の痛みだ！　これ以上はやらせん！」":
        "「라이오의 아픔은 내 아픔이다!　더는 못 하게 한다!」",
    "「戦うぞ、雷鳳！　俺はまだ動けるんだ！」": "「싸우자, 라이오!　난 아직 움직일 수 있어!」",
    "「俺と雷鳳が一つになっている……！」": "「나와 라이오가 하나가 됐어……!」",
    "「いいぞ、雷鳳！　反応はばっちりだ！」": "「좋아, 라이오!　반응은 완벽해!」",
    "「いいぞ、雷鳳！　俺達はやれる！」": "「좋아, 라이오!　우린 할 수 있어!」",
    "「カロ＝ラン、雷鳳はここにいるぞ！」": "「카로 란, 라이오는 여기에 있다!」",
    "「踏ん張れ、雷鳳！」": "「버텨라, 라이오!」",
    "「俺達も行くぞ、雷鳳！」": "「우리도 가자, 라이오!」",
    "「耐えろよ、雷鳳！」": "「버텨, 라이오!」",
    "「ブロックだ、雷鳳！」": "「막아라, 라이오!」",
    "「気合で耐えるぞ、雷鳳！」": "「기합으로 버틴다, 라이오!」",
    "「飛べ、雷鳳！」": "「날아라, 라이오!」",
    "「決めるぞ、雷鳳！」": "「끝내자, 라이오!」",
}


def normalize_names(text: str) -> str:
    replacements = (
        ("헤루루가", "헬루가"), ("헤루가", "헬루가"), ("헤를루", "헬루가"),
        ("그 란돈", "구 랜든"), ("구 란돈", "구 랜든"),
        ("구 랜던", "구 랜든"), ("구 란던", "구 랜든"),
        ("푸＝루 무루", "후 루 무르"), ("푸＝루 무르", "후 루 무르"),
        ("후＝루 무루", "후 루 무르"), ("후＝루 무르", "후 루 무르"),
        ("푸 루 무루", "후 루 무르"), ("푸 루 무르", "후 루 무르"),
        ("후 루 무루", "후 루 무르"),
        ("푸＝루", "후 루"), ("후＝루", "후 루"), ("푸 루", "후 루"),
        ("고모우드카", "고모우돗카"), ("고모도카", "고모우돗카"),
        ("고모우돗커", "고모우돗카"),
        ("고라이쿤르", "골라이큰르"), ("고라이큰루", "골라이큰르"),
        ("고라이큰르", "골라이큰르"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return re.sub(r"(?<![가-힣])잉(?!그|[가-힣])", "잉그", text)


def field(data: bytes, offset: int) -> bytes:
    end = data.find(b"\0", offset)
    return data[offset:] if end < 0 else data[offset:end]


def finish_var(source: Path, output: Path, plain: Path, modified: dict,
               retail_name: str) -> dict:
    out_plain = BUILD / (plain.stem + "_out.psarc")
    try:
        size = rebuild_var(str(plain), modified, str(out_plain))
        encode(str(out_plain), source.read_bytes()[:0x100], str(output))
        if output.stat().st_size > source.stat().st_size:
            raise AssertionError(f"{output.name}: SDAT 크기 초과")
        BASE.pad_file(output, source.stat().st_size)
        with output.open("rb") as stream:
            archive = PSARC(SDATReader(stream, 0))
            for entry, expected in modified.items():
                if archive.read_entry(entry) != expected:
                    raise AssertionError(f"{output.name}: entry {entry} 재읽기 불일치")
        restore_retail_time(output, retail_name)
        return {"pack": {"mode": "variable", "logical_size": size},
                "sha256": digest(output)}
    finally:
        for temporary in (plain, out_plain):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def load_logic_rows() -> list[dict]:
    rows = []
    for line in (ROOT / "extract_all" / "master_all.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["psarc"] != "LOGIC":
            continue
        if any(token in row["text"] for token in JP_NAME_TOKENS) or (row["file"], row["off"]) in SPECIAL_LOGIC:
            rows.append(row)
    return rows


def build_logic() -> dict:
    rows = load_logic_rows()
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["entry"]].append(row)
    modified = {}
    changes = []
    with SOURCE_LOGIC.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, entry_rows in grouped.items():
            data = bytearray(archive.read_entry(entry))
            changed = False
            for row in sorted(entry_rows, key=lambda r: r["off"]):
                raw = field(bytes(data), row["off"])
                before = decode_proxy(raw)
                if before is None:
                    continue
                after = SPECIAL_LOGIC.get((row["file"], row["off"]), normalize_names(before))
                if after == before:
                    continue
                encoded = proxy(after)
                capacity = row["blen"]
                if len(encoded) > capacity:
                    raise AssertionError(f"Logic 용량 초과 {row['file']} 0x{row['off']:X}: {len(encoded)}>{capacity}")
                data[row["off"]:row["off"] + capacity] = encoded + b"\0" * (capacity - len(encoded))
                changes.append({"entry": entry, "file": row["file"], "offset": hex(row["off"]),
                                "jp": row["text"], "before": before, "after": after})
                changed = True
            if changed:
                modified[entry] = bytes(data)
    plain = BUILD / "_issue6_logic_source.psarc"
    with SOURCE_LOGIC.open("rb") as source, plain.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)
    result = finish_var(SOURCE_LOGIC, OUTPUT_LOGIC, plain, modified,
                        "Logic.psarc.sdat.orig")
    result.update({"changes": changes, "entries": sorted(modified)})
    return result


def build_battle() -> dict:
    rows = [json.loads(line) for line in
            (ROOT / "issue6_battle_audit.jsonl").read_text(encoding="utf-8").splitlines()]
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["entry"]].append(row)
    modified = {}
    changes = []
    with SOURCE_BATTLE.open("rb") as stream:
        archive = PSARC(SDATReader(stream, 0))
        for entry, entry_rows in grouped.items():
            data = archive.read_entry(entry)
            bmd = BmdFile(data)
            texts = bmd.texts()
            replacements = {}
            seen = set()
            for row in entry_rows:
                key = (row["idx"], row["jp"])
                if key in seen:
                    continue
                seen.add(key)
                before = decode_proxy(texts[row["idx"]].encode("utf-8"))
                if before is None:
                    continue
                after = RAIO_LINES.get(row["jp"], normalize_names(before))
                if after == before:
                    continue
                if after.count("/") != row["jp"].count("/"):
                    raise AssertionError(f"Battle 줄바꿈 수 불일치: {row['jp']}")
                replacements[row["idx"]] = proxy(after).decode("utf-8")
                changes.append({"entry": entry, "file": row["file"], "idx": row["idx"],
                                "jp": row["jp"], "before": before, "after": after})
            if replacements:
                rebuilt = bmd.replace_variable(replacements)
                if len(rebuilt) > len(data):
                    raise AssertionError(f"Battle entry {entry} 크기 증가")
                # 최신 Battle BMD에는 문자열 풀 뒤에 충분한 NUL 여유가 있다.
                # 새 문자열 풀 끝에 그 차이만큼 NUL을 넣어 푸터 위치와 엔트리
                # 크기를 원래대로 유지하면 PSARC 전체 재배치를 피할 수 있다.
                parsed = BmdFile(rebuilt, pool_start=bmd.pool_start)
                pool_end = parsed.records[-1][0] + parsed.records[-1][1]
                pad = len(data) - len(rebuilt)
                fixed = rebuilt[:pool_end] + b"\0" * pad + rebuilt[pool_end:]
                if len(fixed) != len(data):
                    raise AssertionError(f"Battle entry {entry} 패딩 실패")
                modified[entry] = fixed
    plain = BUILD / "_issue6_battle_source.psarc"
    with SOURCE_BATTLE.open("rb") as source, plain.open("wb") as target:
        logical_size, _ = decrypt_stream(source, 0, target)
    result = finish(SOURCE_BATTLE, OUTPUT_BATTLE, plain, modified, logical_size,
                    "Battle.psarc.sdat.orig", fixed_spans=True, recompress_all=True)
    result.update({"changes": changes, "entries": sorted(modified)})
    return result


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    logic = build_logic()
    print(f"Logic: {len(logic['changes'])}건 / {len(logic['entries'])}엔트리 / {logic['sha256']}", flush=True)
    battle = build_battle()
    print(f"Battle: {len(battle['changes'])}건 / {len(battle['entries'])}엔트리 / {battle['sha256']}", flush=True)
    report = {"issue": 6, "date": "2026-09-09", "Logic": logic, "Battle": battle}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
