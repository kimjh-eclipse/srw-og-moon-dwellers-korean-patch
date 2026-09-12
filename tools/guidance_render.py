#!/usr/bin/env python3
"""가이던스 본문 이미지(967x392 BGRA)에 한글을 그린다.

원본은 배경이 투명하고 글자만 있는 오버레이다. 스크린샷·아이콘·유닛 그림은
`keep` 사각형으로 남기고 나머지를 지운 뒤, 같은 자리에 한글을 다시 그린다.

글자 모양: 맑은 고딕 볼드, 검은 테두리 2px, 원본과 같은 색.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 967, 392
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_REG = r"C:\Windows\Fonts\malgun.ttf"
OUTLINE = (0, 0, 0, 255)

WHITE = "#FFFFFF"
ORANGE = "#FF8000"
GREEN = "#00FF00"
RED = "#FF0000"
BLUE = "#006AFF"
YELLOW = "#FFD000"

# 맑은 고딕에 없는 글자를 같은 뜻의 글자로 바꾼다(가운뎃점).
SUBSTITUTE = str.maketrans({"・": "ㆍ"})

_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = (FONT_BOLD if bold else FONT_REG, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(key[0], key[1])
    return _cache[key]


def load_png(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def clear_text(image: Image.Image, keep) -> Image.Image:
    """keep 사각형 안만 남기고 전부 투명하게.

    항목이 (x, y, w, h) 면 제자리에, (x, y, w, h, dx, dy) 면 (dx, dy) 로 옮겨 붙인다.
    한글이 일본어보다 짧아 배지·버튼 그림 앞에 빈 자리가 생길 때 옮기는 데 쓴다.
    """
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for item in keep:
        x, y, w, h = item[:4]
        target = (item[4], item[5]) if len(item) == 6 else (x, y)
        out.paste(image.crop((x, y, x + w, y + h)), target)
    return out


def draw_line(draw: ImageDraw.ImageDraw, x: int, y: int, size: int,
              parts, stroke: int = 2, bold: bool = True) -> int:
    """(글자, 색) 조각들을 이어 그린다. 반환: 끝 x 좌표."""
    face = font(size, bold)
    cursor = x
    for text, color in parts:
        text = text.translate(SUBSTITUTE)
        draw.text((cursor, y), text, font=face, fill=color,
                  stroke_width=stroke, stroke_fill=OUTLINE)
        cursor += int(draw.textlength(text, font=face))
    return cursor


def measure(parts, size: int, bold: bool = True) -> int:
    face = font(size, bold)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    return int(sum(probe.textlength(t.translate(SUBSTITUTE), font=face) for t, _ in parts))


def render_page(source: Path, spec: dict) -> Image.Image:
    image = clear_text(load_png(source), spec.get("keep", []))
    draw = ImageDraw.Draw(image)
    for line in spec["lines"]:
        draw_line(draw, line["x"], line["y"], line.get("size", 22),
                  line["parts"], line.get("stroke", 2), line.get("bold", True))
    return image


def to_dds(image: Image.Image, template: bytes) -> bytes:
    """원본 DDS 헤더를 그대로 쓰고 픽셀만 갈아 끼운다(32bit BGRA, 밉맵 없음)."""
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"크기가 다르다: {image.size}")
    r, g, b, a = image.split()
    payload = Image.merge("RGBA", (b, g, r, a)).tobytes()
    if len(payload) != len(template) - 128:
        raise ValueError("픽셀 크기 불일치")
    return template[:128] + payload
