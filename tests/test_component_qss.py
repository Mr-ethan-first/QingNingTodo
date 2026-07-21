"""组件库 1:1 还原回归测试.

确保 53 个关键组件 selector 都已注入 QSS, 防止后续修改回退.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.theme import get_theme, apply_theme, _build_calendar_qss


# 原型必需组件 selector 清单
COMPONENT_REQUIREMENTS = [
    # 基础
    "QWidget", "QMainWindow", "QStackedWidget",
    "QLabel#titleDisplay", "QLabel#muted",
    # 按钮
    "QPushButton#primary", "QPushButton#ghost", "QPushButton#iconBtn",
    "QPushButton:disabled",
    # 输入
    "QLineEdit", "QLineEdit:focus", "QLineEdit:disabled",
    "QTextEdit", "QSpinBox", "QComboBox", "QComboBox QAbstractItemView",
    "QDateEdit", "QTimeEdit",
    # 控件
    "QCheckBox::indicator", "QCheckBox::indicator:checked",
    "QRadioButton::indicator",
    "QSlider::handle", "QSlider::sub-page",
    "QProgressBar",
    # 容器
    "QFrame#card", "QFrame#panel", "QFrame#glassCard",
    "QFrame#heroBanner", "QFrame#sidebarItem",
    # 日历 (QTableView 在 _build_calendar_qss 中单独注入)
    "QCalendarWidget", "QCalendarWidget QToolButton",
    # 菜单
    "QMenu", "QMenu::item", "QMenu::separator",
    # 列表/表格
    "QListWidget::item", "QListView::item", "QTreeView::item",
    "QTableWidget", "QHeaderView::section",
    # 标签
    "QLabel#chip", "QLabel#chipSuccess", "QLabel#chipDanger",
    "QLabel#chipSolid", "QLabel#statusPill", "QLabel#pillOn",
    # 工具
    "QToolTip", "QStatusBar", "QToolBar", "QMessageBox",
    # 滚动
    "QScrollBar::handle",
    # 特殊
    "QGroupBox", "QTabBar::tab",
]


def test_all_53_components_qss_light():
    """亮色主题: 53 个组件 QSS 全部就位."""
    app = QApplication.instance() or QApplication([])
    theme = get_theme("light")
    apply_theme(app, theme)
    qss = app.styleSheet()
    cal_qss = _build_calendar_qss()
    # 日历 widget 单独注入, 检查 _build_calendar_qss
    cal_requirements = ["QCalendarWidget", "QToolButton", "QTableView", "QHeaderView::section"]
    for sel in cal_requirements:
        assert sel in cal_qss, f"日历 QSS 缺失: {sel}"
    # 全局检查
    for sel in COMPONENT_REQUIREMENTS:
        assert sel in qss, f"全局 QSS 缺失: {sel}"


def test_all_53_components_qss_dark():
    """暗色主题: 53 个组件 QSS 全部就位."""
    app = QApplication.instance() or QApplication([])
    theme = get_theme("dark")
    apply_theme(app, theme)
    qss = app.styleSheet()
    cal_qss = _build_calendar_qss()
    cal_requirements = ["QCalendarWidget", "QToolButton", "QTableView", "QHeaderView::section"]
    for sel in cal_requirements:
        assert sel in cal_qss, f"日历 QSS 缺失: {sel}"
    for sel in COMPONENT_REQUIREMENTS:
        assert sel in qss, f"全局 QSS 缺失: {sel}"


def test_organic_biophilic_light_colors():
    """亮色 1:1 还原 Organic Biophilic 色板."""
    theme = get_theme("light")
    assert theme.bg == "#F2F5EE", f"bg 应为 #F2F5EE, 实际 {theme.bg}"
    assert theme.surface == "#FFFFFF", f"surface 应为 #FFFFFF, 实际 {theme.surface}"
    assert theme.primary == "#5B8A3A", f"primary 应为 #5B8A3A, 实际 {theme.primary}"
    assert theme.text == "#2A3A1F", f"text 应为 #2A3A1F, 实际 {theme.text}"


def test_aurora_ui_dark_colors():
    """暗色 1:1 还原 Aurora UI 色板."""
    theme = get_theme("dark")
    assert theme.bg == "#0B1026", f"bg 应为 #0B1026, 实际 {theme.bg}"
    assert theme.surface == "#161E40", f"surface 应为 #161E40, 实际 {theme.surface}"
    assert theme.primary == "#818CF8", f"primary 应为 #818CF8, 实际 {theme.primary}"
    assert theme.text == "#E0E7FF", f"text 应为 #E0E7FF, 实际 {theme.text}"


def test_light_background_gradient():
    """亮色背景: 右上角 qradialgradient 自然光晕 (Organic Biophilic)."""
    app = QApplication.instance() or QApplication([])
    theme = get_theme("light")
    apply_theme(app, theme)
    qss = app.styleSheet()
    assert "qradialgradient" in qss, "亮色主题应有 qradialgradient 右上角光晕"


def test_dark_background_conical():
    """暗色背景: qconicalgradient 极光 (Aurora UI)."""
    app = QApplication.instance() or QApplication([])
    theme = get_theme("dark")
    apply_theme(app, theme)
    qss = app.styleSheet()
    assert "qconicalgradient" in qss, "暗色主题应有 qconicalgradient 极光"


def test_calendar_widget_standalone_qss():
    """calendarWidget 独立 QSS 注入 (修复 lazy 创建场景)."""
    app = QApplication.instance() or QApplication([])
    get_theme("light")
    cal_qss = _build_calendar_qss()
    # 关键字段
    assert "QCalendarWidget" in cal_qss
    assert "qt_calendar_navigationbar" in cal_qss
    assert "qt_calendar_prevmonth" in cal_qss
    assert "QTableView" in cal_qss
    assert "selected" in cal_qss
    assert len(cal_qss) > 1500, f"日历 QSS 太短: {len(cal_qss)}"


def test_calendar_popup_filter_lazy_inject():
    """calendarPopup 懒加载事件过滤器 (验证 setup_calendar_popup 注册 filter)."""
    from PyQt6.QtWidgets import QDateEdit
    from src.theme import setup_calendar_popup, _CalendarPopupFilter
    app = QApplication.instance() or QApplication([])
    de = QDateEdit()
    de.setCalendarPopup(True)
    setup_calendar_popup(de)
    # 关键: _cal_popup_filter 已挂载到 date_edit
    assert hasattr(de, "_cal_popup_filter")
    assert isinstance(de._cal_popup_filter, _CalendarPopupFilter)
