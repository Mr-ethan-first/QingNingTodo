"""UI 构造期回归测试（无需 MySQL / 显示环境）。

验证 flet 0.86 下各页面在 __init__（控件尚未加入 page）期间
不会调用 Control.update()，避免运行时抛出
"Control must be added to the page first"。初始数据加载交由
did_mount()（控件挂载后由框架调用一次）完成。
"""
import flet as ft

from src.config import AppConfig
from src.theme import DEFAULT_THEME
from src.ui_flet.state import AppState
from src.ui_flet.pages.todo_page import TodoPage
from src.ui_flet.pages.plan_page import PlanPage
from src.ui_flet.pages.stats_page import StatsPage
from src.ui_flet.pages.settings_page import SettingsPage
from src.ui_flet.pages.focus_page import FocusPage


class FakeDB:
    """鸭子类型的内存数据库替身，仅满足 DAO 的查询/写入调用。"""

    def query_all(self, sql, params=None):
        return []

    def query_one(self, sql, params=None):
        return None

    def execute(self, sql, params=None):
        return 0

    def execute_many(self, sql, seq_params):
        return 0

    def close(self):
        pass


def _make_state():
    return AppState(FakeDB(), AppConfig(), DEFAULT_THEME)


def test_pages_build_without_update(monkeypatch):
    """构造期不得触发 update（修复 'must be added to the page first'）。"""
    calls = []
    monkeypatch.setattr(ft.Control, "update", lambda self: calls.append(1))

    state = _make_state()
    pages = [
        TodoPage(state),
        PlanPage(state),
        StatsPage(state),
        SettingsPage(state),
        FocusPage(state),
    ]
    # 构造期间不应有任何 update 调用
    assert calls == [], f"构造期不应调用 update，实际调用 {len(calls)} 次"
    # 确保对象确实被创建
    assert len(pages) == 5


def test_pages_load_on_did_mount(monkeypatch):
    """挂载后 did_mount 应触发数据加载（调用 update）。"""
    calls = []
    monkeypatch.setattr(ft.Control, "update", lambda self: calls.append(1))

    state = _make_state()
    page = TodoPage(state)
    # 模拟框架在控件加入 page 后调用 did_mount
    page.did_mount()

    assert calls, "did_mount 后应执行一次刷新（update）"
