"""关闭窗口退出确认（提醒窗口）相关测试（PyQt6 offscreen）。

覆盖：
1. CloseConfirmDialog 的默认状态与三种动作（退出/最小化/取消）；
2. 主窗口 closeEvent 在不同 confirm_on_close 配置下的行为：
   - 关闭确认关闭时（"false"）→ 直接退出；
   - 开启时（默认）→ 弹出提醒窗口，按对话框结果决定退出/最小化/取消；
   - 勾选"不再提醒"→ 将 confirm_on_close 持久化为 "false"。
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication

from src.config import AppConfig
from src.theme import DEFAULT_THEME
from src.ui_qt.state import AppState
from src.ui_qt.main_window import MainWindow
from src.ui_qt import dialogs
from src.ui_qt.dialogs import CloseConfirmDialog

# 进程级唯一的 QApplication（offscreen），测试期间持续保活，
# 避免控件/动画被提前销毁导致原生崩溃。
_APP = QApplication.instance() or QApplication([])


class _FakeEvent:
    """模拟 QCloseEvent，记录 accept/ignore 调用。"""
    def __init__(self):
        self.accepted = None

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


class _FakeDialog:
    """替身对话框：exec() 立即返回，携带预置结果。"""
    ACTION_EXIT = CloseConfirmDialog.ACTION_EXIT
    ACTION_TRAY = CloseConfirmDialog.ACTION_TRAY
    ACTION_CANCEL = CloseConfirmDialog.ACTION_CANCEL

    _next_action = CloseConfirmDialog.ACTION_CANCEL
    _next_dont_remind = False

    def __init__(self, parent=None):
        self.action = self._next_action
        self.dont_remind = self._next_dont_remind

    def exec(self):
        return 1


@pytest.fixture
def window(db):
    state = AppState(db, AppConfig(), DEFAULT_THEME)
    win = MainWindow(state)
    # 测试环境下系统托盘可能不可用（offscreen 平台），
    # 但 closeEvent 依赖 _tray_available 决定是否弹出确认对话框，
    # 因此手动标记为可用以正确测试对话框逻辑。
    win._tray_available = True
    yield win


# ---------------- CloseConfirmDialog ----------------

def test_dialog_default_state():
    dlg = CloseConfirmDialog()
    assert dlg.action == CloseConfirmDialog.ACTION_CANCEL
    assert dlg.dont_remind is False


def test_dialog_exit_action():
    dlg = CloseConfirmDialog()
    dlg._on_exit()
    assert dlg.action == CloseConfirmDialog.ACTION_EXIT


def test_dialog_tray_action():
    dlg = CloseConfirmDialog()
    dlg._on_tray()
    assert dlg.action == CloseConfirmDialog.ACTION_TRAY


def test_dialog_dont_remind_checkbox():
    dlg = CloseConfirmDialog()
    dlg.cb_dont_remind.setChecked(True)
    dlg._on_exit()
    assert dlg.dont_remind is True


# ---------------- closeEvent ----------------

def test_close_direct_exit_when_disabled(window, monkeypatch):
    """confirm_on_close=false → 点击叉号直接退出（不弹对话框）。"""
    window.state.settings_dao.set("confirm_on_close", "false")
    quit_called = []
    monkeypatch.setattr(QApplication.instance(), "quit",
                        lambda: quit_called.append(True))
    # 对话框不应被创建；若创建则让测试失败
    monkeypatch.setattr(dialogs, "CloseConfirmDialog",
                        lambda *a, **k: pytest.fail("不应弹出确认对话框"))
    ev = _FakeEvent()
    window.closeEvent(ev)
    assert ev.accepted is True
    assert quit_called == [True]


def test_close_shows_dialog_and_exit(window, monkeypatch):
    """confirm_on_close=true 且选择退出 → 退出程序。"""
    window.state.settings_dao.set("confirm_on_close", "true")
    _FakeDialog._next_action = _FakeDialog.ACTION_EXIT
    _FakeDialog._next_dont_remind = False
    monkeypatch.setattr(dialogs, "CloseConfirmDialog", _FakeDialog)
    quit_called = []
    monkeypatch.setattr(QApplication.instance(), "quit",
                        lambda: quit_called.append(True))
    ev = _FakeEvent()
    window.closeEvent(ev)
    assert ev.accepted is True
    assert quit_called == [True]


def test_close_dialog_dont_remind_persists(window, monkeypatch):
    """勾选不再提醒并退出 → confirm_on_close 落库为 false。"""
    window.state.settings_dao.set("confirm_on_close", "true")
    _FakeDialog._next_action = _FakeDialog.ACTION_EXIT
    _FakeDialog._next_dont_remind = True
    monkeypatch.setattr(dialogs, "CloseConfirmDialog", _FakeDialog)
    monkeypatch.setattr(QApplication.instance(), "quit", lambda: None)
    ev = _FakeEvent()
    window.closeEvent(ev)
    assert window.state.settings_dao.get("confirm_on_close") == "false"


def test_close_dialog_tray(window, monkeypatch):
    """选择最小化到托盘 → 收起窗口、不退出。"""
    window.state.settings_dao.set("confirm_on_close", "true")
    _FakeDialog._next_action = _FakeDialog.ACTION_TRAY
    _FakeDialog._next_dont_remind = False
    monkeypatch.setattr(dialogs, "CloseConfirmDialog", _FakeDialog)
    quit_called = []
    monkeypatch.setattr(QApplication.instance(), "quit",
                        lambda: quit_called.append(True))
    collapse_called = []
    monkeypatch.setattr(window, "collapse_to_taskbar",
                        lambda: collapse_called.append(True))
    ev = _FakeEvent()
    window.closeEvent(ev)
    assert ev.accepted is False  # ignore()
    assert quit_called == []
    assert collapse_called == [True]


def test_close_dialog_cancel(window, monkeypatch):
    """取消（关闭对话框）→ 窗口保持，不退出。"""
    window.state.settings_dao.set("confirm_on_close", "true")
    _FakeDialog._next_action = _FakeDialog.ACTION_CANCEL
    _FakeDialog._next_dont_remind = False
    monkeypatch.setattr(dialogs, "CloseConfirmDialog", _FakeDialog)
    quit_called = []
    monkeypatch.setattr(QApplication.instance(), "quit",
                        lambda: quit_called.append(True))
    ev = _FakeEvent()
    window.closeEvent(ev)
    assert ev.accepted is False
    assert quit_called == []
