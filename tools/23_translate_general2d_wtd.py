#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract and translate all Japanese length-prefixed strings in main WTD."""

from __future__ import annotations

import json
import re
import struct
import sys
import unicodedata
from pathlib import Path

import ctranslate2
import sentencepiece as spm

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psarc import PSARC
from textextract import is_jp


ENTRY = 3751
PROTECTED = re.compile(
    r"(<[^>]*>|%[-+0-9.]*[A-Za-z]|\\[nrt]|@[A-Za-z0-9_]*|"
    r"\[[^\]]*\]|\{[^}]*\})"
)


def parse_wtd(data: bytes) -> list[dict]:
    rows = []
    for offset in range(len(data) - 5):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        if not 2 <= length <= 4096 or offset + 4 + length > len(data):
            continue
        raw = data[offset + 4 : offset + 4 + length]
        if raw[-1] != 0 or b"\0" in raw[:-1]:
            continue
        try:
            text = raw[:-1].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(is_jp(ord(ch)) for ch in text):
            rows.append(
                {
                    "offset": offset,
                    "length": length,
                    "capacity": length - 1,
                    "jp": text,
                }
            )
    return rows


def load_existing_translations(root: Path) -> dict[str, str]:
    unique = [
        json.loads(line)
        for line in (root / "extract" / "unique_jp.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    translated = {}
    for path in sorted((root / "translated").glob("batch_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            uid, text = line.split("\t", 1)
            translated[int(uid)] = text
    return {
        row["jp"]: translated[row["uid"]]
        for row in unique
        if row["uid"] in translated
    }


class NLLB:
    def __init__(self, model_dir: Path):
        self.sp = spm.SentencePieceProcessor(
            model_file=str(model_dir / "sentencepiece.bpe.model")
        )
        self.translator = ctranslate2.Translator(
            str(model_dir), device="cpu", inter_threads=2, intra_threads=0
        )
        self.cache: dict[str, str] = {}

    def translate_many(self, texts: list[str]) -> dict[str, str]:
        pending = [
            text
            for text in dict.fromkeys(texts)
            if text not in self.cache and any(is_jp(ord(ch)) for ch in text)
        ]
        for start in range(0, len(pending), 24):
            batch = pending[start : start + 24]
            sources = [
                self.sp.encode(text, out_type=str) + ["</s>", "jpn_Jpan"]
                for text in batch
            ]
            results = self.translator.translate_batch(
                sources,
                target_prefix=[["kor_Hang"]] * len(batch),
                beam_size=2,
                max_decoding_length=256,
            )
            for source, result in zip(batch, results):
                tokens = [
                    token
                    for token in result.hypotheses[0]
                    if token not in ("kor_Hang", "</s>")
                ]
                value = self.sp.decode(tokens).strip()
                value = re.sub(r"^(그리고|또한)\s+", "", value)
                self.cache[source] = value
            print(
                f"translated segments {min(start + len(batch), len(pending))}/"
                f"{len(pending)}",
                flush=True,
            )
        return self.cache


def translate_preserving_tokens(text: str, model: NLLB) -> str:
    parts = PROTECTED.split(text)
    translated = []
    for part in parts:
        if not part:
            continue
        if PROTECTED.fullmatch(part) or not any(is_jp(ord(ch)) for ch in part):
            translated.append(part)
        else:
            translated.append(model.cache.get(part, part))
    return "".join(translated)


def main() -> None:
    root = Path("work_ogmd")
    out_dir = root / "general2d_translation"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = PSARC(str(root / "GENERAL2D.psarc")).read_entry(ENTRY)
    rows = parse_wtd(data)
    unique_texts = list(dict.fromkeys(row["jp"] for row in rows))
    existing = load_existing_translations(root)

    missing = [text for text in unique_texts if text not in existing]
    segments = []
    for text in missing:
        for part in PROTECTED.split(text):
            if (
                part
                and not PROTECTED.fullmatch(part)
                and any(is_jp(ord(ch)) for ch in part)
            ):
                segments.append(part)

    model = NLLB(root / "models" / "nllb-200-distilled-600M-ct2-int8")
    model.translate_many(segments)

    translations = dict(existing)
    for text in missing:
        translations[text] = translate_preserving_tokens(text, model)

    output_rows = []
    for row in rows:
        ko = translations[row["jp"]]
        output_rows.append(
            {
                **row,
                "ko": ko,
                "source": "existing" if row["jp"] in existing else "nllb",
                "jp_bytes": len(row["jp"].encode("utf-8")),
                "ko_bytes": len(ko.encode("utf-8")),
                "fits": len(ko.encode("utf-8")) <= row["capacity"],
            }
        )

    (out_dir / "wtd_strings.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in output_rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    unique_output = []
    seen = set()
    for row in output_rows:
        if row["jp"] in seen:
            continue
        seen.add(row["jp"])
        unique_output.append(
            {
                "uid": len(unique_output),
                "jp": row["jp"],
                "ko": row["ko"],
                "source": row["source"],
            }
        )
    (out_dir / "wtd_unique.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in unique_output
        ),
        encoding="utf-8",
        newline="\n",
    )

    korean_chars = {
        ch
        for row in output_rows
        for ch in row["ko"]
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3130 <= ord(ch) <= 0x318F
    }
    report = {
        "occurrences": len(output_rows),
        "unique": len(unique_output),
        "existing_exact": sum(row["source"] == "existing" for row in unique_output),
        "machine_translated": sum(row["source"] == "nllb" for row in unique_output),
        "over_capacity_occurrences": sum(not row["fits"] for row in output_rows),
        "korean_characters": len(korean_chars),
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
