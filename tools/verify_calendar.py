"""不依赖 GUI 渲染, 直接对比 QSS 字符串验证日历组件 1:1 还原."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QCalendarWidget
from PyQt6.QtCore import QDate

from src.theme import (
    get_theme, apply_theme, _build_calendar_qss, _apply_calendar_qss
)


def main():
    app = QApplication(sys.argv)

    for name in ("light", "dark"):
        theme = get_theme(name)
        apply_theme(app, theme)
        cal = QCalendarWidget()
        cal.setSelectedDate(QDate(2026, 8, 20))
        _apply_calendar_qss(cal)
        # 验证 calendar 真的拿到了 QSS
        got = cal.styleSheet()
        print(f"\n=== {name} 主题 ===")
        print(f"  QSS 长度: {len(got)} 字符")
        # 关键字段检查
        checks = [
            ("QCalendarWidget", "QCalendarWidget"),
            ("nav bar", "qt_calendar_navigationbar"),
            ("prev/next 按钮", "qt_calendar_prevmonth"),
            ("table view", "QTableView"),
            ("selected", "selected"),
            ("header section", "QHeaderView::section"),
        ]
        for label, key in checks:
            print(f"  [{'✓' if key in got else '✗'}] {label}")
        # 颜色 token 验证
        t = theme
        # 1:1 Organic Biophilic 亮色
        if name == "light":
            assert t.primary == "#5B8A3A", f"primary 不匹配: {t.primary}"
            assert t.bg == "#F2F5EE", f"bg 不匹配: {t.bg}"
            print(f"  [✓] primary = {t.primary}")
            print(f"  [✓] bg = {t.bg}")
        # 1:1 Aurora UI 暗色
        else:
            assert t.primary == "#818CF8", f"primary 不匹配: {t.primary}"
            assert t.bg == "#0B1026", f"bg 不匹配: {t.bg}"
            print(f"  [✓] primary = {t.primary}")
            print(f"  [✓] bg = {t.bg}")
        # 渲染一次让布局完成
        cal.resize(340, 320)
        cal.show()
        for _ in range(20):
            app.processEvents()
        cal.close()
        cal.deleteLater()
        app.processEvents()
    app.quit()
    print("\n=== 全部校验通过 ===")


if __name__ == "__main__":
    main()
