"""专注计时引擎逻辑验证测试（不依赖 PyQt6 widget 构建）。

通过 mock _build 方法跳过 UI 创建，只验证计时引擎的纯逻辑。
"""
import datetime

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.config import AppConfig
from src.theme import DEFAULT_THEME
from src.ui_qt.state import AppState
from src.ui_qt.pages.focus_page import (
    FocusPage, IDLE, RUNNING, PAUSED, RESTING, STOPWATCH,
)

# 进程级唯一的 QApplication（offscreen），测试期间持续保活，
# 避免控件/动画在 GC/teardown 阶段被提前销毁导致原生崩溃。
_APP = QApplication.instance() or QApplication([])

# 学霸模式监控器替身（避免在无 QObject 父对象的测试页上构造真实 FocusGuard）
@pytest.fixture(autouse=True)
def _patch_focus_guard(monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)

# 默认待办（单轮）
_TODO_SINGLE = {
    "id": 1, "title": "测试", "duration": 1500,
    "timer_type": 0, "break_duration": 300, "loop_count": 1,
    "custom_break_duration": None,
}

# 多轮待办
_TODO_LOOP = {
    "id": 2, "title": "循环测试", "duration": 1500,
    "timer_type": 0, "break_duration": 300, "loop_count": 3,
    "custom_break_duration": None,
}

# 自定义休息时长
_TODO_CUSTOM_BREAK = {
    "id": 3, "title": "自定义休息", "duration": 1500,
    "timer_type": 0, "break_duration": 300, "loop_count": 1,
    "custom_break_duration": 600,
}


class _FakeDB:
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


class _FakeDBWithSettings(_FakeDB):
    def __init__(self, settings: dict = None):
        self._settings = settings or {}

    def query_one(self, sql, params=None):
        if "settings" in sql and "setting_key" in sql and params:
            key = params[1]
            if key in self._settings:
                return {"setting_value": self._settings[key]}
            return None
        return None


def _make_page(db=None):
    """创建一个不执行 _build 的 FocusPage（仅初始化引擎逻辑）。

    使用 FocusPage.__new__ 跳过 __init__（避免 QFrame 构造），
    手动设置所有属性以验证纯逻辑。
    """
    from unittest.mock import MagicMock
    state = AppState(db or _FakeDB(), AppConfig(), DEFAULT_THEME)
    page = FocusPage.__new__(FocusPage)
    import src.database.dao as _dao_mod
    page.focus_dao = _dao_mod.FocusRecordDAO(state.db)
    page.interrupt_dao = _dao_mod.InterruptDetailDAO(state.db)
    page.ach_dao = _dao_mod.AchievementDAO(state.db)
    page.noise_dao = _dao_mod.WhiteNoiseDAO(state.db)
    page.todo_dao = _dao_mod.TodoDAO(state.db)
    page.settings_dao = _dao_mod.SettingsDAO(state.db)
    page.state = state
    page.fstate = IDLE
    page.current_todo = None
    page.remaining = 0
    page.elapsed = 0
    page.planned = 1500
    page.start_time = None
    page.timer_type = 0
    page.noise_player = __import__('src.audio_player', fromlist=['get_player']).get_player()
    page.current_loop = 1
    page.total_loops = 1
    page._pause_start = None
    page._stopwatch_record_saved = False
    page._t = state.theme
    page._timer = MagicMock()  # mock QTimer，避免实际 Qt 操作
    page._guard = None  # 学霸模式监控器（测试页未走 __init__，显式初始化）
    page._guard_violations = []
    page._guard_notified = False  # 离开提醒去重标记（__init__ 中初始化）
    page._lay = MagicMock()
    page._toast = lambda msg: None  # 避免 self.window() 需要 QFrame __init__
    return page


def _mock_widgets(page):
    """为 page 添加模拟的 widget 属性。"""
    from unittest.mock import MagicMock
    page.lbl_task = MagicMock()
    page.lbl_state = MagicMock()
    page.lbl_timer = MagicMock()
    page.lbl_loop = MagicMock()
    page.lbl_motto = MagicMock()
    page.lbl_stopwatch_hint = MagicMock()
    page.cb_noise = MagicMock()
    page.btn_start = MagicMock()
    page.btn_pause = MagicMock()
    page.btn_finish = MagicMock()
    page.btn_giveup = MagicMock()
    # Mock hero banner for _refresh_hero_subtitle
    page._hero = MagicMock()
    page._hero.findChild.return_value = None  # No subtitle label in tests


# ==================== 专注页背景解析（修复：背景图不生效） ====================

import os
from unittest.mock import MagicMock


def _fake_settings(values):
    """返回可替换 settings_dao.get 的替身。"""
    s = MagicMock()
    s.get = lambda k, d="": values.get(k, d)
    return s


def test_resolve_focus_background_global(tmp_path):
    """无待办时，应解析并使用全局 app_background 配置。"""
    p = _make_page()
    gfp = tmp_path / "global.png"
    gfp.write_bytes(b"x")
    p.settings_dao = _fake_settings({"app_background": str(gfp)})
    p.current_todo = None
    assert p._resolve_focus_background() == str(gfp)


def test_resolve_focus_background_todo_priority(tmp_path):
    """加载待办时，待办级 background_path 优先于全局配置。"""
    p = _make_page()
    gfp = tmp_path / "global.png"; gfp.write_bytes(b"x")
    tfp = tmp_path / "todo.png"; tfp.write_bytes(b"x")
    p.settings_dao = _fake_settings({"app_background": str(gfp)})
    p.current_todo = {"background_path": str(tfp)}
    assert p._resolve_focus_background() == str(tfp)


def test_resolve_focus_background_falls_back(tmp_path):
    """待办背景文件不存在时，回退到全局 app_background。"""
    p = _make_page()
    gfp = tmp_path / "global.png"; gfp.write_bytes(b"x")
    p.settings_dao = _fake_settings({"app_background": str(gfp)})
    p.current_todo = {"background_path": str(tmp_path / "missing.png")}
    assert p._resolve_focus_background() == str(gfp)


# ==================== 原有基础功能 ====================

def test_focus_default_state():
    p = _make_page()
    assert p.fstate == IDLE
    assert p.remaining == 0
    assert p.elapsed == 0
    assert p.current_loop == 1
    assert p.total_loops == 1


def test_load_todo_sets_timer():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    assert p.current_todo is _TODO_SINGLE
    assert p.planned == 1500
    assert p.remaining == 1500


def test_start_changes_state():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._start()
    assert p.fstate == RUNNING
    p._timer = None  # 避免后续操作出错


def test_pause_resume():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._start()
    p._on_pause()
    assert p.fstate == PAUSED
    p._on_pause()
    assert p.fstate == RUNNING


def test_finish_saves_record():
    p = _make_page()
    _mock_widgets(p)
    saved = []
    p._save_record = lambda actual, completed, reason=None: saved.append((actual, completed))
    p._after_focus_completed = lambda: None
    p.load_todo(_TODO_SINGLE)
    p.remaining = 300
    p.fstate = RUNNING
    p._on_finish()
    assert len(saved) == 1
    assert saved[0][1] == 1


def test_giveup_saves_record():
    p = _make_page()
    _mock_widgets(p)
    saved = []
    p._save_record = lambda actual, completed, reason=None: saved.append((actual, completed, reason))
    p._save_interrupt_detail = lambda reason: None
    p.load_todo(_TODO_SINGLE)
    p.fstate = RUNNING
    # 模拟无打断原因（取消对话框）
    from unittest.mock import patch
    with patch("src.ui_qt.pages.focus_page.QInputDialog.getText", return_value=("", False)), \
         patch("src.ui_qt.pages.focus_page.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        p._on_giveup()
    assert len(saved) == 1
    assert saved[0][1] == 0


# ==================== 1. 循环计时 ====================

def test_loop_init():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    assert p.total_loops == 3
    assert p.current_loop == 1


def test_loop_label_hidden_for_single():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._update_loop_label()
    p.lbl_loop.setVisible.assert_called_with(False)


def test_loop_label_shown_for_multi():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    p._update_loop_label()
    p.lbl_loop.setVisible.assert_called_with(True)
    p.lbl_loop.setText.assert_called_with("第 1/3 轮")


def test_loop_label_updates():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 2
    p._update_loop_label()
    p.lbl_loop.setText.assert_called_with("第 2/3 轮")


def test_all_loops_done_triggers_finished():
    p = _make_page()
    _mock_widgets(p)
    finished_called = []
    p.state.on_focus_finished = lambda: finished_called.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 3
    p._all_loops_done()
    assert p.fstate == IDLE
    assert len(finished_called) == 1


def test_loop_advances_after_rest_finished():
    p = _make_page()
    _mock_widgets(p)
    started = []
    p._start = lambda: started.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 1
    p._on_rest_finished()
    assert p.current_loop == 2
    assert len(started) == 1


def test_rest_finished_last_loop_calls_all_done():
    p = _make_page()
    _mock_widgets(p)
    done_called = []
    p._all_loops_done = lambda: done_called.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 3
    p._on_rest_finished()
    assert len(done_called) == 1


def test_no_rest_advances_loop():
    p = _make_page()
    _mock_widgets(p)
    started = []
    p._start = lambda: started.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 1
    p._on_no_rest()
    assert p.current_loop == 2
    assert len(started) == 1


def test_no_rest_last_loop_calls_all_done():
    p = _make_page()
    _mock_widgets(p)
    done_called = []
    p._all_loops_done = lambda: done_called.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 3
    p._on_no_rest()
    assert len(done_called) == 1


def test_reset_loop_state():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 2
    p._stopwatch_record_saved = True
    p._pause_start = datetime.datetime.now()
    p._reset_loop_state()
    assert p.current_loop == 1
    assert p._stopwatch_record_saved is False
    assert p._pause_start is None


def test_end_rest_advances_loop():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 1
    p._end_rest()
    assert p.current_loop == 2
    assert p.fstate == IDLE


def test_end_rest_last_loop_done():
    p = _make_page()
    _mock_widgets(p)
    done_called = []
    p._all_loops_done = lambda: done_called.append(True)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 3
    p._end_rest()
    assert len(done_called) == 1


# ==================== 2. 倒计时自动转正计时 ====================

def test_auto_switch_disabled_saves_record():
    settings_db = _FakeDBWithSettings({"auto_switch_stopwatch": "false"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    saved = []
    p._save_record = lambda actual, completed, reason=None: saved.append((actual, completed))
    p._after_focus_completed = lambda: None
    p.load_todo(_TODO_SINGLE)
    p.remaining = 0
    p.fstate = RUNNING
    p._try_auto_switch_stopwatch()
    assert len(saved) == 1
    assert p.fstate != STOPWATCH


def test_auto_switch_enabled_enters_stopwatch():
    settings_db = _FakeDBWithSettings({"auto_switch_stopwatch": "true"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p.remaining = 0
    p.fstate = RUNNING
    p._try_auto_switch_stopwatch()
    assert p.fstate == STOPWATCH
    assert p.elapsed == 0
    p.lbl_stopwatch_hint.setVisible.assert_called_with(True)
    p.lbl_stopwatch_hint.setText.assert_called_with("已自动转正计时")


def test_stopwatch_tick_increments_elapsed():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p.fstate = STOPWATCH
    p.elapsed = 0
    p._on_tick()
    assert p.elapsed == 1
    p._on_tick()
    assert p.elapsed == 2


def test_stopwatch_finish_saves_extra():
    p = _make_page()
    _mock_widgets(p)
    saved = []
    p._reset_loop_state = lambda: None
    p.focus_dao.create = lambda **kw: saved.append(kw) or 1
    p._toast = lambda msg: None
    p.load_todo(_TODO_SINGLE)
    p.planned = 1500
    p.elapsed = 120
    p.fstate = STOPWATCH
    p._on_finish()
    assert len(saved) == 1
    assert saved[0]["actual_duration"] == 1620
    assert p.fstate == IDLE


def test_stopwatch_giveup_discards():
    p = _make_page()
    _mock_widgets(p)
    p._reset_loop_state = lambda: None
    p.load_todo(_TODO_SINGLE)
    p.fstate = STOPWATCH
    from unittest.mock import patch
    with patch("src.ui_qt.pages.focus_page.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        p._on_giveup()
    assert p.fstate == IDLE


def test_stopwatch_finish_no_duplicate_save():
    p = _make_page()
    _mock_widgets(p)
    saved = []
    p._reset_loop_state = lambda: None
    p.focus_dao.create = lambda **kw: saved.append(kw) or 1
    p._toast = lambda msg: None
    p.load_todo(_TODO_SINGLE)
    p.planned = 1500
    p.elapsed = 60
    p.fstate = STOPWATCH
    p._on_finish()
    assert len(saved) == 1
    # 再次 finish 不应重复保存
    p.fstate = STOPWATCH
    p._on_finish()
    assert len(saved) == 1


# ==================== 3. 自定义暂停时间上限 ====================

def test_pause_records_start_time():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._start()
    p._on_pause()
    assert p._pause_start is not None


def test_pause_timeout_auto_giveup():
    settings_db = _FakeDBWithSettings({"max_pause_minutes": "3"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    saved = []
    p._save_record = lambda actual, completed, reason=None: saved.append((actual, completed, reason))
    p._toast = lambda msg: None
    p.load_todo(_TODO_SINGLE)
    p._start()
    p._on_pause()
    p._pause_start = datetime.datetime.now() - datetime.timedelta(minutes=4)
    result = p._check_pause_timeout()
    assert result is False
    assert p.fstate == IDLE
    assert len(saved) == 1
    assert saved[0][1] == 0
    assert "暂停超时" in saved[0][2]


def test_pause_within_limit_resumes():
    settings_db = _FakeDBWithSettings({"max_pause_minutes": "3"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._start()
    p._on_pause()
    p._pause_start = datetime.datetime.now() - datetime.timedelta(minutes=1)
    result = p._check_pause_timeout()
    assert result is True


def test_pause_no_limit():
    settings_db = _FakeDBWithSettings({"max_pause_minutes": "0"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._start()
    p._on_pause()
    p._pause_start = datetime.datetime.now() - datetime.timedelta(minutes=100)
    result = p._check_pause_timeout()
    assert result is True


# ==================== 4. 自定义番茄钟格言 ====================

def test_get_setting_reads_from_db():
    settings_db = _FakeDBWithSettings({"focus_motto": "心静自然凉"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    assert p._get_setting("focus_motto") == "心静自然凉"


def test_get_setting_default():
    p = _make_page()
    assert p._get_setting("nonexistent", "fallback") == "fallback"


# ==================== 5. 进入休息计时前询问 ====================

def test_ask_before_break_disabled_goes_direct():
    settings_db = _FakeDBWithSettings({
        "ask_before_break": "false",
        "default_break_duration": "300",
    })
    p = _make_page(settings_db)
    _mock_widgets(p)
    entered_rest = []
    p._enter_rest = lambda: entered_rest.append(True)
    p.load_todo(_TODO_SINGLE)
    p._ask_before_rest_or_direct()
    assert len(entered_rest) == 1


def test_ask_before_break_disabled_no_break():
    settings_db = _FakeDBWithSettings({
        "ask_before_break": "false",
        "default_break_duration": "0",
    })
    p = _make_page(settings_db)
    _mock_widgets(p)
    no_rest_called = []
    p._on_no_rest = lambda: no_rest_called.append(True)
    p.load_todo(_TODO_SINGLE)
    p._ask_before_rest_or_direct()
    assert len(no_rest_called) == 1


def test_ask_before_break_enabled_shows_dialog():
    p = _make_page()
    _mock_widgets(p)
    dialog_called = []
    p._show_break_dialog = lambda: dialog_called.append(True)
    p.load_todo(_TODO_SINGLE)
    p._ask_before_rest_or_direct()
    assert len(dialog_called) == 1


# ==================== 6. 自定义休息时长 ====================

def test_custom_break_duration_from_todo():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_CUSTOM_BREAK)
    assert p._get_effective_break_duration() == 600


def test_default_break_duration_from_settings():
    settings_db = _FakeDBWithSettings({"default_break_duration": "600"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    assert p._get_effective_break_duration() == 600


def test_enter_rest_uses_effective_duration():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_CUSTOM_BREAK)
    p._enter_rest()
    assert p.rest_remaining == 600
    assert p.fstate == RESTING


def test_enter_rest_zero_duration_calls_on_rest_finished():
    p = _make_page()
    _mock_widgets(p)
    finished_called = []
    p._on_rest_finished = lambda: finished_called.append(True)
    p.load_todo(_TODO_SINGLE)
    p._get_effective_break_duration = lambda: 0
    p._enter_rest()
    assert len(finished_called) == 1


# ==================== 7. 打断详情记录 ====================

def test_interrupt_detail_saved():
    p = _make_page()
    _mock_widgets(p)
    interrupt_saved = []
    def fake_create(focus_record_id, process_name, occurred_at):
        interrupt_saved.append((focus_record_id, process_name))
    p.interrupt_dao.create = fake_create
    p._save_record = lambda actual, completed, reason=None: None
    p.focus_dao.list_recent = lambda limit=None: [{"id": 42}]
    p.load_todo(_TODO_SINGLE)
    p.fstate = RUNNING
    from unittest.mock import patch
    with patch("src.ui_qt.pages.focus_page.QInputDialog.getText", return_value=("摸鱼", True)), \
         patch("src.ui_qt.pages.focus_page.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        p._on_giveup()
    assert len(interrupt_saved) == 1
    assert interrupt_saved[0][0] == 42
    assert interrupt_saved[0][1] == "摸鱼"


def test_interrupt_detail_not_saved_when_no_reason():
    p = _make_page()
    _mock_widgets(p)
    interrupt_saved = []
    p.interrupt_dao.create = lambda **kw: interrupt_saved.append(kw)
    p._save_record = lambda actual, completed, reason=None: None
    p.load_todo(_TODO_SINGLE)
    p.fstate = RUNNING
    from unittest.mock import patch
    with patch("src.ui_qt.pages.focus_page.QInputDialog.getText", return_value=("", False)), \
         patch("src.ui_qt.pages.focus_page.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        p._on_giveup()
    assert len(interrupt_saved) == 0


# ==================== 按钮状态 ====================

def test_buttons_stopwatch_state():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p.fstate = STOPWATCH
    p._update_buttons()
    # 通过 setEnabled 调用验证，而非 isEnabled()（mock 返回值不可靠）
    p.btn_finish.setEnabled.assert_called_with(True)
    p.btn_giveup.setEnabled.assert_called_with(True)
    p.btn_start.setEnabled.assert_called_with(False)
    p.btn_pause.setEnabled.assert_called_with(False)


def test_strict_mode_disables_pause():
    p = _make_page()
    _mock_widgets(p)
    strict_todo = {**_TODO_SINGLE, "timer_type": 3}
    p.load_todo(strict_todo)
    p._start()
    p._update_buttons()
    p.btn_pause.setEnabled.assert_called_with(False)


# ==================== 综合流程 ====================

def test_full_countdown_flow():
    settings_db = _FakeDBWithSettings({
        "auto_switch_stopwatch": "false",
        "ask_before_break": "false",
        "default_break_duration": "0",
    })
    p = _make_page(settings_db)
    _mock_widgets(p)
    saved = []
    p._save_record = lambda actual, completed, reason=None: saved.append((actual, completed))
    # 真实的 _all_loops_done 会设置 fstate=IDLE，mock 也需要这样做
    p._all_loops_done = lambda: (setattr(p, 'fstate', IDLE), done_called.append(True))
    done_called = []
    p.load_todo(_TODO_SINGLE)
    p._start()
    assert p.fstate == RUNNING
    # 模拟倒计时结束
    p.remaining = 1
    p._on_tick()
    assert p.remaining == 0
    p._on_tick()  # 第二次 tick 时 fstate 已经是 IDLE，不会再触发
    assert len(saved) == 1
    assert saved[0][1] == 1
    assert len(done_called) == 1


def test_load_todo_resets_stopwatch_state():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_SINGLE)
    p._stopwatch_record_saved = True
    p.lbl_stopwatch_hint.setVisible(True)
    p.load_todo(_TODO_SINGLE)
    assert p._stopwatch_record_saved is False
    p.lbl_stopwatch_hint.setVisible.assert_called_with(False)


def test_on_rest_giveup():
    p = _make_page()
    _mock_widgets(p)
    p.load_todo(_TODO_LOOP)
    p.current_loop = 2
    p._on_rest_giveup()
    assert p.fstate == IDLE


# ==================== 8. 自定义番茄钟格言生效 ====================

def test_effective_motto_uses_custom():
    settings_db = _FakeDBWithSettings({"focus_motto": "心静自然凉"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    assert p._effective_motto() == "心静自然凉"


def test_effective_motto_falls_back_to_random():
    settings_db = _FakeDBWithSettings({"focus_motto": ""})
    p = _make_page(settings_db)
    _mock_widgets(p)
    val = p._effective_motto()
    assert isinstance(val, str) and val != ""


def test_refresh_motto_shows_custom():
    settings_db = _FakeDBWithSettings({"focus_motto": "一念清净"})
    p = _make_page(settings_db)
    _mock_widgets(p)
    p._refresh_motto()
    p.lbl_motto.setText.assert_called_with("一念清净")


# ==================== 9. 午夜模式（midnight_shift）生效 ====================

def _save_and_capture_belong_date(midnight: str):
    """构造页面并调用 _save_record，捕获传入的 belong_date。"""
    settings_db = _FakeDBWithSettings({"midnight_shift": midnight})
    p = _make_page(settings_db)
    _mock_widgets(p)
    captured = {}
    p.focus_dao.create = lambda **kw: captured.update(kw) or 1
    p.ach_dao.evaluate = lambda: None
    p._toast = lambda msg: None
    p.current_todo = _TODO_SINGLE
    p.planned = 1500
    p.start_time = datetime.datetime(2026, 7, 16, 2, 30)  # 凌晨 2:30
    p._save_record(100, 1)
    return captured.get("belong_date")


def test_midnight_shift_off_keeps_start_date():
    """关闭午夜模式：凌晨记录归属当天（不偏移）。"""
    bd = _save_and_capture_belong_date("false")
    assert bd == datetime.date(2026, 7, 16)


def test_midnight_shift_on_offsets_before_4am():
    """开启午夜模式：凌晨 0-4 点记录归属前一天。"""
    bd = _save_and_capture_belong_date("true")
    assert bd == datetime.date(2026, 7, 15)


# ==================== 10. 计时完成提示音生效 ====================

def test_play_complete_sound_respects_setting(monkeypatch):
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    p = _make_page()
    _mock_widgets(p)
    called = {}
    monkeypatch.setattr(
        QApplication, "beep",
        staticmethod(lambda: called.setdefault("beep", True)))
    # 设置为 none：不播放
    p._get_setting = lambda k, d=None: "none"
    p._play_complete_sound()
    assert "beep" not in called
    # 设置为 default：播放系统提示音
    p._get_setting = lambda k, d=None: "default"
    p._play_complete_sound()
    assert called.get("beep") is True


def test_after_focus_completed_plays_sound():
    p = _make_page()
    _mock_widgets(p)
    played = []
    p._play_complete_sound = lambda: played.append(True)
    p._ask_before_rest_or_direct = lambda: None
    p._after_focus_completed()
    assert played == [True]


# ==================== 11. 全局快捷键重新注册回调 ====================

def test_edit_shortcut_triggers_reregister(monkeypatch):
    """保存新快捷键后，设置页应调用 state.on_shortcut_change 重新注册。"""
    from unittest.mock import MagicMock
    from src.ui_qt.pages.settings_page import SettingsPage
    s = MagicMock()
    s.on_shortcut_change = None
    sp = SettingsPage.__new__(SettingsPage)
    sp.state = s
    sp.settings_dao = MagicMock()
    sp.lbl_shortcut = MagicMock()
    sp._toast = lambda msg: None
    reregistered = {}
    s.on_shortcut_change = lambda combo: reregistered.setdefault("combo", combo)
    sp._apply_shortcut("Ctrl+Alt+S")
    assert reregistered.get("combo") == "Ctrl+Alt+S"


# ==================== 12. 学霸模式（前台进程拦截）整合 ====================

class _FakeSignal:
    """最小信号替身，支持 connect / emit。"""

    def __init__(self):
        self._handlers = []

    def connect(self, fn):
        self._handlers.append(fn)

    def emit(self, *a):
        for h in self._handlers:
            h(*a)


class _FakeGuard:
    """FocusGuard 替身：记录 start/stop，violation 可手动触发。"""

    def __init__(self, wl, sd, timer=None, parent=None):
        self.violation = _FakeSignal()
        self.restored = _FakeSignal()
        self.started = 0
        self.stopped = 0
        self.wl = wl
        self.sd = sd

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def _enable_guard(p, enable="true", strict="false"):
    p._get_setting = lambda k, d="": {
        "enable_focus_guard": enable,
        "strict_mode": strict,
        "ask_before_break": "false",
        "default_break_duration": "0",
    }.get(k, d)


def test_guard_starts_when_enabled(monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)
    p = _make_page()
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=0)
    p.fstate = IDLE
    p._start()
    assert p._guard is not None
    assert p._guard.started == 1


def test_guard_not_started_when_exempt(monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)
    p = _make_page()
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=1)
    p.fstate = IDLE
    p._start()
    assert p._guard is None


def test_guard_non_strict_appends_violation_and_continues(monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)
    p = _make_page()
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=0)
    p.fstate = RUNNING
    p.timer_type = 0
    p.planned = 1500
    p.remaining = 1000
    p._guard = _FakeGuard(None, None)
    p._on_guard_violation("chrome.exe", False)
    assert p.fstate == RUNNING  # 未结束，仅提醒
    assert "chrome.exe" in p._guard_violations


def test_guard_strict_aborts_focus(db, monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)
    p = _make_page(db)
    _mock_widgets(p)
    _enable_guard(p, "true", "true")
    # 隔离：清空专注记录相关表，避免共享库中其它测试的干扰
    try:
        p.focus_dao.db.execute("DELETE FROM focus_record")
        p.interrupt_dao.db.execute("DELETE FROM interrupt_details")
    except Exception:
        pass
    p.current_todo = dict(_TODO_SINGLE, id=1, title="T", is_amway_mode_exempted=0)
    p.fstate = RUNNING
    p.timer_type = 0
    p.planned = 1500
    p.remaining = 1400
    p._guard = _FakeGuard(None, None)
    p._on_guard_violation("game.exe", True)
    # 专注被结束
    assert p.fstate == IDLE
    assert p._guard.stopped == 1
    # 记录已保存且未完成，原因含学霸模式
    recs = p.focus_dao.list_recent(10)
    assert any(r["is_completed"] == 0 and "学霸模式" in (r["interrupt_reason"] or "")
               for r in recs)
    # 离开行为写入打断详情
    rid = p.focus_dao.list_recent(1)[0]["id"]
    details = p.interrupt_dao.list_by_focus(rid)
    assert any(d["process_name"] == "game.exe" for d in details)


def test_guard_violations_flushed_on_normal_finish(db, monkeypatch):
    monkeypatch.setattr("src.ui_qt.focus_guard.FocusGuard", _FakeGuard)
    p = _make_page(db)
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    try:
        p.focus_dao.db.execute("DELETE FROM focus_record")
        p.interrupt_dao.db.execute("DELETE FROM interrupt_details")
    except Exception:
        pass
    p.current_todo = dict(_TODO_SINGLE, id=1, title="T", is_amway_mode_exempted=0)
    p.fstate = RUNNING
    p.timer_type = 0
    p.planned = 1500
    p.remaining = 1000
    p._guard = _FakeGuard(None, None)
    # 非严格模式先记录一次离开
    p._on_guard_violation("chrome.exe", False)
    assert p.fstate == RUNNING
    # 正常完成
    p._on_finish()
    rec = p.focus_dao.list_recent(1)[0]
    assert rec["is_completed"] == 1
    details = p.interrupt_dao.list_by_focus(rec["id"])
    assert any(d["process_name"] == "chrome.exe" for d in details)


# ==================== 4. 学霸模式离开提醒去重（避免频繁重复） ====================

def test_guard_violation_reminds_once_not_repeatedly(monkeypatch):
    """同一离开期间，守门员每 2 秒上报也应只提醒一次。"""
    calls = []
    monkeypatch.setattr(
        "src.ui_qt.pages.focus_page.show_toast",
        lambda *a, **k: calls.append((a, k)))
    p = _make_page()
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=0)
    p.fstate = RUNNING
    p._guard = _FakeGuard(None, None)
    p._on_guard_violation("chrome.exe", False)
    p._on_guard_violation("chrome.exe", False)
    p._on_guard_violation("chrome.exe", False)
    assert len(calls) == 1  # 仅提醒一次


def test_guard_violation_remind_reset_after_restored(monkeypatch):
    """回到专注（restored）后再次离开，应可再次提醒一次。"""
    calls = []
    monkeypatch.setattr(
        "src.ui_qt.pages.focus_page.show_toast",
        lambda *a, **k: calls.append((a, k)))
    p = _make_page()
    _mock_widgets(p)
    _enable_guard(p, "true", "false")
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=0)
    p.fstate = RUNNING
    p._guard = _FakeGuard(None, None)
    p._on_guard_violation("chrome.exe", False)
    assert len(calls) == 1
    p._on_guard_restored()  # 回到专注
    p._on_guard_violation("chrome.exe", False)  # 再次离开
    assert len(calls) == 2


# ==================== 5. 白噪音计时开始自动播放 ====================

def _auto_play_page(auto_settings, noises):
    """构造一个可验证自动播放的专注页。"""
    p = _make_page()
    _mock_widgets(p)
    p.settings_dao = _fake_settings(auto_settings)
    p._noises = lambda: noises
    played = []
    p.noise_player.play_file = lambda path: (played.append(path), True)[1]
    p._update_music_button = lambda: None
    p.current_todo = dict(_TODO_SINGLE, is_amway_mode_exempted=0)
    p.fstate = IDLE
    return p, played


def test_auto_play_noise_on_start_when_enabled():
    """开启「计时开始自动播放」后，计时开始应自动播放上次选定音源。"""
    noises = [{"id": 1, "name": "雨声", "file_path": "rain.wav"}]
    p, played = _auto_play_page(
        {"auto_play_on_start": "true", "last_noise_id": "1"}, noises)
    p._start()
    assert played == ["rain.wav"]
    assert p._current_noise_id == 1
    # last_noise_id 被持久化为所选音源
    p.settings_dao.set.assert_called_with("last_noise_id", "1")


def test_auto_play_noise_falls_back_when_no_selection():
    """仅开启背景音但未显式选过音源时，回退到第一条可用音源。"""
    noises = [
        {"id": 1, "name": "雨声", "file_path": "rain.wav"},
        {"id": 2, "name": "海浪", "file_path": "sea.wav"},
    ]
    p, played = _auto_play_page(
        {"bg_music_enabled": "true"}, noises)
    p._start()
    assert played == ["rain.wav"]


def test_no_auto_play_when_disabled():
    """两项配置均未开启时，计时开始不应自动播放白噪音。"""
    noises = [{"id": 1, "name": "雨声", "file_path": "rain.wav"}]
    p, played = _auto_play_page({}, noises)
    p._start()
    assert played == []


if __name__ == "__main__":
    import sys
    failed = []
    passed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"  PASS: {name}")
            except Exception as e:
                failed.append(name)
                print(f"  FAIL: {name} -> {e}")
    print(f"\n{passed} passed, {len(failed)} failed")
    if failed:
        for f in failed:
            print(f"  - {f}")
        sys.exit(1)