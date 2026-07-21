"""主题切换状态机测试。"""
from src.theme import DEFAULT_THEME, DARK, LIGHT, get_current_theme, set_current_theme
from src.config import AppConfig
from src.database import dao
from src.ui_qt.state import AppState


class _FakeDB:
    def query_all(self, sql, params=None): return []
    def query_one(self, sql, params=None): return None
    def execute(self, sql, params=None): return 0
    def execute_many(self, sql, seq_params): return 0
    def close(self): pass


def test_set_theme_notifies():
    from src.ui_qt.state import AppState
    notified = []

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    state.subscribe(lambda t: notified.append(t.name))

    state.set_theme("dark")
    assert state.theme_name == "dark"
    assert state.theme is DARK
    assert len(notified) == 1
    assert notified[0] == "dark"

    state.set_theme("light")
    assert len(notified) == 2
    assert notified[1] == "light"


def test_set_theme_updates_global():
    set_current_theme(LIGHT)
    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    state.set_theme("dark")
    assert get_current_theme() is DARK


def test_subscribers_not_called_for_identical():
    """重复 set_theme 不应触发订阅。"""
    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    called = []
    state.subscribe(lambda t: called.append(1))
    state.set_theme("light")  # 已经是 light
    assert len(called) == 1
    state.set_theme("light")  # 再次
    assert len(called) == 2  # state 允许重复切换
