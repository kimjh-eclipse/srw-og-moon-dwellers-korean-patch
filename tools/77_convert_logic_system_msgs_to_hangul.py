#!/usr/bin/env python3
"""시스템 메시지를 프록시 CJK에서 진짜 한글로 되돌린다.

근거
----
RPCS3 로그에서 두 확인창의 실제 호출을 확인했다.

    cellMsgDialogOpen2(type=0x115, msgString="篠箍黍 廷¨鵬槌 廠臥緋峠¦. ...")  → 한자처럼 깨짐
    cellMsgDialogOpen2(type=0x15,  msgString="저장이 끝났습니다. ...")        → 정상

`cellMsgDialogOpen2` 는 게임 폰트가 아니라 시스템(오버레이) 폰트로 그린다. 따라서
인게임 텍스트 규약인 프록시 CJK 인코딩을 넣으면 프록시 글자가 그대로 한자로 보인다.
이 경로에 실리는 문자열은 진짜 한글 UTF-8 이어야 한다.

범위 (1차)
---------
저장 / 불러오기 / 시스템 데이터 / 시나리오 데이터 / 설치 / HDD 오류 계열만 바꾼다.
난이도 이름, 합체·분리, 갈아타기 안내처럼 게임이 직접 그릴 가능성이 있는 문자열은
건드리지 않는다. 잘못 바꾸면 지금 정상인 텍스트가 보이지 않게 된다.

이 스크립트는 인코딩만 바꾼다. 문구와 글자수 필드는 손대지 않는다.
원인 판정을 위해 변수를 하나로 유지하기 위함이다.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from psarc import PSARC
from psarc_fixed_entry_spans import rebuild_fixed_entry_spans
from sdat import decrypt_stream
from sdat_encode import encode


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "korean_build_v3"
SOURCE = BUILD / "Logic_system_dialogs_spirit_chain_fixed_20260812.psarc.sdat"
ORIGINAL = ROOT / "original_backups" / "Logic.psarc.sdat.orig"
OUTPUT = BUILD / "Logic_system_msgs_hangul_20260813.psarc.sdat"
REPORT = BUILD / "logic_system_msgs_hangul_20260813_report.json"
ENTRY = 22

MAP_FILES = (
    "korean_font_map.tsv",
    "compact_aliases.tsv",
    "general2d_compact_aliases.tsv",
    "logic_suffix_aliases.tsv",
)

# 1차 대상: 저장 시스템 계열만
INCLUDE = (
    "저장", "불러오", "시스템 데이터", "시나리오 데이터", "시나리오데이터",
    "설치", "ＨＤＤ", "데이터가 없습니다", "데이터가 손상", "재시도",
    "작성할까요", "사용자가 만든", "스테이지 데이터", "버전이 다릅니다",
    "타이틀로 돌아갑니다", "데이터 쓰기", "데이터 읽기",
)
# 게임이 직접 그릴 수 있는 것 — 제외
EXCLUDE = ("모드", "합체", "분리", "갈아타기", "탑승", "파일럿", "부대")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_proxy_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in MAP_FILES:
        path = BUILD / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                proxy, hangul = row.get("proxy"), row.get("hangul")
                if proxy and hangul:
                    mapping.setdefault(proxy, hangul)
    return mapping


def spans(original_entry: bytes) -> dict[int, int]:
    """오프셋별 원본 슬롯 크기. 제자리 교체이므로 이 범위를 넘으면 안 된다."""
    result = {}
    off = 0
    while off < len(original_entry):
        end = original_entry.find(b"\0", off)
        if end < 0:
            break
        if end > off:
            result[off] = end - off
        off = end + 1
    return result


def pad(path: Path, size: int) -> None:
    current = path.stat().st_size
    if current > size:
        raise AssertionError(f"encoded SDAT grew: {current} > {size}")
    if current < size:
        with path.open("ab") as stream:
            stream.write(b"\0" * (size - current))


def main() -> None:
    proxy_to_hangul = load_proxy_map()
    source_plain = BUILD / "LOGIC_sysmsg_source.psarc"
    output_plain = BUILD / "LOGIC_sysmsg_out.psarc"
    verify_plain = BUILD / "LOGIC_sysmsg_verify.psarc"
    source_archive = candidate = original_archive = None
    try:
        with SOURCE.open("rb") as src, source_plain.open("wb") as dst:
            decrypt_stream(src, 0, dst)
        original_plain = BUILD / "LOGIC_sysmsg_original.psarc"
        with ORIGINAL.open("rb") as src, original_plain.open("wb") as dst:
            decrypt_stream(src, 0, dst)

        source_archive = PSARC(str(source_plain))
        original_archive = PSARC(str(original_plain))
        entry = bytearray(source_archive.read_entry(ENTRY))
        slot = spans(original_archive.read_entry(ENTRY))

        changes = []
        skipped = []
        off = 0
        while off < len(entry):
            end = entry.find(b"\0", off)
            if end < 0:
                break
            chunk = bytes(entry[off:end])
            if 4 <= len(chunk) <= 400:
                try:
                    text = chunk.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
                if text:
                    decoded = "".join(proxy_to_hangul.get(c, c) for c in text)
                    is_proxy = decoded != text
                    wanted = any(k in decoded for k in INCLUDE)
                    blocked = any(k in decoded for k in EXCLUDE)
                    if is_proxy and wanted and not blocked:
                        span = slot.get(off, 0)
                        payload = decoded.encode("utf-8")
                        record = {
                            "offset": off,
                            "span": span,
                            "before_bytes": len(chunk),
                            "after_bytes": len(payload),
                            "text": decoded,
                        }
                        if span and len(payload) <= span:
                            entry[off : off + span] = payload + b"\0" * (span - len(payload))
                            changes.append(record)
                        else:
                            record["reason"] = "span 초과 — 문구 조정 필요"
                            skipped.append(record)
            off = end + 1

        if not changes:
            raise AssertionError("변환 대상이 없습니다")

        fixed = rebuild_fixed_entry_spans(
            source_plain, {ENTRY: bytes(entry)}, output_plain
        )
        encode(str(output_plain), SOURCE.read_bytes()[:0x100], str(OUTPUT))
        pad(OUTPUT, SOURCE.stat().st_size)

        with OUTPUT.open("rb") as src, verify_plain.open("wb") as dst:
            decrypt_stream(src, 0, dst)
        candidate = PSARC(str(verify_plain))
        if candidate.manifest() != source_archive.manifest():
            raise AssertionError("manifest mismatch")
        mismatches = [
            index
            for index in range(source_archive.n)
            if candidate.read_entry(index)
            != (bytes(entry) if index == ENTRY else source_archive.read_entry(index))
        ]
        if mismatches:
            raise AssertionError(f"semantic mismatches: {mismatches[:20]}")

        report = {
            "source": str(SOURCE),
            "output": str(OUTPUT),
            "source_sha256": digest(SOURCE),
            "output_sha256": digest(OUTPUT),
            "entry": ENTRY,
            "converted": len(changes),
            "skipped": len(skipped),
            "changes": changes,
            "skipped_records": skipped,
            "semantic_mismatches": 0,
            "size": OUTPUT.stat().st_size,
            **fixed,
        }
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in report.items()
                          if k not in ("changes", "skipped_records")},
                         ensure_ascii=False, indent=2))
        print("변환 %d건 / 보류 %d건" % (len(changes), len(skipped)))
        for record in skipped:
            print("  보류 off=%d  %d/%d바이트  %r"
                  % (record["offset"], record["after_bytes"], record["span"],
                     record["text"][:40]))
    finally:
        for archive in (source_archive, candidate, original_archive):
            if archive is not None:
                archive.f.close()
        for temp in (source_plain, output_plain, verify_plain,
                     BUILD / "LOGIC_sysmsg_original.psarc"):
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
