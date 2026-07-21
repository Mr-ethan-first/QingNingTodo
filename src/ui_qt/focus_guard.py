"""学霸模式监控器。

在专注进行中对前台窗口所属进程进行轮询：若前台进程不在白名单中，
发出 `violation` 信号（携带进程名与是否"严格模式"）。
由专注页决定如何处理（非严格→提醒；严格→直接结束专注）。
"""
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.ui_qt.process_monitor import (
    get_current_process_name,
    get_foreground_process_name,
    is_allowed,
    normalize,
)


class FocusGuard(QObject):
    """前台进程守门员。"""

    # 违规信号：参数分别为（前台进程名, 是否严格模式）
    violation = pyqtSignal(str, bool)
    # 回归信号：前台进程从「非白名单」回到「白名单」后发出（用于重置提醒标记）
    restored = pyqtSignal()

    def __init__(self, whitelist_dao, settings_dao, timer=None, parent=None):
        super().__init__(parent)
        self._whitelist_dao = whitelist_dao
        self._settings_dao = settings_dao
        self._timer = timer
        self._active = False
        self._allowed = set()
        self._violating = False
        self._interval_ms = 2000

    # ---------- 生命周期 ----------
    def start(self):
        """开始监控：构建白名单并启动轮询定时器。"""
        self._build_allowed()
        self._active = True
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._poll)
            self._timer.setInterval(self._interval_ms)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """停止监控。"""
        self._active = False
        if self._timer is not None and self._timer.isActive():
            try:
                self._timer.stop()
            except Exception:
                pass

    def _build_allowed(self):
        """构建被允许的进程名集合（小写、去 .exe）。"""
        allowed = set()
        try:
            for w in self._whitelist_dao.list():
                for key in (w.get("process_name"), w.get("app_name")):
                    if key:
                        allowed.add(normalize(key))
        except Exception:
            pass
        # 本应用进程始终允许（专注窗口本身处于前台时不算违规）
        cur = get_current_process_name()
        if cur:
            allowed.add(normalize(cur))
        self._allowed = allowed

    # ---------- 轮询 ----------
    def _poll(self):
        if not self._active:
            return
        fg = get_foreground_process_name()
        if is_allowed(fg, self._allowed):
            # 已从非白名单应用回到专注窗口，发出回归信号（仅状态切换时）
            if self._violating:
                self._violating = False
                self.restored.emit()
            return
        self._violating = True
        strict = False
        try:
            strict = (self._settings_dao.get("strict_mode", "false") or
                      "false").lower() == "true"
        except Exception:
            strict = False
        self.violation.emit(fg, strict)
