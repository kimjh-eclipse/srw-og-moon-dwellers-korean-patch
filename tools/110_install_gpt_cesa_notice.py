from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
GPT_SOURCE = Path(r"C:\Users\OXP2\.codex\generated_images\01a00505-e0aa-7682-bd04-b3a73b44cc8f\exec-add0e4a6-826b-4684-ab9b-a81cf3ca8db6.png")
ORIGINAL_DDS = ROOT / "image_localization" / "audit_remaining" / "Common" / "Dat" / "Logo" / "@Ja" / "@ps3" / "CESA_720.dds"
WORKSPACE_PNG = ROOT / "image_localization" / "CESA_720_gpt_ko.png"
TARGET_DDS = ROOT / "image_localization" / "localized" / "Common" / "Dat" / "Logo" / "@Ja" / "@ps3" / "CESA_720.dds"


def main() -> None:
    original = Image.open(ORIGINAL_DDS).convert("RGBA")
    generated = Image.open(GPT_SOURCE).convert("RGBA")
    resized = generated.resize(original.size, Image.Resampling.LANCZOS).convert("RGB")

    # Keep the GPT-generated Hangul glyph shapes, but remove the model's subtle
    # photographic background noise. The retail texture uses a flat RGB 239
    # field; restoring it is required for the fixed PSARC compression span.
    pixels = np.asarray(resized).astype(np.float32)
    luminance = pixels.mean(axis=2)
    yy, xx = np.indices(luminance.shape)
    localized_rgb = np.full((original.height, original.width, 3), 239, dtype=np.float32)

    body_zone = (xx >= 320) & (xx <= 970) & (yy >= 205) & (yy <= 575)
    body_alpha = np.clip((232.0 - luminance) / 137.0, 0.0, 1.0) * body_zone
    body_color = np.array([91.0, 91.0, 91.0], dtype=np.float32)
    localized_rgb = localized_rgb * (1.0 - body_alpha[:, :, None]) + body_color * body_alpha[:, :, None]

    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    header_zone = (xx >= 540) & (xx <= 740) & (yy >= 90) & (yy <= 190)
    header_signal = np.maximum(red - green, red - blue)
    header_alpha = np.clip((header_signal - 2.0) / 90.0, 0.0, 1.0) * header_zone
    header_color = np.array([207.0, 62.0, 28.0], dtype=np.float32)
    localized_rgb = localized_rgb * (1.0 - header_alpha[:, :, None]) + header_color * header_alpha[:, :, None]

    localized = Image.fromarray(np.clip(localized_rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # Preserve the retail one-pixel frame exactly.
    retail = np.asarray(original)
    clean = np.asarray(localized).copy()
    clean[0, :, :] = retail[0, :, :]
    clean[-1, :, :] = retail[-1, :, :]
    clean[:, 0, :] = retail[:, 0, :]
    clean[:, -1, :] = retail[:, -1, :]
    localized = Image.fromarray(clean, "RGBA")
    localized.save(WORKSPACE_PNG)

    source_bytes = ORIGINAL_DDS.read_bytes()
    encoded = BytesIO()
    localized.save(encoded, format="DDS")
    payload = encoded.getvalue()
    if len(payload) != len(source_bytes):
        raise ValueError(f"DDS size changed: {len(source_bytes)} -> {len(payload)}")

    TARGET_DDS.parent.mkdir(parents=True, exist_ok=True)
    TARGET_DDS.write_bytes(source_bytes[:128] + payload[128:])
    check = Image.open(TARGET_DDS).convert("RGBA")
    if check.size != original.size:
        raise ValueError(f"DDS verification size mismatch: {check.size}")

    print(f"gpt_source_size={generated.size}")
    print(f"output_png={WORKSPACE_PNG} size={localized.size}")
    print(f"output_dds={TARGET_DDS} size={check.size} bytes={TARGET_DDS.stat().st_size}")


if __name__ == "__main__":
    main()
