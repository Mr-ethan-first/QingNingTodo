"""Render the app's taskbar 'leaf' icon into a multi-size .ico.

Mirrors src/ui_qt/icons.py:app_icon() exactly (same SVG, same theme-primary color)
so the EXE file icon matches the running app's taskbar/window icon.
"""
import sys

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

# 与 src/ui_qt/theme.py 默认主题 primary 一致
PRIMARY = "#5B8A3A"

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'width="24" height="24">'
    '<g fill="{c}" stroke="none">'
    '<path d="M5 19 C5 10 12 4 20 5 C20 13 14 20 5 19 Z"/></g>'
    '<g fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" opacity="0.55">'
    '<path d="M9 16 C12 13 15 10 17 7"/></g>'
    "</svg>"
).format(c=PRIMARY)


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_RGBA8888)
    img.fill(QColor(0, 0, 0, 0))  # transparent
    renderer = QSvgRenderer(QByteArray(SVG.encode("utf-8")))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/icons/qingning.ico"
    tmpdir = sys.argv[2] if len(sys.argv) > 2 else "tools/_icon_png"
    os.makedirs(tmpdir, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48),
             (64, 64), (128, 128), (256, 256)]
    paths = []
    for (w, h) in sizes:
        img = render(w)
        p = os.path.join(tmpdir, f"leaf_{w}.png")
        img.save(p, "PNG")
        paths.append((p, (w, h)))
    # emit the target ico path and the png list so the PIL step can build it
    print("PNGS " + out + " " + " ".join(f"{p},{w}x{h}" for p, (w, h) in paths))


if __name__ == "__main__":
    import os
    app = QApplication(sys.argv)
    main()
