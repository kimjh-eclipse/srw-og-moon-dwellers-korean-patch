#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FTTF font.bin의 PS3 DXT5 알파 아틀라스를 해제한다.

font.bin 내부 텍스처:
  GCM format 0x88 (DXT5), 1024x4096, data offset 0x18600

PS3의 pitch=0 텍스처는 블록 단위 스위즐 가능성이 있으므로 linear,
Morton XY, Morton YX 세 후보를 모두 출력한다.
"""

from pathlib import Path
import argparse

import numpy as np
from PIL import Image


DATA_OFFSET = 0x18600
WIDTH = 1024
HEIGHT = 4096
BLOCK_BYTES = 16


def alpha_palette(a0: int, a1: int) -> tuple[int, ...]:
    if a0 > a1:
        return (
            a0,
            a1,
            (6 * a0 + a1) // 7,
            (5 * a0 + 2 * a1) // 7,
            (4 * a0 + 3 * a1) // 7,
            (3 * a0 + 4 * a1) // 7,
            (2 * a0 + 5 * a1) // 7,
            (a0 + 6 * a1) // 7,
        )
    return (
        a0,
        a1,
        (4 * a0 + a1) // 5,
        (3 * a0 + 2 * a1) // 5,
        (2 * a0 + 3 * a1) // 5,
        (a0 + 4 * a1) // 5,
        0,
        255,
    )


def spread8(v: int) -> int:
    """하위 8비트를 짝수 비트 위치로 펼친다."""
    v &= 0xFF
    v = (v | (v << 4)) & 0x0F0F
    v = (v | (v << 2)) & 0x3333
    v = (v | (v << 1)) & 0x5555
    return v


def block_index(x: int, y: int, mode: str) -> int:
    blocks_w = WIDTH // 4
    if mode == "linear":
        return y * blocks_w + x

    # 블록 격자는 256x1024. 공통 하위 8비트를 Morton으로 배열한 뒤
    # 남는 y 상위 2비트를 256x256 타일 번호로 붙인다.
    tile = (y >> 8) << 16
    lo_y = y & 0xFF
    if mode == "morton_xy":
        return tile | spread8(x) | (spread8(lo_y) << 1)
    if mode == "morton_yx":
        return tile | spread8(lo_y) | (spread8(x) << 1)
    raise ValueError(mode)


def decode_alpha(data: bytes, mode: str) -> np.ndarray:
    blocks_w = WIDTH // 4
    blocks_h = HEIGHT // 4
    expected = blocks_w * blocks_h * BLOCK_BYTES
    if len(data) != expected:
        raise ValueError(f"DXT5 크기 불일치: {len(data):#x} != {expected:#x}")

    image = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    for by in range(blocks_h):
        py = by * 4
        for bx in range(blocks_w):
            p = block_index(bx, by, mode) * BLOCK_BYTES
            a0, a1 = data[p], data[p + 1]
            palette = alpha_palette(a0, a1)
            bits = int.from_bytes(data[p + 2 : p + 8], "little")
            px = bx * 4
            for i in range(16):
                image[py + i // 4, px + i % 4] = palette[(bits >> (3 * i)) & 7]
    return image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "font",
        nargs="?",
        default="work_ogmd/font_dump/font.bin",
        help="원본 FTTF font.bin",
    )
    ap.add_argument(
        "--out-dir",
        default="work_ogmd/font_dump/dxt5",
        help="PNG 출력 폴더",
    )
    args = ap.parse_args()

    font_path = Path(args.font)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = font_path.read_bytes()
    texture = raw[DATA_OFFSET:]

    for mode in ("linear", "morton_xy", "morton_yx"):
        alpha = decode_alpha(texture, mode)
        full = Image.fromarray(alpha, "L")
        full_path = out_dir / f"font_alpha_{mode}_{WIDTH}x{HEIGHT}.png"
        preview_path = out_dir / f"font_alpha_{mode}_preview.png"
        full.save(full_path)
        full.resize((256, 1024), Image.Resampling.NEAREST).save(preview_path)
        print(full_path)
        print(preview_path)


if __name__ == "__main__":
    main()
