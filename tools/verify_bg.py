"""验证主题背景: light + dark 都应该叠加极光/光晕 gradient."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.theme import get_theme, apply_theme


def main():
    app = QApplication(sys.argv)
    for name in ("light", "dark"):
        theme = get_theme(name)
        apply_theme(app, theme)
        qss = app.styleSheet()
        print(f"\n=== {name} 主题背景 QSS 验证 ===")
        # 验证 1: QWidget 默认背景含 gradient
        import re
        m = re.search(r'QWidget\s*\{[^}]+\}', qss)
        if m:
            block = m.group()
            print(f"  QWidget 块: {len(block)} 字符")
            checks = [
                ("background-color 存在", "background-color" in block),
                ("background-image 存在 (gradient/光晕)", "background-image" in block),
                ("background-repeat 存在", "background-repeat" in block),
            ]
            for label, ok in checks:
                print(f"  [{'✓' if ok else '✗'}] {label}")
            if name == "light":
                # 亮色应该有 radial-gradient (右上角自然光晕)
                print(f"  [{'✓' if 'qradialgradient' in block else '✗'}] qradialgradient (Organic Biophilic 光晕)")
            else:
                # 暗色应该有 qconicalgradient (极光旋转)
                print(f"  [{'✓' if 'qconicalgradient' in block else '✗'}] qconicalgradient (Aurora UI 极光)")
        else:
            print("  ✗ 未找到 QWidget 块")
        # 主题背景色验证
        print(f"  bg color: {theme.bg}")
        print(f"  surface: {theme.surface}")
        print(f"  text:    {theme.text}")
    app.quit()
    print("\n=== 背景验证完成 ===")


if __name__ == "__main__":
    main()
