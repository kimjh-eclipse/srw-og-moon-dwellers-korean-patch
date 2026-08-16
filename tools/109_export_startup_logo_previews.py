from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent / "image_localization" / "audit_remaining" / "Common" / "Dat" / "Logo" / "@Ja" / "@ps3"
OUT = Path(__file__).resolve().parent / "image_localization" / "startup_logo_previews"
OUT.mkdir(parents=True, exist_ok=True)

for source in ROOT.glob("*.dds"):
    image = Image.open(source).convert("RGBA")
    target = OUT / f"{source.stem}.png"
    image.save(target)
    print(source.name, image.size, target)
