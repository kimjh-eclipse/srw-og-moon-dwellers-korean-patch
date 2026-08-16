from pathlib import Path

import colorsys
import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "image_localization" / "title720_source.png"
GPT = Path(r"C:\Users\OXP2\.codex\generated_images\01a00505-e0aa-7682-bd04-b3a73b44cc8f\exec-4e008573-57cd-47c6-aa51-6f6a1e30a48e.png")
OUT = ROOT / "image_localization" / "title720_gpt_aligned.png"
PREVIEW = ROOT / "image_localization" / "title720_gpt_aligned_preview.png"


def chroma_alpha(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.float32) / 255.0
    mx = f.max(axis=2)
    mn = f.min(axis=2)
    delta = mx - mn
    hue = np.zeros_like(mx)
    nz = delta > 1e-6
    r, g, b = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    sel = nz & (mx == r)
    hue[sel] = ((g[sel] - b[sel]) / delta[sel]) % 6
    sel = nz & (mx == g)
    hue[sel] = (b[sel] - r[sel]) / delta[sel] + 2
    sel = nz & (mx == b)
    hue[sel] = (r[sel] - g[sel]) / delta[sel] + 4
    hue *= 60.0
    sat = np.where(mx > 0, delta / np.maximum(mx, 1e-6), 0)

    # GPT produced a slightly graded magenta canvas. Its hue stays tightly near
    # 300 degrees even though its brightness varies.
    hue_dist = np.abs(((hue - 300.0 + 180.0) % 360.0) - 180.0)
    key_strength = np.clip((34.0 - hue_dist) / 14.0, 0.0, 1.0)
    key_strength *= np.clip((sat - 0.48) / 0.25, 0.0, 1.0)
    key_strength *= np.clip((mx - 0.45) / 0.25, 0.0, 1.0)
    alpha = (1.0 - key_strength) * 255.0
    return alpha.astype(np.uint8)


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    target_bbox = source.getchannel("A").getbbox()
    if target_bbox is None:
        raise RuntimeError("Source title has no visible alpha bounds")

    generated = Image.open(GPT).convert("RGB")
    rgb = np.asarray(generated)
    alpha = chroma_alpha(rgb)
    alpha_image = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(0.45))
    rgba = generated.convert("RGBA")
    rgba.putalpha(alpha_image)

    # Crop to the real generated subject, excluding residual low-alpha canvas.
    strong_bbox = alpha_image.point(lambda v: 255 if v >= 96 else 0).getbbox()
    if strong_bbox is None:
        raise RuntimeError("Could not isolate GPT title from chroma canvas")
    subject = rgba.crop(strong_bbox)

    left, top, right, bottom = target_bbox
    subject = subject.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    canvas.alpha_composite(subject, (left, top))
    canvas.save(OUT)

    checker = Image.new("RGBA", source.size, (225, 225, 225, 255))
    tile = 24
    draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(checker)
    for y in range(0, source.height, tile):
        for x in range(0, source.width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(180, 180, 180, 255))
    checker.alpha_composite(canvas)
    checker.convert("RGB").save(PREVIEW)

    print(f"source_size={source.size} target_bbox={target_bbox}")
    print(f"gpt_size={generated.size} detected_bbox={strong_bbox}")
    print(f"output={OUT} output_alpha_bbox={canvas.getchannel('A').getbbox()}")


if __name__ == "__main__":
    main()
