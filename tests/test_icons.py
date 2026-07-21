"""图标工厂回归测试（快速验证，不遍历全部 20 个图标）。"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication([])

from src.theme import set_current_theme, LIGHT
set_current_theme(LIGHT)
from src.ui_qt.icons import icon, app_icon, tinted, SVGS


def test_svgs_dict_has_all_keys():
    expected = {"leaf", "checklist", "timer", "chart", "map", "settings",
                "plus", "play", "pause", "stop", "check", "edit", "trash",
                "more", "close", "calendar", "user", "target", "shield",
                "database", "chevron", "refresh"}
    for key in expected:
        assert key in SVGS, f"SVGS 缺少 {key}"


def test_icon_produces_non_null():
    """对线性图标抽样验证渲染不空。"""
    for name in ["checklist", "leaf", "timer", "plus"]:
        ico = icon(name)
        assert ico is not None
        pix = ico.pixmap(24, 24)
        assert not pix.isNull(), f"{name} 图标生成为空"


def test_app_icon():
    ico = app_icon()
    pix = ico.pixmap(64, 64)
    assert not pix.isNull()


def test_tinted_closedover():
    maker = tinted("#FF0000")
    ico = maker("leaf")
    assert ico is not None
    assert not ico.pixmap(20, 20).isNull()


def test_colored_icon_specific():
    ico = icon("checklist", "#7DB33F", 24)
    assert not ico.pixmap(24, 24).isNull()
