#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create an auditable first-pass Korean translation QA report.

This script is intentionally read-only.  It reviews every translated TSV row
against its Japanese source and writes a JSON report plus JSONL findings.  A
finding is a review queue, not an automatic rewrite: game control codes and
short labels need contextual judgement before changing them.
"""
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

from __future__ import annotations

import json
import importlib.util
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("work_ogmd")
TRANSLATED = ROOT / "translated"
MASTER = ROOT / "extract" / "master.jsonl"
OUT = ROOT / "review_v1"

TAG = re.compile(r"<[^>\n]*>|\]-\d+|\[[^\]\n]*\]")
CONTROL_TAG = re.compile(r"\]-\d+|\[[^\]\n]*\]")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
HANGUL = re.compile(r"[\uac00-\ud7a3]")
DOUBLE_SPACE = re.compile(r"(?<!@) {2,}")
BROKEN_QUOTES = re.compile(r"[「」『』]|(?:^|\s)[\"”](?:\s|$)")

# These are source-language terms that must not survive in a Korean target
# except inside an explicitly preserved code/control tag.
TERM_RULES = load_table('TERM_RULES')


def unescape_tsv(text: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "\\" or index + 1 >= len(text):
            output.append(text[index])
            index += 1
            continue
        code = text[index + 1]
        if code == "n":
            output.append("\n")
        elif code == "t":
            output.append("\t")
        elif code == "\\":
            output.append("\\")
        else:
            output.extend(("\\", code))
        index += 2
    return "".join(output)


def tags(text: str) -> Counter[str]:
    # <...> is the game's visible dictionary-link syntax, not a binary
    # control token.  Its contents are intentionally translated by the
    # builder; only the bracketed runtime controls must be byte-for-byte
    # identical.
    return Counter(CONTROL_TAG.findall(text))


def strip_tags(text: str) -> str:
    return TAG.sub("", text)


def load_translations() -> dict[int, str]:
    rows: dict[int, str] = {}
    for path in sorted(TRANSLATED.glob("batch_*.tsv")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            uid, sep, text = raw.partition("\t")
            if not sep:
                raise ValueError(f"malformed line in {path}: {raw!r}")
            rows[int(uid)] = unescape_tsv(text)
    return rows


def load_builder():
    """Use the exact normalization that the package builder will apply."""
    path = ROOT / "27_build_logic_translation.py"
    spec = importlib.util.spec_from_file_location("logic_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builder = load_builder()
    translations = load_translations()
    master = [json.loads(line) for line in MASTER.read_text(encoding="utf-8").splitlines()]
    by_uid: dict[int, list[dict]] = defaultdict(list)
    for row in master:
        if row.get("psarc") == "LOGIC":
            by_uid[row["uid"]].append(row)

    findings: list[dict] = []
    counts: Counter[str] = Counter()
    for uid, raw_target in translations.items():
        target = builder.normalize_translation(raw_target)
        sources = by_uid.get(uid, [])
        if not sources:
            # The shared translated folder also contains rows extracted from
            # other archives.  They are outside this LOGIC audit rather than
            # missing translations, so record them only as scope exclusions.
            counts["outside_logic_scope"] += 1
            continue
        # A UID can legitimately occur in more than one entry.  Report only
        # collisions with different Japanese source text, because those cannot
        # safely share one translation row.
        source_texts = {row["text"] for row in sources}
        if len(source_texts) > 1:
            findings.append(
                {
                    "kind": "uid_collision",
                    "uid": uid,
                    "sources": sorted(source_texts),
                    "target": target,
                    "occurrences": len(sources),
                }
            )
            counts["uid_collision"] += 1
        source = sources[0]["text"]
        if tags(source) != tags(target):
            findings.append(
                {"kind": "tag_mismatch", "uid": uid, "source": source, "target": target}
            )
            counts["tag_mismatch"] += 1
        visible = strip_tags(target)
        if JAPANESE.search(visible):
            findings.append(
                {"kind": "japanese_remaining", "uid": uid, "source": source, "target": target}
            )
            counts["japanese_remaining"] += 1
        if DOUBLE_SPACE.search(visible):
            findings.append(
                {"kind": "double_space", "uid": uid, "source": source, "target": target}
            )
            counts["double_space"] += 1
        if BROKEN_QUOTES.search(visible):
            findings.append(
                {"kind": "quote_review", "uid": uid, "source": source, "target": target}
            )
            counts["quote_review"] += 1
        if source and target == source and JAPANESE.search(strip_tags(source)):
            findings.append(
                {"kind": "unchanged_japanese", "uid": uid, "source": source, "target": target}
            )
            counts["unchanged_japanese"] += 1
        for japanese, korean in TERM_RULES.items():
            if japanese in visible:
                findings.append(
                    {
                        "kind": "term_untranslated",
                        "uid": uid,
                        "term": japanese,
                        "expected": korean,
                        "source": source,
                        "target": target,
                    }
                )
                counts["term_untranslated"] += 1

    OUT.mkdir(exist_ok=True)
    with (OUT / "findings.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for finding in findings:
            stream.write(json.dumps(finding, ensure_ascii=False) + "\n")
    report = {
        "translated_uid_rows": len(translations),
        "logic_master_occurrences": sum(len(rows) for rows in by_uid.values()),
        "findings": dict(sorted(counts.items())),
        "total_findings": len(findings),
    }
    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
