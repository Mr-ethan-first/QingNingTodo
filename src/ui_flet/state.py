"""应用全局状态：持有数据库、当前主题与主题变更订阅。

页面在构建时从 AppState 读取当前主题；切换主题时，AppState 广播给所有
订阅者（页面），由页面重建自身控件树完成换肤。
"""
from typing import Callable, List

from src.theme import Theme, get_theme, DEFAULT_THEME


class AppState:
    def __init__(self, db, app_config, theme_name: str = DEFAULT_THEME):
        self.db = db
        self.app_config = app_config
        self._theme_name = theme_name
        self._subscribers: List[Callable[[Theme], None]] = []
        self.nav_callback: Callable[[str], None] = None

    @property
    def theme(self) -> Theme:
        return get_theme(self._theme_name)

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def set_theme(self, name: str) -> Theme:
        self._theme_name = name
        t = self.theme
        for cb in self._subscribers:
            try:
                cb(t)
            except Exception:
                pass
        return t

    def subscribe(self, cb: Callable[[Theme], None]) -> None:
        if cb not in self._subscribers:
            self._subscribers.append(cb)

    def navigate(self, route: str) -> None:
        if self.nav_callback:
            self.nav_callback(route)
