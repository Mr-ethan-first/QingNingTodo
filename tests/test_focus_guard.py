"""学霸模式守门员（FocusGuard）轮询与回归信号测试。"""
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from src.ui_qt.focus_guard import FocusGuard

# 进程级唯一的 QApplication（offscreen），测试期间持续保活
_APP = QApplication.instance() or QApplication([])


def _patch_process(monkeypatch, fg_provider):
    """替换前台进程相关函数，由 fg_provider 决定当前前台进程名。

    保留真实的 is_allowed / normalize，确保归一化后的比对逻辑与生产一致。
    """
    monkeypatch.setattr(
        "src.ui_qt.focus_guard.get_foreground_process_name",
        lambda: fg_provider())
    monkeypatch.setattr(
        "src.ui_qt.focus_guard.get_current_process_name",
        lambda: "qingning.exe")


def _make_guard(allowed_processes, strict="false"):
    wl = MagicMock()
    wl.list.return_value = [
        {"process_name": p, "app_name": p} for p in allowed_processes]
    sd = MagicMock()
    sd.get = lambda k, d="false": strict if k == "strict_mode" else d
    return FocusGuard(wl, sd)


def test_restored_emitted_once_on_return(monkeypatch):
    """从非白名单回到白名单时，restored 仅触发一次（用于重置提醒标记）。"""
    state = {"fg": "game.exe"}

    def fg():
        return state["fg"]

    _patch_process(monkeypatch, fg)
    g = _make_guard(["editor.exe"])
    viol, rest = [], []
    g.violation.connect(lambda p, s: viol.append((p, s)))
    g.restored.connect(lambda: rest.append(True))
    g.start()

    # 离开到非白名单：发出 violation
    state["fg"] = "game.exe"
    g._poll()
    assert len(viol) == 1 and len(rest) == 0

    # 持续停留非白名单：仍持续上报 violation（去重在专注页层）
    g._poll()
    assert len(viol) == 2

    # 回到白名单：restored 触发一次
    state["fg"] = "editor.exe"
    g._poll()
    assert len(rest) == 1

    # 仍在白名单：restored 不再触发
    g._poll()
    assert len(rest) == 1
    g.stop()
