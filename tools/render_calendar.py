"""渲染一个带日历控件的对话框截图, 验证可爱日历图标效果."""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.theme import LIGHT, DARK, apply_theme
from src.ui_qt.widgets import CalendarDateEdit


def render_calendar_widget(theme, name):
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app, theme)

    container = QWidget()
    container.resize(400, 200)
    lay = QVBoxLayout(container)
    lay.setContentsMargins(20, 20, 20, 20)

    # 浅色/深色各一个日历控件
    cal = CalendarDateEdit()
    cal.setDate(QDate(2026, 7, 21))
    cal.setDisplayFormat("yyyy-MM-dd")
    cal.setMinimumWidth(160)
    lay.addWidget(cal)

    # 再加一个日历控件展示不同日期
    cal2 = CalendarDateEdit()
    cal2.setDate(QDate(2026, 12, 25))
    cal2.setDisplayFormat("yyyy-MM-dd")
    cal2.setMinimumWidth(160)
    lay.addWidget(cal2)

    container.show()
    for _ in range(5):
        app.processEvents()

    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"calendar_{name}.png")
    pix = container.grab()
    pix.save(out_path, "PNG")
    print(f"  ✓ [{name}] 截图保存: {out_path}")
    container.close()
    container.deleteLater()
    return out_path


def main():
    print("=" * 60)
    print("日历控件渲染验证")
    print("=" * 60)
    render_calendar_widget(LIGHT, "light")
    render_calendar_widget(DARK, "dark")


if __name__ == "__main__":
    main()
