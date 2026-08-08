from pathlib import Path
import importlib.util
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dxt", root / "15_font_dxt5.py")
dxt = importlib.util.module_from_spec(spec); spec.loader.exec_module(dxt)
dxt.WIDTH = 512; dxt.HEIGHT = 512
raw = Path(__file__).with_name("exfont_4.bin").read_bytes()[0x1e80:]
page_bytes = 512 * 512
for mode in ("linear", "morton_xy", "morton_yx"):
    out = Image.new("L", (512 * 5, 512 * 2))
    for i in range(10):
        chunk = raw[i*page_bytes:(i+1)*page_bytes]
        a = dxt.decode_alpha(chunk, mode)
        im = Image.fromarray(a, "L")
        im.save(Path(__file__).with_name(f"exfont_page{i}_{mode}.png"))
        out.paste(im, ((i % 5)*512, (i//5)*512))
        ImageDraw.Draw(out).text(((i % 5)*512+4, (i//5)*512+4), str(i), fill=128)
    out.save(Path(__file__).with_name(f"exfont_pages_{mode}.png"))
