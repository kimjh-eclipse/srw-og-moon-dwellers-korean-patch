from pathlib import Path
from PIL import Image, ImageDraw

src = Image.open(Path(__file__).with_name("exfont01_preview.png")).convert("RGBA")
# The decoded texture repeats its logical 512 px-wide icon atlas twice.
src = src.crop((0, 0, 512, src.height))
scale = 2
dst = src.resize((src.width * scale, src.height * scale), Image.Resampling.NEAREST)
d = ImageDraw.Draw(dst)
cols = src.width // 32
rows = src.height // 32
for row in range(rows):
    for col in range(cols):
        idx = row * cols + col
        x, y = col * 32 * scale, row * 32 * scale
        d.rectangle((x, y, x + 63, y + 63), outline=(255, 0, 0, 180), width=1)
        d.rectangle((x, y, x + 34, y + 12), fill=(0, 0, 0, 220))
        d.text((x + 1, y), str(idx), fill=(255, 255, 0, 255))
dst.save(Path(__file__).with_name("exfont01_cells_labeled.png"))
dst.crop((0, 26 * 64, 1024, 32 * 64)).save(Path(__file__).with_name("exfont01_cells_416_511.png"))
src_full = Image.open(Path(__file__).with_name("exfont01_preview.png")).convert("RGBA")
src_full.crop((0, 970, 256, 1040)).resize((1024, 280), Image.Resampling.NEAREST).save(Path(__file__).with_name("exfont01_terrain_crop.png"))
