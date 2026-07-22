import os
from PIL import Image

sizes = [16, 24, 32, 48, 64, 128, 256]
# 用 256px 原生渲染图作为源，PIL 会按需下采样出各尺寸
src = Image.open("tools/_icon_png/leaf_256.png").convert("RGBA")
out = "assets/icons/qingning.ico"
src.save(out, format="ICO", sizes=[(s, s) for s in sizes])
im = Image.open(out)
print("saved", out, "sizes:", sorted(im.info.get("sizes")))
for s in sizes:
    if os.path.exists(f"tools/_icon_png/leaf_{s}.png"):
        os.remove(f"tools/_icon_png/leaf_{s}.png")
if os.path.isdir("tools/_icon_png"):
    try:
        os.rmdir("tools/_icon_png")
    except OSError:
        pass
print("temp cleaned")
