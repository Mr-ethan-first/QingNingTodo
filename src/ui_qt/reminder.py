"""习惯每日打卡提醒服务。

读取 settings 中的 `habit_reminder_time`（HH:MM），每隔 15 秒检查一次当前时间，
当到达设定时刻且当天尚未提醒过时，收集今天尚未打卡的"养习惯"待办（type=1），
通过 `reminder` 信号发出通知（由主窗口转交系统托盘气泡）。

逻辑与 Qt 事件循环解耦：纯方法 `is_due` / `unchecked_habits` 均可独立单元测试。
"""
import datetime
from typing import List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class ReminderService(QObject):
    """每日习惯打卡提醒。"""

    # (标题, 内容)
    reminder = pyqtSignal(str, str)

    def __init__(self, state, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.state = state
        self._last_fired: Optional[str] = None  # "YYYY-MM-DD"
        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self._check)

    # ---------- 控制 ----------
    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # ---------- 纯逻辑（可独立测试） ----------
    def target_time(self) -> (int, int):
        """返回 (时, 分)，解析失败回退 20:00。"""
        raw = "20:00"
        try:
            raw = (self.state.settings_dao.get("habit_reminder_time", "20:00")
                   or "20:00")
        except Exception:
            pass
        try:
            h, m = map(int, raw.strip().split(":"))
            return h, m
        except Exception:
            return 20, 0

    def is_due(self, now: Optional[datetime.datetime] = None) -> bool:
        """当前是否到达提醒时刻且当天尚未提醒过。"""
        now = now or datetime.datetime.now()
        h, m = self.target_time()
        if (now.hour, now.minute) != (h, m):
            return False
        if self._last_fired == str(now.date()):
            return False
        return True

    def unchecked_habits(self, today: Optional[datetime.date] = None) -> List[str]:
        """返回今天尚未打卡的"养习惯"待办标题列表。"""
        today = today or datetime.date.today()
        try:
            todos = self.state.todo_dao.list(status=0)
            habits = [t for t in todos if (t.get("type") or 0) == 1]
        except Exception:
            return []
        unchecked: List[str] = []
        for h in habits:
            try:
                if self.state.habit_checkin_dao.get_today(h["id"], today) is None:
                    unchecked.append(h.get("title", "习惯"))
            except Exception:
                pass
        return unchecked

    # ---------- 驱动 ----------
    def _check(self):
        self._fire_if_due(datetime.datetime.now())

    def _fire_if_due(self, now):
        """在指定时刻评估是否提醒（供 _check 与单元测试复用）。"""
        if not self.is_due(now):
            return
        habits = self.unchecked_habits(now.date())
        # 无论是否有未打卡项，均标记当天已处理，避免重复触发
        self._last_fired = str(now.date())
        if habits:
            title = "青柠待办 · 习惯打卡提醒"
            msg = f"今天还有 {len(habits)} 个习惯未打卡：\n"
            msg += "、".join(habits[:8])
            if len(habits) > 8:
                msg += " 等"
            self.reminder.emit(title, msg)
