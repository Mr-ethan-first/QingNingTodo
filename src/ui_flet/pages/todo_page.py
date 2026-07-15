"""待办清单页面（Flet）。"""
import datetime

from flet import (
    Column, Row, Text, Container, ListView, AlertDialog, TextField, Dropdown,
    dropdown, IconButton, PopupMenuButton, PopupMenuItem, TextButton,
    alignment, padding, Icons as icons, FontWeight, ScrollMode, MainAxisAlignment,
    CrossAxisAlignment, ControlEvent, TextStyle, TextDecoration,
)
from src.ui_flet.pad import pad

from src.database import dao
from src.theme import Theme
from src.ui_flet.widgets import (
    card, section_title, primary_button, ghost_button, text_field,
    dropdown_field, badge, hero_banner, border_1,
)

TIMER_TYPES = ["普通番茄钟", "正计时", "倒计时", "严格模式"]
REPEAT_TYPES = ["不重复", "每日", "每周", "每月"]
PRIORITY = ["普通", "重要", "紧急"]


class TodoPage(Column):
    def __init__(self, state):
        super().__init__(expand=True, scroll=ScrollMode.AUTO, spacing=0)
        self.state = state
        self.t = state.theme
        self.todo_dao = dao.TodoDAO(state.db)
        self.group_dao = dao.TodoGroupDAO(state.db)
        self.filter_group = "all"
        self.filter_status = 0
        self._build()
        state.subscribe(self._on_theme)

    # ---------------- 构建 ----------------
    def _build(self):
        self.controls.clear()
        t = self.t
        self.cb_group = dropdown_field(
            t, "待办集", [("all", "全部")] + [(g["id"], g["name"]) for g in self.group_dao.list()],
            value=self.filter_group, width=180, on_change=self._on_filter,
        )
        self.cb_status = dropdown_field(
            t, "状态", [(0, "进行中"), (1, "已完成"), (2, "全部")],
            value=self.filter_status, width=140, on_change=self._on_filter,
        )
        header = Row([
            section_title(t, "待办清单", "📝"),
            Row([
                ghost_button(t, "＋ 待办集", icon=icons.ADD, on_click=self._add_group),
                primary_button(t, "＋ 新建待办", icon=icons.ADD, on_click=self._add_todo),
            ], spacing=8),
        ], alignment=MainAxisAlignment.SPACE_BETWEEN)

        toolbar = Row([self.cb_group, self.cb_status], spacing=12)

        self.list_view = ListView(expand=True, spacing=10, padding=pad.only(bottom=12))
        body = card(t, Column([toolbar, self.list_view], spacing=8), padding_=18)

        self.controls.append(header)
        self.controls.append(hero_banner(t, "规划今日之事，集于方寸之间", "井然有序，专注致远"))
        self.controls.append(body)

    def did_mount(self):
        # 控件加入 page 后再做首次数据加载（flet 0.86 要求 update 前必须已挂载）
        self._refresh_list()

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        self._refresh_list()

    # ---------------- 数据 ----------------
    def refresh(self):
        self._refresh_list()
        self.update()

    def _on_filter(self, e: ControlEvent):
        self.filter_group = self.cb_group.value
        self.filter_status = int(self.cb_status.value)
        self._refresh_list()

    def _refresh_list(self):
        self.list_view.controls.clear()
        status = None if self.filter_status == 2 else self.filter_status
        gid = None if self.filter_group == "all" else int(self.filter_group)
        todos = self.todo_dao.list(status=status, group_id=gid)
        groups = {g["id"]: g["name"] for g in self.group_dao.list()}
        for td in todos:
            self.list_view.controls.append(self._todo_row(td, groups))
        self.update()

    def _todo_row(self, td: dict, groups: dict) -> Container:
        t = self.t
        gname = groups.get(td.get("group_id")) or "未分类"
        done = td["status"] == 1
        mins = td["duration"] // 60
        title = Text(td["title"], size=15, weight=FontWeight.W_600,
                     color=t.text_muted if done else t.text,
                     style=TextStyle(decoration=TextDecoration.LINE_THROUGH) if done else None)
        meta = Row([
            badge(t, gname),
            badge(t, TIMER_TYPES[td["timer_type"]]),
            Text(f"{mins} 分钟", size=12, color=t.text_subtle),
        ], spacing=8)
        left = Column([title, meta], spacing=4, expand=True)
        menu = PopupMenuButton(items=[
            PopupMenuItem(content="开始专注", icon=icons.PLAY_ARROW,
                          on_click=lambda e, x=td: self._start_focus(x)),
            PopupMenuItem(content="编辑", icon=icons.EDIT,
                          on_click=lambda e, x=td: self._edit_todo(x)),
            PopupMenuItem(content="标记完成" if not done else "标记进行中",
                          icon=icons.CHECK_CIRCLE,
                          on_click=lambda e, x=td: self._toggle_done(x)),
            PopupMenuItem(content="删除", icon=icons.DELETE,
                          on_click=lambda e, x=td: self._delete_todo(x)),
        ], icon=icons.MORE_VERT)
        return Container(
            content=Row([left, menu], alignment=MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=CrossAxisAlignment.CENTER),
            bgcolor=t.surface_variant if not done else t.surface,
            border_radius=t.radius_md,
            padding=pad.symmetric(horizontal=14, vertical=10),
            border=border_1(t, t.border),
        )

    # ---------------- 动作 ----------------
    def _start_focus(self, td: dict):
        self.state.navigate("focus")
        # 通知主窗口加载
        if hasattr(self.state, "on_start_focus"):
            self.state.on_start_focus(td)

    def _toggle_done(self, td: dict):
        if td["status"] == 1:
            self.todo_dao.update(td["id"], status=0, completed_at=None)
        else:
            self.todo_dao.complete(td["id"])
        self._refresh_list()

    def _delete_todo(self, td: dict):
        dlg = AlertDialog(
            title=Text("删除待办"), content=Text(f"确认删除『{td['title']}』？"),
            actions=[
                TextButton("取消", on_click=lambda e: self._close(dlg)),
                TextButton("删除", on_click=lambda e: self._do_delete(dlg, td)),
            ], modal=True,
        )
        self.page.show_dialog(dlg)

    def _do_delete(self, dlg, td):
        self.todo_dao.delete(td["id"])
        self.page.pop_dialog()
        self._refresh_list()

    def _add_group(self, e):
        dlg = _GroupDialog(self, None)
        self.page.show_dialog(dlg.build())

    def _add_todo(self, e):
        dlg = _TodoDialog(self, None)
        self.page.show_dialog(dlg.build())

    def _edit_todo(self, td):
        dlg = _TodoDialog(self, td)
        self.page.show_dialog(dlg.build())

    def _close(self, dlg):
        self.page.pop_dialog()


class _TodoDialog:
    def __init__(self, page_ref, todo):
        self.page_ref = page_ref
        self.t = page_ref.t
        self.todo = todo
        self.groups = page_ref.group_dao.list()

    def build(self):
        t = self.t
        self.ed_title = text_field(t, "待办名称", value=self.todo["title"] if self.todo else "")
        self.cb_group = dropdown_field(
            t, "待办集",
            [("0", "未分类")] + [(str(g["id"]), g["name"]) for g in self.groups],
            value=str(self.todo["group_id"] or "0") if self.todo else "0", width=200)
        self.cb_timer = dropdown_field(t, "计时方式",
            [(i, v) for i, v in enumerate(TIMER_TYPES)], value=str(self.todo["timer_type"] if self.todo else 0), width=200)
        self.sp_duration = _num_field(t, "专注时长(分钟)", self.todo["duration"] // 60 if self.todo else 25, 1, 600)
        self.sp_break = _num_field(t, "休息时长(分钟)", self.todo["break_duration"] // 60 if self.todo else 5, 0, 120)
        self.sp_loop = _num_field(t, "循环次数", self.todo["loop_count"] if self.todo else 1, 1, 20)
        self.cb_priority = dropdown_field(t, "优先级",
            [(i, v) for i, v in enumerate(PRIORITY)], value=str(self.todo["priority"] if self.todo else 0), width=200)
        self.cb_repeat = dropdown_field(t, "重复",
            [(i, v) for i, v in enumerate(REPEAT_TYPES)], value=str(self.todo["repeat_type"] if self.todo else 0), width=200)

        form = Column([
            self.ed_title,
            Row([self.cb_group, self.cb_timer], spacing=12),
            Row([self.sp_duration, self.sp_break], spacing=12),
            Row([self.sp_loop, self.cb_priority], spacing=12),
            self.cb_repeat,
        ], spacing=12, width=460)

        return AlertDialog(
            title=Text("编辑待办" if self.todo else "新建待办"),
            content=form, modal=True, scrollable=True,
            actions=[
                TextButton("取消", on_click=lambda e: self._cancel()),
                TextButton("保存", on_click=lambda e: self._save()),
            ],
        )

    def _cancel(self):
        self.page_ref.page.pop_dialog()

    def _save(self):
        title = self.ed_title.value.strip()
        if not title:
            self.ed_title.error_text = "请输入待办名称"
            self.ed_title.update()
            return
        values = dict(
            title=title,
            group_id=(int(self.cb_group.value) if self.cb_group.value != "0" else None),
            timer_type=int(self.cb_timer.value),
            duration=int(self.sp_duration.value or 25) * 60,
            break_duration=int(self.sp_break.value or 0) * 60,
            loop_count=int(self.sp_loop.value or 1),
            priority=int(self.cb_priority.value),
            repeat_type=int(self.cb_repeat.value),
        )
        if self.todo:
            self.page_ref.todo_dao.update(self.todo["id"], **values)
        else:
            self.page_ref.todo_dao.create(**values)
        self.page_ref.page.pop_dialog()
        self.page_ref._refresh_list()


class _GroupDialog:
    def __init__(self, page_ref, group):
        self.page_ref = page_ref
        self.t = page_ref.t

    def build(self):
        t = self.t
        self.ed_name = text_field(t, "待办集名称")
        return AlertDialog(
            title=Text("新建待办集"),
            content=self.ed_name, modal=True,
            actions=[
                TextButton("取消", on_click=lambda e: self._cancel()),
                TextButton("保存", on_click=lambda e: self._save()),
            ],
        )

    def _cancel(self):
        self.page_ref.page.pop_dialog()

    def _save(self):
        name = self.ed_name.value.strip()
        if not name:
            self.ed_name.error_text = "请输入名称"
            self.ed_name.update()
            return
        self.page_ref.group_dao.create(name)
        self.page_ref.page.pop_dialog()
        self.page_ref._build()
        self.page_ref.update()


def _num_field(t: Theme, label: str, value: int, min_v: int, max_v: int):
    from flet import TextField
    return TextField(label=label, value=str(value), width=200,
        keyboard_type="number", bgcolor=t.surface_variant, color=t.text,
        border_color=t.border, focused_border_color=t.primary,
        border_radius=t.radius_md)
