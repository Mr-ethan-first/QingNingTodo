"""习惯每日提醒服务（ReminderService）纯逻辑测试。

不依赖 QApplication：使用 __new__ + QObject.__init__ 构造对象，
仅验证 is_due / unchecked_habits / 每日仅触发一次 等核心逻辑。
"""
import datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import QObject

from src.ui_qt.reminder import ReminderService


class _FakeState:
    """最小化的 state 替身，驱动 ReminderService 的纯逻辑。"""

    def __init__(self, settings=None, habits=None, checked=None):
        self._settings = settings or {}
        self._habits = habits or []      # 激活中的待办列表
        self._checked = checked or {}    # todo_id -> 今天是否已打卡
        self.settings_dao = MagicMock()
        self.settings_dao.get = lambda k, d=None: self._settings.get(k, d)
        self.todo_dao = MagicMock()
        self.todo_dao.list = lambda status=None: list(self._habits)
        self.habit_checkin_dao = MagicMock()

        def get_today(tid, today=None):
            return {"id": 1} if self._checked.get(tid) else None

        self.habit_checkin_dao.get_today = get_today


def _make_service(state):
    svc = ReminderService.__new__(ReminderService)
    QObject.__init__(svc)
    svc.state = state
    svc._last_fired = None
    svc._timer = None
    return svc


# ---------------- target_time 解析 ----------------

def test_target_time_default():
    svc = _make_service(_FakeState())
    assert svc.target_time() == (20, 0)


def test_target_time_parsed():
    svc = _make_service(_FakeState(settings={"habit_reminder_time": "07:15"}))
    assert svc.target_time() == (7, 15)


def test_target_time_fallback_on_garbage():
    svc = _make_service(_FakeState(settings={"habit_reminder_time": "garbage"}))
    assert svc.target_time() == (20, 0)


# ---------------- is_due ----------------

def test_is_due_true_at_target_time():
    svc = _make_service(_FakeState(settings={"habit_reminder_time": "20:30"}))
    assert svc.is_due(datetime.datetime(2026, 7, 16, 20, 30, 10)) is True


def test_is_due_false_off_time():
    svc = _make_service(_FakeState(settings={"habit_reminder_time": "20:30"}))
    assert svc.is_due(datetime.datetime(2026, 7, 16, 20, 29)) is False
    assert svc.is_due(datetime.datetime(2026, 7, 16, 8, 0)) is False


def test_is_due_false_already_fired_today():
    svc = _make_service(_FakeState(settings={"habit_reminder_time": "20:30"}))
    now = datetime.datetime(2026, 7, 16, 20, 30)
    svc._last_fired = str(now.date())
    assert svc.is_due(now) is False


# ---------------- unchecked_habits ----------------

def test_unchecked_habits_lists_only_unchecked_habits():
    habits = [
        {"id": 1, "title": "读书", "type": 1},
        {"id": 2, "title": "跑步", "type": 1},
        {"id": 3, "title": "普通待办", "type": 0},  # 非习惯，忽略
    ]
    svc = _make_service(_FakeState(habits=habits, checked={1: True}))
    assert svc.unchecked_habits(datetime.date(2026, 7, 16)) == ["跑步"]


def test_unchecked_habits_empty_when_all_checked():
    habits = [{"id": 1, "title": "读书", "type": 1}]
    svc = _make_service(_FakeState(habits=habits, checked={1: True}))
    assert svc.unchecked_habits(datetime.date(2026, 7, 16)) == []


def test_unchecked_habits_empty_when_no_habits():
    svc = _make_service(_FakeState(habits=[{"id": 1, "title": "x", "type": 0}]))
    assert svc.unchecked_habits(datetime.date(2026, 7, 16)) == []


# ---------------- 触发行为（每日仅一次）----------------

def test_fire_emits_when_due_and_unchecked():
    habits = [{"id": 1, "title": "读书", "type": 1}]
    svc = _make_service(_FakeState(habits=habits, checked={}))
    captured = []
    svc.reminder.connect(lambda t, m: captured.append((t, m)))
    svc._fire_if_due(datetime.datetime(2026, 7, 16, 20, 0))
    assert len(captured) == 1
    assert "读书" in captured[0][1]
    assert svc._last_fired == "2026-07-16"


def test_fire_no_emit_when_all_checked():
    habits = [{"id": 1, "title": "读书", "type": 1}]
    svc = _make_service(_FakeState(habits=habits, checked={1: True}))
    captured = []
    svc.reminder.connect(lambda t, m: captured.append((t, m)))
    svc._fire_if_due(datetime.datetime(2026, 7, 16, 20, 0))
    assert captured == []
    # 即便无未打卡项，仍标记当天已处理，避免反复检查
    assert svc._last_fired == "2026-07-16"


def test_fire_only_once_per_day():
    habits = [{"id": 1, "title": "读书", "type": 1}]
    svc = _make_service(_FakeState(habits=habits, checked={}))
    captured = []
    svc.reminder.connect(lambda t, m: captured.append((t, m)))
    now = datetime.datetime(2026, 7, 16, 20, 0)
    svc._fire_if_due(now)
    svc._fire_if_due(now)  # 同日第二次：应被 is_due 拦截
    assert len(captured) == 1


def test_no_fire_off_target_time():
    habits = [{"id": 1, "title": "读书", "type": 1}]
    svc = _make_service(
        _FakeState(habits=habits, checked={},
                   settings={"habit_reminder_time": "20:00"}))
    captured = []
    svc.reminder.connect(lambda t, m: captured.append((t, m)))
    svc._fire_if_due(datetime.datetime(2026, 7, 16, 9, 0))
    assert captured == []
