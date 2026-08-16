#!/usr/bin/env python3
"""Render DDS/PNG assets into a labeled PNG contact sheet for review."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pattern", default="*.dds")
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--cell-width", type=int, default=420)
    parser.add_argument("--cell-height", type=int, default=240)
    args = parser.parse_args()

    files = sorted(args.source.rglob(args.pattern))
    if not files:
        raise SystemExit("no matching images")
    label_height = 32
    rows = (len(files) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB",
        (args.columns * args.cell_width, rows * (args.cell_height + label_height)),
        "#20242b",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    for index, path in enumerate(files):
        image = Image.open(path).convert("RGBA")
        backdrop = Image.new("RGBA", image.size, "#707070")
        backdrop.alpha_composite(image)
        backdrop.thumbnail((args.cell_width - 16, args.cell_height - 16), Image.Resampling.LANCZOS)
        column = index % args.columns
        row = index // args.columns
        x = column * args.cell_width
        y = row * (args.cell_height + label_height)
        px = x + (args.cell_width - backdrop.width) // 2
        py = y + (args.cell_height - backdrop.height) // 2
        sheet.paste(backdrop.convert("RGB"), (px, py))
        label = path.relative_to(args.source).as_posix()
        draw.text((x + 8, y + args.cell_height + 6), label, fill="white", font=font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"saved={args.output} images={len(files)} size={sheet.size}")


if __name__ == "__main__":
    main()
