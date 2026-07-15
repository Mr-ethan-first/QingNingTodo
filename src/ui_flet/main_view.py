"""主窗口视图（Flet）：侧边导航 + 页面容器。

负责构建导航栏、承载五个页面、处理主题切换时的整体换肤（更新页面背景）。
"""
from flet import (
    Column, Row, Text, Container, NavigationRail, NavigationRailDestination,
    Icons as icons, padding, alignment, FontWeight, BoxShadow, MainAxisAlignment,
    CrossAxisAlignment, Switch,
)
from src.ui_flet.pad import pad

from src import __app_name__, __version__
from src.theme import Theme
from src.ui_flet.state import AppState
from src.ui_flet.pages.todo_page import TodoPage
from src.ui_flet.pages.focus_page import FocusPage
from src.ui_flet.pages.stats_page import StatsPage
from src.ui_flet.pages.plan_page import PlanPage
from src.ui_flet.pages.settings_page import SettingsPage
from src.ui_flet.widgets import border_1


class MainView(Row):
    ROUTES = ["todo", "focus", "stats", "plan", "settings"]
    NAV = [
        ("待办清单", icons.CHECKLIST, "📝"),
        ("专注计时", icons.TIMER, "🍅"),
        ("数据统计", icons.INSIGHTS, "📊"),
        ("未来计划", icons.EXPLORE, "🗺"),
        ("设置", icons.SETTINGS, "⚙"),
    ]

    def __init__(self, state: AppState):
        super().__init__(expand=True, spacing=0)
        self.state = state
        self.t = state.theme
        self.pages = {}
        self._build()
        state.subscribe(self._on_theme)
        state.nav_callback = self.navigate
        # 跨页面回调
        state.on_start_focus = self._on_start_focus
        state.on_focus_finished = self._on_focus_finished

    # ---------------- 构建 ----------------
    def _build(self):
        self.controls.clear()
        self.t = self.state.theme

        rail = NavigationRail(
            selected_index=0,
            label_type="all",
            bgcolor=self.t.surface,
            indicator_color=self.t.soft(),
            destinations=[
                NavigationRailDestination(
                    icon=icons.CHECKLIST_OUTLINED if i != 0 else icons.CHECKLIST,
                    selected_icon=icons.CHECKLIST,
                    label=name,
                ) for i, (name, _, _) in enumerate(self.NAV)
            ],
            on_change=self._on_nav,
            width=170,
        )
        # 用自定义侧栏替代，获得更好视觉控制
        self.sidebar = self._sidebar()
        self.sidebar_container = Container(
            content=self.sidebar, width=210, bgcolor=self.t.surface,
            border=border_1(self.t, self.t.border),
        )

        # 页面
        self.pages = {
            "todo": TodoPage(self.state),
            "focus": FocusPage(self.state),
            "stats": StatsPage(self.state),
            "plan": PlanPage(self.state),
            "settings": SettingsPage(self.state),
        }
        self.content = Column(
            [self.pages["todo"]], expand=True, scroll=None,
        )
        self.content_container = Container(content=self.content, expand=True,
                                           bgcolor=self.t.bg, padding=pad.all(22))

        self.controls.extend([self.sidebar_container, self.content_container])

    def _sidebar(self) -> Column:
        t = self.t
        brand = Container(
            content=Column([
                Row([
                    Container(content=Text("🍅", size=22), padding=pad.all(6),
                              bgcolor=t.soft(), border_radius=10),
                    Column([
                        Text("番茄ToDo", size=16, weight=FontWeight.BOLD, color=t.text),
                        Text("专注 · 致远", size=11, color=t.text_subtle),
                    ], spacing=0),
                ], spacing=10),
            ]),
            padding=pad.all(16),
        )
        nav_col = Column(spacing=4)
        self.nav_btns = []
        for i, (name, icon, emoji) in enumerate(self.NAV):
            btn = self._nav_button(name, emoji, i)
            self.nav_btns.append(btn)
            nav_col.controls.append(btn)
        self.nav_btns[0].selected = True

        ver = Text(f"v{__version__}", size=11, color=t.text_subtle)
        return Column([
            brand,
            Container(height=6),
            nav_col,
            Container(expand=True),
            Container(content=ver, padding=pad.only(left=16, bottom=12)),
        ], spacing=2, expand=True)

    def _nav_button(self, name, emoji, idx):
        t = self.t
        btn = Container(
            content=Row([Text(emoji, size=16), Text(name, size=14, weight=FontWeight.W_500)],
                        spacing=10, vertical_alignment=CrossAxisAlignment.CENTER),
            padding=pad.symmetric(horizontal=14, vertical=11),
            border_radius=t.radius_md, on_click=lambda e, i=idx: self.navigate(self.ROUTES[i]),
            data=idx,
        )
        btn.selected = False
        return btn

    def _style_nav(self):
        t = self.t
        for i, btn in enumerate(self.nav_btns):
            sel = getattr(btn, "selected", False)
            btn.bgcolor = t.soft() if sel else None
            for c in btn.content.controls:
                if isinstance(c, Text):
                    c.color = t.primary if sel else t.text_muted
                    if isinstance(c, Text) and c.weight == FontWeight.W_500:
                        c.weight = FontWeight.BOLD if sel else FontWeight.W_500

    # ---------------- 交互 ----------------
    def _on_nav(self, e):
        self.navigate(self.ROUTES[e.control.selected_index])

    def navigate(self, route: str):
        if route not in self.pages:
            return
        idx = self.ROUTES.index(route)
        # 选中态
        for i, btn in enumerate(self.nav_btns):
            btn.selected = (i == idx)
        self._style_nav()
        for i, btn in enumerate(self.nav_btns):
            btn.update()
        # 切换页面
        page = self.pages[route]
        # 先挂载（加入可见容器并 update）再刷新，避免 refresh 内的 update
        # 在控件尚未加入 page 时执行而抛出 "must be added to the page first"
        self.content.controls = [page]
        self.content.update()
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                pass

    def _on_start_focus(self, todo):
        self.pages["focus"].load_todo(todo)
        self.navigate("focus")

    def _on_focus_finished(self):
        try:
            self.pages["stats"].refresh()
        except Exception:
            pass

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        # 重建后保持当前路由：简单回到 todo
        self.update()
