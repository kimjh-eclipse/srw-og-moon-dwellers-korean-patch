#!/usr/bin/env python3
"""Patch exFont01 icon atlas: Korean terrain labels and blank option debris."""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from psarc import PSARC
from psarc_fixed_blocks import rebuild_fixed_blocks
from psarc_write import rebuild
from sdat import SDATReader, decrypt_stream
from sdat_encode import encode
import config  # 경로 설정 — 환경변수 OGMD_* 로 바꿀 수 있다

ENTRY = 4
TEX = 0x1E80
WIDTH = 1024
HEIGHT = 2560
BLOCKS_X = WIDTH // 4
DESC = 0x454


def alpha_palette(a0, a1):
    if a0 > a1:
        return (a0, a1, (6*a0+a1)//7, (5*a0+2*a1)//7,
                (4*a0+3*a1)//7, (3*a0+4*a1)//7,
                (2*a0+5*a1)//7, (a0+6*a1)//7)
    return (a0, a1, (4*a0+a1)//5, (3*a0+2*a1)//5,
            (2*a0+3*a1)//5, (a0+4*a1)//5, 0, 255)


def decode_block(block: bytes) -> list[int]:
    pal = alpha_palette(block[0], block[1])
    bits = int.from_bytes(block[2:8], "little")
    return [pal[(bits >> (3*i)) & 7] for i in range(16)]


def encode_block(values: list[int], old: bytes) -> bytes:
    a0, a1 = max(values), min(values)
    if a0 == a1:
        pal = (a0,) * 8
    else:
        pal = (a0, a1, (6*a0+a1)//7, (5*a0+2*a1)//7,
               (4*a0+3*a1)//7, (3*a0+4*a1)//7,
               (2*a0+5*a1)//7, (a0+6*a1)//7)
    bits = 0
    for i, value in enumerate(values):
        idx = min(range(8), key=lambda j: abs(pal[j] - value))
        bits |= idx << (3*i)
    # Preserve RGB for transparent blocks; Korean glyph blocks need a neutral
    # white color because the shader applies the requested UI text color.
    color = old[8:16] if a0 == 0 else b"\xff\xff\xff\xff\0\0\0\0"
    return bytes((a0, a1)) + bits.to_bytes(6, "little") + color


def descriptor(font: bytes, icon_id: int) -> tuple[int, int, int, int]:
    row = font[DESC + icon_id*18: DESC + (icon_id+1)*18]
    if len(row) != 18 or row[11] != 0xFE:
        raise ValueError(f"invalid icon descriptor {icon_id}")
    return int.from_bytes(row[12:14], "big"), int.from_bytes(row[14:16], "big"), row[1], row[17]


def patch_rect(font: bytearray, x: int, y: int, image: Image.Image) -> None:
    pix = image.convert("L").load(); w, h = image.size
    for by in range(y//4, (y+h+3)//4):
        for bx in range(x//4, (x+w+3)//4):
            off = TEX + (by*BLOCKS_X + bx)*16
            old = bytes(font[off:off+16]); vals = decode_block(old)
            for py in range(4):
                for px in range(4):
                    gx, gy = bx*4+px, by*4+py
                    if x <= gx < x+w and y <= gy < y+h:
                        vals[py*4+px] = pix[gx-x, gy-y]
            font[off:off+16] = encode_block(vals, old)


def render_label(ch: str, w: int, h: int, face: ImageFont.FreeTypeFont) -> Image.Image:
    im = Image.new("L", (w, h), 0); d = ImageDraw.Draw(im)
    box = d.textbbox((0, 0), ch, font=face, stroke_width=0)
    x = (w-(box[2]-box[0]))//2-box[0]
    y = (h-(box[3]-box[1]))//2-box[1]
    d.text((x, y), ch, font=face, fill=255)
    return im


def pad(path: Path, size: int):
    if path.stat().st_size > size: raise ValueError("rebuilt file grew")
    if path.stat().st_size < size:
        with path.open("ab") as f: f.write(b"\0"*(size-path.stat().st_size))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source-sdat",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,default=Path("korean_build_v3")); ap.add_argument("--tag",default="iconfont_ui6_20260808")
    ap.add_argument("--blank-options-only", action="store_true")
    ap.add_argument("--rebuild-mode", choices=("standard", "fixed"), default="standard")
    a=ap.parse_args(); root=Path(__file__).resolve().parent; out=a.output_dir if a.output_dir.is_absolute() else root/a.output_dir; out.mkdir(exist_ok=True)
    source_plain=out/f"COMMON_{a.tag}_source.psarc"; output_plain=out/f"COMMON_{a.tag}.psarc"; output_sdat=out/f"Common_{a.tag}.psarc.sdat"
    header=a.source_sdat.read_bytes()[:0x100]
    with a.source_sdat.open("rb") as s, source_plain.open("wb") as t: logical,_=decrypt_stream(s,0,t)
    arc=PSARC(str(source_plain)); manifest=arc.manifest(); font=bytearray(arc.read_entry(ENTRY))
    if manifest[ENTRY-1] != "/Dat/Font/exFont01.bin": raise AssertionError(manifest[ENTRY-1])
    changes=[]
    # Remove the two option-value boundary glyphs at their true atlas rectangles.
    for icon_id in (117,118):
        x,y,w,h=descriptor(font,icon_id); patch_rect(font,x,y,Image.new("L",(w,h),0)); changes.append({"id":icon_id,"action":"blank","rect":[x,y,w,h]})
    if not a.blank_options_only:
        face=ImageFont.truetype(config.KOREAN_FONT_BOLD,20)
        for icon_id,ch in zip((223,224,225,226),("공","지","해","우")):
            x,y,w,h=descriptor(font,icon_id); patch_rect(font,x,y,render_label(ch,w,h,face)); changes.append({"id":icon_id,"action":ch,"rect":[x,y,w,h]})
    if a.rebuild_mode == "fixed":
        rebuild_report = rebuild_fixed_blocks(source_plain, {ENTRY: bytes(font)}, output_plain)
    else:
        rebuild(str(source_plain),{ENTRY:bytes(font)},str(output_plain)); pad(output_plain,logical)
        rebuild_report = {"rebuild_mode": "standard"}
    arc.f.close(); source_plain.unlink(); encode(str(output_plain),header,str(output_sdat)); pad(output_sdat,a.source_sdat.stat().st_size); output_plain.unlink()
    with output_sdat.open("rb") as s:
        chk=PSARC(SDATReader(s,0)); assert chk.manifest()==manifest and chk.read_entry(ENTRY)==bytes(font)
    report={"source":str(a.source_sdat),"source_sha256":hashlib.sha256(a.source_sdat.read_bytes()).hexdigest(),"output_sha256":hashlib.sha256(output_sdat.read_bytes()).hexdigest(),"size":output_sdat.stat().st_size,"changes":changes,**rebuild_report}
    (out/f"common_{a.tag}_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
