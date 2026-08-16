from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE_DDS = ROOT / "image_localization" / "extracted_common" / "Dat" / "Title" / "Logo" / "@Ja" / "@ps3" / "title720.dds"
GPT_PNG = ROOT / "image_localization" / "title720_gpt_aligned.png"
GAME_PNG = ROOT / "image_localization" / "title720_gpt_game.png"
TARGET_DDS = ROOT / "image_localization" / "localized" / "Common" / "Dat" / "Title" / "Logo" / "@Ja" / "@ps3" / "title720.dds"


def main() -> None:
    source_bytes = SOURCE_DDS.read_bytes()
    image = Image.open(GPT_PNG).convert("RGBA")
    if image.size != (1280, 720):
        raise ValueError(f"Unexpected GPT title size: {image.size}")

    # PSARC gives this entry only a fixed compressed span. Remove model color
    # noise while keeping the GPT-generated geometry and the exact alpha matte.
    alpha = image.getchannel("A")
    image = image.quantize(
        colors=256,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    ).convert("RGBA")
    image.putalpha(alpha)
    image.save(GAME_PNG)

    encoded = BytesIO()
    image.save(encoded, format="DDS")
    payload = encoded.getvalue()
    if len(payload) != len(source_bytes):
        raise ValueError(f"DDS size changed: {len(source_bytes)} -> {len(payload)}")

    TARGET_DDS.parent.mkdir(parents=True, exist_ok=True)
    TARGET_DDS.write_bytes(source_bytes[:128] + payload[128:])

    check = Image.open(TARGET_DDS).convert("RGBA")
    if check.size != image.size:
        raise ValueError(f"DDS verification size mismatch: {check.size}")
    print(f"wrote={TARGET_DDS}")
    print(f"game_png={GAME_PNG}")
    print(f"size={check.size} alpha_bbox={check.getchannel('A').getbbox()} bytes={TARGET_DDS.stat().st_size}")


if __name__ == "__main__":
    main()
