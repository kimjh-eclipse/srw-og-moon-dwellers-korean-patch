#!/usr/bin/env python3
"""Create Korean replacements for OGMD's remaining text-bearing textures."""

from __future__ import annotations
from tl_data import load_table  # 번역 대역표는 저장소에 포함되지 않는다

import json
import math
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "image_localization"
OUTPUT = WORK / "localized"
FONT = Path("C:/Windows/Fonts/malgun.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/malgunbd.ttf")


SCENE_TITLES = load_table('SCENE_TITLES')


GUIDANCE = load_table('GUIDANCE')


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def save_dds_preserving_header(image: Image.Image, source: Path, destination: Path) -> None:
    source_bytes = source.read_bytes()
    encoded = BytesIO()
    image.convert("RGBA").save(encoded, format="DDS")
    payload = encoded.getvalue()
    if len(payload) != len(source_bytes):
        raise ValueError(f"DDS size changed: {source} {len(source_bytes)} -> {len(payload)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source_bytes[:128] + payload[128:])


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, face, fill, stroke=0, stroke_fill=None):
    box = draw.textbbox((0, 0), text, font=face, stroke_width=stroke)
    x = xy[0] - (box[2] - box[0]) // 2
    y = xy[1] - (box[3] - box[1]) // 2 - box[1]
    draw.text((x, y), text, font=face, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def render_scene_texture(source: Path, text: str, number_asset: bool) -> Image.Image:
    original = Image.open(source).convert("RGBA")
    image = Image.new("RGBA", original.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if number_asset:
        centers = [44, 119, 200, 279, 359, 439]
        sizes = [29, 38, 40, 49, 40, 49]
    else:
        centers = [95, 285, 479, 671, 862, 1055]
        sizes = [38, 46, 48, 58, 48, 58]
    for index, (cy, size) in enumerate(zip(centers, sizes)):
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        # These six rows are animation phases.  Flat alpha levels preserve the
        # fade while remaining compact enough for the original PSARC span.
        alpha = (96, 176, 255, 255, 150, 96)[index]
        shade = 255 if index < 4 else 205
        fill = (shade, shade, shade, alpha)
        centered(layer_draw, (image.width // 2, cy), text, font(FONT_BOLD, size), fill)
        image.alpha_composite(layer)
    return image


def render_scene_assets(manifest: list[dict]) -> None:
    source_root = WORK / "scene_all" / "Dat" / "SceneTitle" / "Dds" / "@Ja"
    target_root = OUTPUT / "Common" / "Dat" / "SceneTitle" / "Dds" / "@Ja"
    for source in sorted(source_root.glob("sn_*.dds")):
        code = int(source.stem.split("_")[1])
        text = load_table("_INLINE")[2] if code in (99, 999) else f"제 {code}화"
        destination = target_root / source.name
        save_dds_preserving_header(render_scene_texture(source, text, True), source, destination)
        manifest.append({"archive": "Common", "path": "/Dat/SceneTitle/Dds/@Ja/" + source.name, "text": text})
    for source in sorted(source_root.glob("st_*.dds")):
        code = int(source.stem.split("_")[1])
        text = SCENE_TITLES[code]
        destination = target_root / source.name
        save_dds_preserving_header(render_scene_texture(source, text, False), source, destination)
        manifest.append({"archive": "Common", "path": "/Dat/SceneTitle/Dds/@Ja/" + source.name, "text": text})


def transparent_text_texture(source: Path, text: str, size: int, color, stroke=0, stroke_fill=None) -> Image.Image:
    image = Image.new("RGBA", Image.open(source).size, (0, 0, 0, 0))
    centered(ImageDraw.Draw(image), (image.width // 2, image.height // 2), text, font(FONT_BOLD, size), color, stroke, stroke_fill)
    return image


def render_lesson_assets(manifest: list[dict]) -> None:
    source_root = WORK / "extracted_common" / "Dat" / "LessonTitle" / "@Ja" / "Dds"
    target_root = OUTPUT / "Common" / "Dat" / "LessonTitle" / "@Ja" / "Dds"
    replacements = load_table('replacements')
    for name, (text, size, color) in replacements.items():
        source = source_root / name
        image = transparent_text_texture(source, text, size, color, 2, (0, 220, 230, 255) if "guidance" in name or "lesson" in name else (130, 20, 15, 255))
        save_dds_preserving_header(image, source, target_root / name)
        manifest.append({"archive": "Common", "path": f"/Dat/LessonTitle/@Ja/Dds/{name}", "text": text})

    source = source_root / "guidance_matome.dds"
    image = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((145, 176, 292, 228), radius=8, fill=(2, 46, 48, 255))
    draw.text((171, 181), load_table("_INLINE")[0], font=font(FONT_BOLD, 30), fill=(255, 255, 255, 255))
    save_dds_preserving_header(image, source, target_root / source.name)
    manifest.append({"archive": "Common", "path": "/Dat/LessonTitle/@Ja/Dds/guidance_matome.dds", "text": load_table("_INLINE")[0]})


def wrap_text(draw: ImageDraw.ImageDraw, text: str, face, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if current and draw.textlength(candidate, font=face) > width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_guidance_assets(manifest: list[dict]) -> None:
    source_root = WORK / "extracted_logic" / "Dat" / "logic" / "Resource" / "summary" / "Img" / "@Ja" / "@ps3"
    target_root = OUTPUT / "Logic" / "Dat" / "logic" / "Resource" / "summary" / "Img" / "@Ja" / "@ps3"
    body_face = font(FONT, 16)
    title_face = font(FONT_BOLD, 20)
    for index in range(1, 16):
        source = source_root / f"guidance_{index:02}.dds"
        image = Image.new("RGBA", Image.open(source).size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        y = 12
        for heading, body in GUIDANCE[index]:
            draw.ellipse((8, y + 5, 18, y + 15), fill=(245, 245, 245, 255))
            draw.text((24, y), heading, font=title_face, fill=(255, 145, 35, 255), stroke_width=1, stroke_fill=(65, 35, 0, 255))
            y += 27
            lines = wrap_text(draw, body, body_face, image.width - 52)
            for line in lines:
                draw.text((31, y), line, font=body_face, fill=(245, 245, 245, 255), stroke_width=1, stroke_fill=(25, 25, 25, 220))
                y += 21
            y += 8
        save_dds_preserving_header(image, source, target_root / source.name)
        manifest.append({"archive": "Logic", "path": f"/Dat/logic/Resource/summary/Img/@Ja/@ps3/{source.name}", "text": [x[0] for x in GUIDANCE[index]]})


def render_battle_console(manifest: list[dict]) -> None:
    source_root = WORK / "extracted_battle" / "Dat" / "Battle" / "Console" / "Dds" / "@Ja"
    target_root = OUTPUT / "Battle" / "Dat" / "Battle" / "Console" / "Dds" / "@Ja"
    source = source_root / "cosl.dds"
    image = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(image)
    # This section of the atlas consists entirely of localized label sprites.
    # Clear it as a group so no Japanese antialiasing survives under the new labels.
    draw.rectangle((0, 96, 1024, 282), fill=(0, 0, 0, 0))
    zones = load_table('zones')
    for (x0, y0, x1, y1), text, size in zones:
        draw.rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 0))
        centered(draw, ((x0 + x1) // 2, (y0 + y1) // 2), text, font(FONT_BOLD, size), (236, 236, 255, 255), 1, (45, 60, 120, 255))
    save_dds_preserving_header(image, source, target_root / source.name)
    manifest.append({"archive": "Battle", "path": "/Dat/Battle/Console/Dds/@Ja/cosl.dds", "text": [z[1] for z in zones]})


def render_option_assets(manifest: list[dict]) -> None:
    source_root = WORK / "option_images" / "Dat" / "Option" / "Img"
    target_root = OUTPUT / "Common" / "Dat" / "Option" / "Img"
    captions = load_table('captions')
    for name, caption in captions.items():
        source = source_root / name
        original = Image.open(source).convert("RGBA")
        # Keep the instructional screenshot and its red focus marks.  A subtle
        # blur/dim treatment makes the baked Japanese non-instructional while
        # the Korean callout remains crisp and readable.
        alpha = original.getchannel("A")
        image = original.filter(ImageFilter.GaussianBlur(1.35))
        image = ImageEnhance.Brightness(image).enhance(0.62)
        image.putalpha(alpha)
        draw = ImageDraw.Draw(image)
        box_height = max(30, min(46, image.height // 5))
        y0 = image.height - box_height - 6
        draw.rounded_rectangle((6, y0, image.width - 6, y0 + box_height), radius=7, fill=(0, 30, 42, 238), outline=(0, 230, 230, 255), width=2)
        size = max(15, min(27, box_height * 3 // 5))
        while size > 14:
            face = font(FONT_BOLD, size)
            bounds = draw.textbbox((0, 0), caption, font=face)
            if bounds[2] - bounds[0] <= image.width - 22:
                break
            size -= 1
        centered(draw, (image.width // 2, y0 + box_height // 2), caption, font(FONT_BOLD, size), (255, 255, 255, 255))
        save_dds_preserving_header(image, source, target_root / name)
        manifest.append({"archive": "Common", "path": f"/Dat/Option/Img/{name}", "text": caption})

    for name in ("04_02ability.dds", "04_03ability.dds"):
        source = source_root / name
        image = transparent_text_texture(source, load_table("_INLINE")[3], 28, (15, 15, 15, 255), 1, (255, 215, 215, 255))
        save_dds_preserving_header(image, source, target_root / name)
        manifest.append({"archive": "Common", "path": f"/Dat/Option/Img/{name}", "text": load_table("_INLINE")[3]})


def render_title_menu_assets(manifest: list[dict]) -> None:
    source_root = WORK / "audit_remaining" / "Common" / "Dat" / "Title" / "Menu" / "Dds"
    target_root = OUTPUT / "Common" / "Dat" / "Title" / "Menu" / "Dds"
    labels = load_table('labels')
    for name, label in labels.items():
        source = source_root / name
        original = Image.open(source).convert("RGBA")
        image = Image.new("RGBA", original.size, (0, 0, 0, 0))
        slot_height = image.height // 5
        size = 25 if image.width <= 184 else 21
        face = font(FONT_BOLD, size)
        for row in range(5):
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            cy = row * slot_height + slot_height // 2
            if row == 0:
                centered(ld, (image.width // 2, cy), label, face, (80, 190, 220, 95), 1, (15, 70, 90, 90))
            elif row == 1:
                centered(ld, (image.width // 2, cy), label, face, (255, 255, 255, 255), 1, (55, 75, 85, 255))
            elif row == 2:
                centered(ld, (image.width // 2, cy), label, face, (255, 255, 255, 55), 1, (240, 250, 255, 190))
            elif row == 3:
                centered(ld, (image.width // 2, cy), label, face, (255, 255, 255, 220), 1, (70, 85, 95, 180))
                layer = layer.filter(ImageFilter.GaussianBlur(2.2))
            else:
                for offset, opacity in ((-12, 35), (-7, 60), (-3, 100), (0, 190)):
                    centered(ld, (image.width // 2 + offset, cy), label, face, (255, 255, 255, opacity))
            image.alpha_composite(layer)
        save_dds_preserving_header(image, source, target_root / name)
        manifest.append({"archive": "Common", "path": f"/Dat/Title/Menu/Dds/{name}", "text": label})


def render_general2d_ui_atlas(manifest: list[dict]) -> None:
    source = WORK / "audit_remaining" / "General2d" / "Dat" / "Window" / "WindowToolData" / "Texture" / "tex_06.dds"
    image = Image.open(source).convert("RGBA")
    pixels = np.array(image)

    def erase_colored(bounds, kind: str) -> None:
        x0, y0, x1, y1 = bounds
        crop = pixels[y0:y1, x0:x1]
        rgb = crop[:, :, :3].astype(np.int16)
        red, green, blue = (rgb[:, :, index] for index in range(3))
        alpha = crop[:, :, 3]
        if kind == "cyan":
            selected = (green > 105) & (blue > 115) & (blue > red + 20) & (alpha > 0)
        elif kind == "warm":
            selected = (red > 145) & (red > green + 30) & (alpha > 0)
        else:
            selected = (red > 115) & (green > 115) & (blue > 115) & (np.maximum.reduce([red, green, blue]) - np.minimum.reduce([red, green, blue]) < 55) & (alpha > 0)
        expanded = Image.fromarray((selected * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(3))
        mask = np.asarray(expanded) > 0
        crop[mask] = 0

    erase_colored((105, 75, 205, 108), "white")
    erase_colored((220, 68, 405, 113), "cyan")
    erase_colored((220, 104, 415, 151), "cyan")
    erase_colored((320, 130, 435, 166), "warm")
    erase_colored((350, 151, 440, 190), "warm")
    erase_colored((130, 270, 465, 340), "white")
    image = Image.fromarray(pixels, "RGBA")
    draw = ImageDraw.Draw(image)
    for bounds in (
        (108, 78, 200, 105),
        (225, 72, 385, 112),
        (225, 107, 390, 145),
        (330, 132, 425, 167),
        (360, 153, 430, 188),
        (140, 278, 460, 335),
    ):
        draw.rectangle(bounds, fill=(0, 0, 0, 0))
    zones = load_table('zones__2')
    for (x0, y0, x1, y1), label, size, color in zones:
        centered(draw, ((x0 + x1) // 2, (y0 + y1) // 2), label, font(FONT_BOLD, size), color, 1, (40, 70, 80, 220))
    target = OUTPUT / "General2d" / "Dat" / "Window" / "WindowToolData" / "Texture" / "tex_06.dds"
    save_dds_preserving_header(image, source, target)
    manifest.append({"archive": "General2d", "path": "/Dat/Window/WindowToolData/Texture/tex_06.dds", "text": [row[1] for row in zones]})


def remove_checker_background(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    spread = rgb.max(axis=2) - rgb.min(axis=2)
    candidate = (spread <= 4) & (rgb.mean(axis=2) >= 238)
    # The generator baked a two-tone checkerboard into every transparent
    # region, including enclosed holes in the OG emblem.  Its pixels are
    # neutral and very bright, so remove all such pixels rather than only
    # the component connected to the outer edge.
    alpha = Image.fromarray(np.where(candidate, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.55))
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def render_title_logo(manifest: list[dict]) -> None:
    source = WORK / "extracted_common" / "Dat" / "Title" / "Logo" / "@Ja" / "@ps3" / "title720.dds"
    localized = Image.open(source).convert("RGBA")
    # Keep the original chrome OG emblem, moon, and English subtitle.  The
    # model-assisted draft established the intended gold/blue treatment, but
    # deterministic rendering avoids its baked checkerboard and preserves the
    # retail texture's exact alpha outside the Japanese title region.
    localized.paste((0, 0, 0, 0), (270, 92, 770, 316))
    title = load_table('title')
    face = font(FONT_BOLD, 70)
    mask = Image.new("L", localized.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    box = mask_draw.textbbox((0, 0), title, font=face, stroke_width=0)
    tx = 295
    ty = 167 - box[1]
    outline = Image.new("RGBA", localized.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    od.text((tx, ty), title, font=face, fill=(245, 177, 35, 255), stroke_width=14, stroke_fill=(0, 115, 230, 255))
    od.text((tx, ty), title, font=face, fill=(245, 177, 35, 255), stroke_width=8, stroke_fill=(25, 18, 12, 255))
    localized.alpha_composite(outline)
    # Warm metallic vertical gradient clipped to the Hangul face.
    mask_draw.text((tx, ty), title, font=face, fill=255)
    gradient = Image.new("RGBA", localized.size, (0, 0, 0, 0))
    gp = gradient.load()
    top = max(0, ty)
    bottom = min(localized.height, ty + 88)
    for y in range(top, bottom):
        t = (y - top) / max(1, bottom - top - 1)
        if t < 0.45:
            u = t / 0.45
            color = tuple(int(a * (1 - u) + b * u) for a, b in zip((255, 245, 180, 255), (255, 159, 10, 255)))
        else:
            u = (t - 0.45) / 0.55
            color = tuple(int(a * (1 - u) + b * u) for a, b in zip((255, 159, 10, 255), (132, 54, 0, 255)))
        for x in range(270, 770):
            gp[x, y] = color
    localized.alpha_composite(Image.composite(gradient, Image.new("RGBA", localized.size), mask))
    # Reconstruct the moon-texture strip behind the Japanese phonetic line,
    # then match its compact black lettering with a fine white keyline.
    subtitle_background = localized.crop((442, 358, 626, 374)).resize(
        (184, 36), Image.Resampling.BICUBIC
    )
    localized.paste(subtitle_background, (442, 374))
    subtitle_draw = ImageDraw.Draw(localized)
    centered(subtitle_draw, (534, 392), load_table("_INLINE")[1], font(FONT_BOLD, 21), (18, 18, 20, 255), 2, (250, 250, 245, 255))
    target = OUTPUT / "Common" / "Dat" / "Title" / "Logo" / "@Ja" / "@ps3" / "title720.dds"
    save_dds_preserving_header(localized, source, target)
    localized.save(WORK / "title720_localized_preview.png")
    manifest.append({"archive": "Common", "path": "/Dat/Title/Logo/@Ja/@ps3/title720.dds", "text": [load_table("_INLINE")[4], load_table("_INLINE")[1]], "method": "imagegen style study + deterministic alpha-safe render"})


def main() -> None:
    manifest: list[dict] = []
    render_scene_assets(manifest)
    render_lesson_assets(manifest)
    render_guidance_assets(manifest)
    render_battle_console(manifest)
    render_option_assets(manifest)
    render_title_menu_assets(manifest)
    render_general2d_ui_atlas(manifest)
    render_title_logo(manifest)
    report = WORK / "localized_manifest.json"
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"localized={len(manifest)} manifest={report}")


if __name__ == "__main__":
    main()
