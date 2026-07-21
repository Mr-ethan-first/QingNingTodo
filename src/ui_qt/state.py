"""应用全局状态（PyQt 版）。

持有数据库、当前主题与主题变更订阅。页面构建时从 AppState 读取当前主题；
切换主题时广播给所有订阅者，由页面就地换肤（重建自绘控件配色）。
"""
from typing import Callable, List

from src.database import dao
from src.theme import (
    Theme, get_theme, DEFAULT_THEME, set_current_theme,
    derive_theme_with_primary,
)


class AppState:
    def __init__(self, db, app_config, theme_name: str = DEFAULT_THEME):
        self.db = db
        self.app_config = app_config
        self._theme_name = theme_name
        # 自定义主色覆盖（来自 settings.theme_color，为空表示使用默认主色）
        try:
            self._theme_color_override = (dao.SettingsDAO(db).get("theme_color") or "").strip()
        except Exception:
            self._theme_color_override = ""
        # DAO 实例
        self.todo_dao = dao.TodoDAO(db)
        self.group_dao = dao.TodoGroupDAO(db)
        self.plan_dao = dao.FuturePlanDAO(db)
        self.focus_record_dao = dao.FocusRecordDAO(db)
        self.stats_dao = dao.StatsDAO(db)
        self.settings_dao = dao.SettingsDAO(db)
        self.user_dao = dao.UserDAO(db)
        self.achievement_dao = dao.AchievementDAO(db)
        self.goal_dao = dao.GoalDAO(db)
        self.habit_checkin_dao = dao.HabitCheckinDAO(db)
        self.interrupt_detail_dao = dao.InterruptDetailDAO(db)
        self.whitelist_dao = dao.WhitelistDAO(db)
        self.lock_schedule_dao = dao.LockScheduleDAO(db)
        self.white_noise_dao = dao.WhiteNoiseDAO(db)
        self._subscribers: List[Callable[[Theme], None]] = []
        self._bg_subscribers: List[Callable[[], None]] = []
        self.nav_callback: Callable[[str], None] = None
        # 跨页面回调
        self.on_start_focus: Callable = None
        self.on_focus_finished: Callable = None
        # 全局快捷键变更回调（设置页保存新快捷键时调用，由主窗口注册）
        self.on_shortcut_change: Callable = None

    @property
    def theme(self) -> Theme:
        """当前有效主题：在 light/dark 基础上叠加自定义主色（若设置）。"""
        base = get_theme(self._theme_name)
        override = self._theme_color_override
        if override:
            try:
                return derive_theme_with_primary(base, override)
            except Exception:
                return base
        return base

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def set_theme(self, name: str) -> Theme:
        """切换 light/dark 基础主题（保留自定义主色覆盖）。"""
        self._theme_name = name
        return self._broadcast()

    def apply_theme_color(self, hex_color: str) -> Theme:
        """设置/清除自定义主色（hex_color 为空则恢复默认主色）。"""
        self._theme_color_override = hex_color or ""
        return self._broadcast()

    def _broadcast(self) -> Theme:
        t = self.theme
        set_current_theme(t)
        for cb in self._subscribers:
            try:
                cb(t)
            except Exception:
                pass
        return t

    def subscribe(self, cb: Callable[[Theme], None]) -> None:
        if cb not in self._subscribers:
            self._subscribers.append(cb)

    def subscribe_background(self, cb: Callable[[], None]) -> None:
        """订阅背景海报变更（仅专注页用于即时刷新背景）。"""
        if cb not in self._bg_subscribers:
            self._bg_subscribers.append(cb)

    def notify_background_change(self) -> None:
        """广播背景海报变更给订阅者（如专注页立即刷新背景）。"""
        for cb in self._bg_subscribers:
            try:
                cb()
            except Exception:
                pass

    def navigate(self, route: str) -> None:
        if self.nav_callback:
            self.nav_callback(route)
