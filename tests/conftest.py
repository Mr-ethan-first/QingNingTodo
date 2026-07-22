# -*- coding: utf-8 -*-
"""共享 pytest fixtures — 数据库隔离 + QApplication 管理。

设计要点：
- 每个测试函数获得独立的临时数据库（通过 QINGNING_TODO_HOME 指向临时目录）
- QApplication 全局共享（pytest-qt 不可用时手动管理）
- DAO fixtures 基于独立数据库，测试间互不干扰
"""
import os
import sys
import tempfile
import shutil
import datetime
from pathlib import Path

import pytest

# 确保项目路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# 在导入任何项目模块之前设置环境变量
@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """每个测试自动使用独立的临时目录作为 QINGNING_TODO_HOME。"""
    home = tmp_path / "qingning_home"
    home.mkdir()
    monkeypatch.setenv("QINGNING_TODO_HOME", str(home))
    yield
    # tmp_path 由 pytest 自动清理


# ===================== QApplication 管理 =====================

_qapp = None


@pytest.fixture(scope="session")
def qapp():
    """全局共享的 QApplication 实例。"""
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication
        _qapp = QApplication.instance() or QApplication(sys.argv)
    return _qapp


# ===================== 数据库 Fixtures =====================

@pytest.fixture
def app_config():
    """返回基于临时目录的 AppConfig。"""
    from src.config import AppConfig
    return AppConfig()


@pytest.fixture
def db(app_config):
    """每个测试独立的 SQLiteDatabase 实例（已初始化表结构+种子数据）。"""
    from src.database.sqlite_backend import create_sqlite_database
    database = create_sqlite_database(app_config)
    database.init_database()
    yield database
    try:
        database.close()
    except Exception:
        pass


@pytest.fixture
def db_with_data(db):
    """带基础测试数据的数据库（1个分组 + 3条待办 + 5条专注记录）。"""
    from src.database.dao import TodoGroupDAO, TodoDAO, FocusRecordDAO
    group_dao = TodoGroupDAO(db)
    todo_dao = TodoDAO(db)
    focus_dao = FocusRecordDAO(db)

    gid = group_dao.create("测试组", color="#8CC44A")
    tid1 = todo_dao.create("学习Python", timer_type=0, duration=1500, group_id=gid)
    tid2 = todo_dao.create("写周报", timer_type=1, duration=1800, group_id=gid)
    tid3 = todo_dao.create("跑步锻炼", timer_type=2, duration=600, group_id=gid)

    now = datetime.datetime.now()
    # 5条专注记录：今天3条 + 昨天2条
    focus_data = [
        (0, 9, 0, 1500, 1500, 1, tid1),
        (0, 14, 0, 1800, 1800, 1, tid2),
        (0, 20, 0, 600, 600, 1, tid3),
        (1, 10, 0, 1500, 900, 0, tid1),
        (1, 15, 0, 1800, 1800, 1, tid2),
    ]
    for day_off, h, m, planned, actual, completed, tid in focus_data:
        start = datetime.datetime(now.year, now.month, now.day, h, m) - datetime.timedelta(days=day_off)
        end = start + datetime.timedelta(seconds=actual)
        focus_dao.create(
            todo_id=tid, timer_type=0, planned_duration=planned,
            actual_duration=actual, start_time=start, end_time=end,
            is_completed=completed, record_name=f"测试_{h}点",
        )
    return db


# ===================== DAO Fixtures =====================

@pytest.fixture
def todo_dao(db):
    from src.database.dao import TodoDAO
    return TodoDAO(db)


@pytest.fixture
def group_dao(db):
    from src.database.dao import TodoGroupDAO
    return TodoGroupDAO(db)


@pytest.fixture
def focus_dao(db):
    from src.database.dao import FocusRecordDAO
    return FocusRecordDAO(db)


@pytest.fixture
def stats_dao(db):
    from src.database.dao import StatsDAO
    return StatsDAO(db)


@pytest.fixture
def checkin_dao(db):
    from src.database.dao import CheckinDAO
    return CheckinDAO(db)


@pytest.fixture
def interrupt_dao(db):
    from src.database.dao import InterruptDetailDAO
    return InterruptDetailDAO(db)


@pytest.fixture
def settings_dao(db):
    from src.database.dao import SettingsDAO
    return SettingsDAO(db)


@pytest.fixture
def goal_dao(db):
    from src.database.dao import GoalDAO
    return GoalDAO(db)


@pytest.fixture
def plan_dao(db):
    from src.database.dao import FuturePlanDAO
    return FuturePlanDAO(db)


@pytest.fixture
def achievement_dao(db):
    from src.database.dao import AchievementDAO
    return AchievementDAO(db)


@pytest.fixture
def whitelist_dao(db):
    from src.database.dao import WhitelistDAO
    return WhitelistDAO(db)


@pytest.fixture
def lock_dao(db):
    from src.database.dao import LockScheduleDAO
    return LockScheduleDAO(db)


@pytest.fixture
def noise_dao(db):
    from src.database.dao import WhiteNoiseDAO
    return WhiteNoiseDAO(db)


@pytest.fixture
def user_dao(db):
    from src.database.dao import UserDAO
    return UserDAO(db)


@pytest.fixture
def habit_dao(db):
    from src.database.dao import HabitCheckinDAO
    return HabitCheckinDAO(db)


# ===================== UI Fixtures =====================

@pytest.fixture
def stats_page(qapp, db_with_data):
    """数据统计页面实例（带测试数据）。"""
    from src.config import AppConfig
    from src.database.sqlite_backend import create_sqlite_database
    from src.theme import apply_theme, get_current_theme

    # 需要用带数据的数据库
    app_cfg = AppConfig()
    # 由于 _isolate_home 已经设置了环境变量，AppConfig 会使用临时目录
    # 但 db_with_data 已经初始化了同一个路径的数据库
    # 所以这里直接用 db_with_data
    from src.ui_qt.pages.stats_page import StatsPage
    from src.ui_qt.state import AppState

    state = AppState(db_with_data, app_cfg, "light")
    page = StatsPage(state)
    yield page
    page.deleteLater()


@pytest.fixture
def todo_page(qapp, db_with_data):
    """待办清单页面实例。"""
    from src.config import AppConfig
    from src.ui_qt.pages.todo_page import TodoPage
    from src.ui_qt.state import AppState

    app_cfg = AppConfig()
    state = AppState(db_with_data, app_cfg, "light")
    page = TodoPage(state)
    yield page
    page.deleteLater()


@pytest.fixture
def settings_page(qapp, db_with_data):
    """设置页面实例。"""
    from src.config import AppConfig
    from src.ui_qt.pages.settings_page import SettingsPage
    from src.ui_qt.state import AppState

    app_cfg = AppConfig()
    state = AppState(db_with_data, app_cfg, "light")
    page = SettingsPage(state)
    yield page
    page.deleteLater()
