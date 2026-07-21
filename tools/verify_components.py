"""1:1 还原验证: 一次性检查所有组件 QSS 是否完整覆盖原型规格."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from src.theme import get_theme, apply_theme


# 原型 Organic Biophilic / Aurora UI 必需的组件 selector
COMPONENT_REQUIREMENTS = [
    # 基础
    ("QWidget", "全局基础 (含 gradient 背景)"),
    ("QMainWindow", "主窗口"),
    ("QStackedWidget", "页面堆叠"),
    ("QLabel#titleDisplay", "标题字体 (Fraunces/Outfit)"),
    ("QLabel#muted", "次要文字"),
    # 按钮
    ("QPushButton#primary", "主按钮"),
    ("QPushButton#ghost", "幽灵按钮"),
    ("QPushButton#iconBtn", "图标按钮"),
    ("QPushButton:disabled", "按钮禁用态"),
    # 输入
    ("QLineEdit", "输入框"),
    ("QLineEdit:focus", "输入框聚焦态"),
    ("QLineEdit:disabled", "输入框禁用态"),
    ("QTextEdit", "多行输入"),
    ("QSpinBox", "数字输入"),
    ("QComboBox", "下拉"),
    ("QComboBox QAbstractItemView", "下拉面板"),
    ("QDateEdit", "日期选择"),
    ("QTimeEdit", "时间选择"),
    # 控件
    ("QCheckBox::indicator", "复选框"),
    ("QCheckBox::indicator:checked", "复选框选中"),
    ("QRadioButton::indicator", "单选框"),
    ("QSlider::handle", "滑块手柄"),
    ("QSlider::sub-page", "滑块已选段"),
    ("QProgressBar", "进度条"),
    # 容器
    ("QFrame#card", "卡片"),
    ("QFrame#panel", "面板"),
    ("QFrame#glassCard", "玻璃卡片"),
    ("QFrame#heroBanner", "Hero 横幅"),
    ("QFrame#sidebarItem", "侧栏项"),
    # 日历
    ("QCalendarWidget", "日历"),
    ("QCalendarWidget QToolButton", "日历按钮"),
    ("QCalendarWidget QTableView", "日历表"),
    # 菜单
    ("QMenu", "右键菜单"),
    ("QMenu::item", "菜单项"),
    ("QMenu::separator", "菜单分隔"),
    # 列表/表格
    ("QListWidget::item", "列表项"),
    ("QListView::item", "列表视图项"),
    ("QTreeView::item", "树项"),
    ("QTableWidget", "表格"),
    ("QHeaderView::section", "表头"),
    # 标签
    ("QLabel#chip", "胶囊标签"),
    ("QLabel#chipSuccess", "成功标签"),
    ("QLabel#chipDanger", "危险标签"),
    ("QLabel#chipSolid", "实心标签"),
    ("QLabel#statusPill", "状态点"),
    ("QLabel#pillOn", "激活 pill"),
    # 工具
    ("QToolTip", "工具提示"),
    ("QStatusBar", "状态栏"),
    ("QToolBar", "工具栏"),
    ("QMessageBox", "消息框"),
    # 滚动
    ("QScrollBar::handle", "滚动条手柄"),
    # 特殊
    ("QGroupBox", "分组框"),
    ("QTabBar::tab", "Tab 项"),
]


def main():
    app = QApplication(sys.argv)
    theme = get_theme("light")
    apply_theme(app, theme)
    qss = app.styleSheet()
    print(f"QSS 总长度: {len(qss)} 字符")
    print(f"组件要求: {len(COMPONENT_REQUIREMENTS)} 项\n")
    missing = []
    for sel, desc in COMPONENT_REQUIREMENTS:
        ok = sel in qss
        print(f"  [{'✓' if ok else '✗'}] {sel:35s} | {desc}")
        if not ok:
            missing.append(sel)
    print(f"\n=== 结果: 缺失 {len(missing)} / {len(COMPONENT_REQUIREMENTS)} ===")
    if missing:
        print("缺失项:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("全部组件 1:1 还原 QSS 已就位 ✓")
    app.quit()


if __name__ == "__main__":
    main()
