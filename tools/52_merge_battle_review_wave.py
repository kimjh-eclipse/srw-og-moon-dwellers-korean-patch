#!/usr/bin/env python3
"""Merge one directly translated 1,000-UID battle review wave."""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "battle_review_next"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("start", type=int)
    parser.add_argument("end", type=int)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    if args.end < args.start:
        raise AssertionError("end UID must not precede start UID")

    draft = [
        json.loads(line)
        for line in (ROOT / "battle_translation" / "battle_unique_draft.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    translations = {}
    for name in args.inputs:
        path = REVIEW / name
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            uid_text, ko = line.split("\t", 1)
            uid = int(uid_text)
            if uid in translations:
                raise AssertionError(f"duplicate UID {uid} in {path.name}:{number}")
            translations[uid] = ko

    expected = list(range(args.start, args.end + 1))
    if sorted(translations) != expected:
        missing = sorted(set(expected) - set(translations))
        extra = sorted(set(translations) - set(expected))
        raise AssertionError(f"invalid UID coverage; missing={missing[:10]} extra={extra[:10]}")

    rows = []
    for uid in expected:
        source = draft[uid]["jp"]
        ko = translations[uid]
        if not ko.strip() or source.count("/") != ko.count("/"):
            raise AssertionError(f"invalid translation at UID {uid}")
        rows.append({"uid": uid, "source": source, "new_ko": ko})

    output = REVIEW / f"review_{args.start}_{args.end}.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
