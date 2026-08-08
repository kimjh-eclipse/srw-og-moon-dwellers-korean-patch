#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a resumable Korean draft corpus for Battle BMD messages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import ctranslate2
import sentencepiece as spm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textextract import is_jp


PROTECTED = re.compile(
    r"(<[^>]*>|%[-+0-9.]*[A-Za-z]|\\[nrt]|@[A-Za-z0-9_]*|"
    r"\[[^\]]*\]|\{[^}]*\})"
)


class NLLB:
    def __init__(self, model_dir: Path) -> None:
        self.sp = spm.SentencePieceProcessor(
            model_file=str(model_dir / "sentencepiece.bpe.model")
        )
        self.translator = ctranslate2.Translator(
            str(model_dir), device="cpu", inter_threads=2, intra_threads=0
        )

    def translate(self, parts: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for start in range(0, len(parts), 24):
            batch = parts[start : start + 24]
            sources = [
                self.sp.encode(text, out_type=str) + ["</s>", "jpn_Jpan"]
                for text in batch
            ]
            outputs = self.translator.translate_batch(
                sources,
                target_prefix=[["kor_Hang"]] * len(batch),
                beam_size=2,
                max_decoding_length=256,
            )
            for source, output in zip(batch, outputs):
                tokens = [
                    token for token in output.hypotheses[0]
                    if token not in ("kor_Hang", "</s>")
                ]
                result[source] = self.sp.decode(tokens).strip()
            print(f"translated {min(start + len(batch), len(parts))}/{len(parts)}", flush=True)
        return result


def pieces(text: str) -> list[str]:
    return [
        part for part in PROTECTED.split(text)
        if part and not PROTECTED.fullmatch(part)
        and any(is_jp(ord(ch)) for ch in part)
    ]


def main() -> None:
    root = Path("work_ogmd")
    out_dir = root / "battle_translation"
    out_dir.mkdir(exist_ok=True)
    output = out_dir / "battle_unique_draft.jsonl"
    rows = [
        json.loads(line)
        for line in (root / "extract_bmd" / "unique_jp.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    old: dict[str, str] = {}
    for path in sorted((root / "translated").glob("batch_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            old[int(uid)] = text.replace("\\n", "\n").replace("\\t", "\t")
    logic = [
        json.loads(line)
        for line in (root / "extract" / "unique_jp.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    reuse = {row["jp"]: old[row["uid"]] for row in logic if row["uid"] in old}
    needed = list(dict.fromkeys(part for row in rows if row["jp"] not in reuse for part in pieces(row["jp"])))
    model = NLLB(root / "models" / "nllb-200-distilled-600M-ct2-int8")
    translated = model.translate(needed)
    result = []
    for uid, row in enumerate(rows):
        jp = row["jp"]
        if jp in reuse:
            ko, source = reuse[jp], "logic-reuse"
        else:
            ko = "".join(
                part if not (part and not PROTECTED.fullmatch(part) and any(is_jp(ord(ch)) for ch in part))
                else translated[part]
                for part in PROTECTED.split(jp)
            )
            source = "nllb"
        result.append({"uid": uid, "jp": jp, "ko": ko, "source": source})
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result),
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"unique": len(result), "reused": sum(r["source"] == "logic-reuse" for r in result), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
