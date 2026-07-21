"""主窗口实景渲染: 用 QSS 应用主题后, 截屏保存到 tools/screenshots/ 用于视觉验证."""
import os
import sys

# 添加项目根
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from src.theme import LIGHT, DARK, apply_theme
from src.ui_qt.state import AppState
from src.ui_qt.main_window import MainWindow


def render(theme, name):
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app, theme)
    # 准备 AppState (mock db, app_config 避免依赖数据库)
    class _MockDB:
        def list_groups(self):
            return [{"id": 1, "name": "工作", "color": theme.primary},
                    {"id": 2, "name": "学习", "color": theme.secondary},
                    {"id": 3, "name": "生活", "color": theme.accent}]
        def list_todos(self, **kwargs):
            return []
        def list_focus_sessions(self, **kwargs):
            return []
        def list_habits(self, **kwargs):
            return []
        def get(self, key, default=None):
            return default
        def __getattr__(self, name):
            def _missing(*args, **kwargs):
                if name in ("get", "settings_dao"):
                    return _MockDB()
                if "list" in name or "all" in name:
                    return []
                return None
            return _missing
    state = AppState(db=_MockDB(), app_config=_MockDB(), theme_name=theme.name)
    win = MainWindow(state)
    win.resize(1180, 760)
    win.show()
    # 强制布局
    for _ in range(5):
        app.processEvents()
    # 截图
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"main_{name}.png")
    pix = win.grab()
    pix.save(out_path, "PNG")
    print(f"  ✓ [{name}] 截图保存: {out_path} ({pix.width()}x{pix.height()})")
    win.close()
    win.deleteLater()
    return out_path


def main():
    print("=" * 60)
    print("主窗口实景渲染验证")
    print("=" * 60)
    light_path = render(LIGHT, "light")
    print()
    dark_path = render(DARK, "dark")
    print()
    print(f"  light: {light_path}")
    print(f"  dark:  {dark_path}")


if __name__ == "__main__":
    main()
