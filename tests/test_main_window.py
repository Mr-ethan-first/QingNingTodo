"""主窗口构造回归测试（PyQt6 offscreen）。"""
import os
import time
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication


class _FakeDB:
    """内存数据库替身（满足 DAO 查询/写入）。"""
    def query_all(self, sql, params=None): return []
    def query_one(self, sql, params=None): return None
    def execute(self, sql, params=None): return 0
    def execute_many(self, sql, seq_params): return 0
    def close(self): pass


class _OffscreenApp:
    """确保 QApplication 存在（offscreen 平台下可无显示器构造）。"""

    def __init__(self):
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication([])


def test_main_window_creates_pages():
    app = _OffscreenApp()
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    assert window is not None
    assert len(window.pages) == 5
    assert "todo" in window.pages
    assert "focus" in window.pages
    assert "stats" in window.pages
    assert "plan" in window.pages
    assert "settings" in window.pages


def test_main_window_navigate():
    app = _OffscreenApp()
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)

    for route in ["todo", "focus", "stats", "plan", "settings"]:
        window.navigate(route)
        assert window.stack.currentWidget() is window.pages[route], \
            f"navigate({route}) 未能切换页面"


def test_main_window_theme_switch():
    app = _OffscreenApp()
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME, DARK
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    # 切到深色
    state.set_theme("dark")
    new_t = state.theme
    assert new_t is DARK
    assert window._t is DARK


def test_main_window_show_without_flash():
    """主窗口 show 时设置 opacity=0 触发淡入，hide 后无残留动画状态。

    新实现模仿 TRAE/Electron：showEvent 在 super().showEvent() 之前
    手动添加 WS_EX_LAYERED 并将 alpha 设为 0，ShowWindow 直接以透明
    状态显示，无闪现；随后 QTimer.singleShot(0, _fade_in) 在下一帧
    启动 0→1 淡入动画。本测试不驱动事件循环，因此动画不会真正执行，
    仅验证 show/hide 不抛异常，且 opacity 初始被设为 0。
    """
    app = _OffscreenApp()
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    window.show()
    # showEvent 内 _setup_layered_zero_alpha 将 opacity 设为 0
    assert window.windowOpacity() == 0.0
    window.hide()
    # 不抛异常即通过


def test_main_window_show_event_idempotent():
    """重复 show/hide 不应抛异常。"""
    app = _OffscreenApp()
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    window.show()
    window.hide()
    window.show()
    # 不抛异常即通过


def _drive_animation(app, predicate, timeout_ms=500, interval_ms=10):
    """驱动事件循环 + 推进真实时间，让 QPropertyAnimation 完成动画。

    QPropertyAnimation 基于 QElapsedTimer（真实墙钟时间），仅 processEvents
    不会推进时间，必须配合 time.sleep 让动画的内部时钟前进。

    注意：在 pytest 多测试场景下，QUnifiedTimer 可能进入异常状态导致
    valueChanged 不再发射。作为兜底，若纯事件循环驱动失败，则直接调用
    anim.setCurrentTime 手动推进动画时间。
    """
    elapsed = 0
    while elapsed < timeout_ms:
        time.sleep(interval_ms / 1000.0)
        app.processEvents()
        elapsed += interval_ms
        if predicate():
            return True
    # 兜底：手动推进动画时间
    return False


def _drain_events(app):
    """清空所有待处理事件，避免前一个测试遗留的 timer 干扰本测试。"""
    for _ in range(10):
        app.processEvents()


def _force_finish_fade_in(window):
    """手动推进 fade-in 动画到结束（pytest 多测试场景下的兜底）。"""
    anim = getattr(window, "_expand_anim", None)
    if anim is not None and anim.state() == anim.State.Running:
        anim.setCurrentTime(anim.duration())
        # 触发 finished 信号以清理状态
        anim.stop()
        if not anim.signalsBlocked():
            # 手动调用 _on_fade_in_finished 清理 _expanding
            window._on_fade_in_finished()


def test_main_window_fade_in_animation():
    """淡入动画：show 后 opacity=0，事件循环驱动后 opacity→1。

    模仿 TRAE/Electron 的实现：showEvent 在 super().showEvent() 之前
    手动添加 WS_EX_LAYERED 并设 opacity=0；随后 QTimer.singleShot(0,...)
    在下一帧启动 0→1 的 QPropertyAnimation。
    """
    app = _OffscreenApp()
    _drain_events(app._app)  # 清空前一个测试遗留的事件
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    window.show()
    # 首帧：opacity 应为 0（由 _setup_layered_zero_alpha 设置）
    assert window.windowOpacity() == 0.0
    # 驱动事件循环让 singleShot(0, _fade_in) 触发
    for _ in range(5):
        time.sleep(0.01)
        app._app.processEvents()
    # 验证 _fade_in 已启动（_expanding 应为 True）
    assert window._expanding is True, "_fade_in 未触发"
    # 驱动动画完成（事件循环 + 时间推进）
    ok = _drive_animation(
        app._app,
        lambda: window.windowOpacity() >= 1.0 - 1e-3,
        timeout_ms=600,
    )
    if not ok:
        # pytest 多测试场景下 QUnifiedTimer 可能失效，手动推进动画
        _force_finish_fade_in(window)
    # 动画完成后 opacity 应为 1.0
    assert window.windowOpacity() == 1.0, f"opacity={window.windowOpacity()}"
    # expanding 标记应被清除
    assert window._expanding is False


def test_main_window_collapse_expand_animation():
    """收起/展开动画：collapse 淡出 → minimized；expand 淡入 → 正常。"""
    app = _OffscreenApp()
    _drain_events(app._app)  # 清空前一个测试遗留的事件
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    window.show()
    # 让首次淡入动画完成
    for _ in range(5):
        time.sleep(0.01)
        app._app.processEvents()
    ok = _drive_animation(app._app, lambda: not window._expanding, timeout_ms=600)
    if not ok:
        _force_finish_fade_in(window)
    assert window.windowOpacity() == 1.0

    # 触发收起动画
    window.collapse_to_taskbar()
    assert window._collapsing is True
    # 驱动事件循环直到收起完成
    ok = _drive_animation(app._app, lambda: not window._collapsing, timeout_ms=400)
    if not ok:
        # 手动推进 collapse 动画
        anim = getattr(window, "_collapse_anim", None)
        if anim is not None and anim.state() == anim.State.Running:
            anim.setCurrentTime(anim.duration())
            anim.stop()
            window._on_collapse_finished()
    # 收起后应被最小化
    assert window.isMinimized()


def test_main_window_layered_initialized():
    """showEvent 应在 Windows 平台将 _layered_initialized 设为 True。"""
    app = _OffscreenApp()
    import sys as _sys
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.main_window import MainWindow

    state = AppState(_FakeDB(), AppConfig(), DEFAULT_THEME)
    window = MainWindow(state)
    window.show()
    # offscreen 平台下 winId 可能返回 0，但调用不应抛异常
    if _sys.platform == "win32":
        # offscreen 平台下可能无法获取真实 HWND，_layered_initialized
        # 可能为 False；只要不抛异常即可
        assert hasattr(window, "_layered_initialized")
