"""未来计划表页面（Flet）。"""
import datetime

from flet import (
    Column, Row, Text, Container, ListView, AlertDialog, TextField, TextButton,
    DatePicker, PopupMenuButton, PopupMenuItem, padding, FontWeight,
    MainAxisAlignment, CrossAxisAlignment, ControlEvent, Icons as icons,
)
from src.ui_flet.pad import pad

from src.database import dao
from src.theme import Theme
from src.ui_flet.widgets import (
    card, section_title, primary_button, ghost_button, text_field, hero_banner, badge,
)


class PlanPage(Column):
    def __init__(self, state):
        super().__init__(expand=True, scroll=None, spacing=0)
        self.state = state
        self.t = state.theme
        self.dao = dao.FuturePlanDAO(state.db)
        self._build()
        state.subscribe(self._on_theme)

    def _build(self):
        self.controls.clear()
        t = self.t
        header = Row([
            section_title(t, "未来计划表", "🗺"),
            primary_button(t, "＋ 新建计划", icon=icons.ADD, on_click=self._add_plan),
        ], alignment=MainAxisAlignment.SPACE_BETWEEN)
        tip = Text("记录重要事项的日期与倒计时，事项过期后不会消失，作为纪念保留。",
                   size=13, color=t.text_muted)
        self.list_view = ListView(expand=True, spacing=10, padding=pad.only(bottom=12))
        body = card(t, Column([tip, self.list_view], spacing=10), padding_=18)
        self.controls.append(header)
        self.controls.append(hero_banner(t, "奔赴山海之约", "重要之事，铭刻于心"))
        self.controls.append(body)

    def did_mount(self):
        self.refresh()

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        self.refresh()

    def refresh(self):
        self.list_view.controls.clear()
        today = datetime.date.today()
        for p in self.dao.list():
            self.list_view.controls.append(self._plan_row(p, today))
        self.update()

    def _plan_row(self, p, today):
        t = self.t
        days = (p["target_date"] - today).days
        if days > 0:
            cd = f"还有 {days} 天"
        elif days == 0:
            cd = "就是今天！"
        else:
            cd = f"已过去 {abs(days)} 天"
        title = Text(p["title"], size=15, weight=FontWeight.W_600, color=t.text)
        sub = Row([
            badge(t, str(p["target_date"])),
            Text(cd, size=12, color=t.primary, weight=FontWeight.W_600),
            Text(p.get("remark") or "", size=12, color=t.text_subtle),
        ], spacing=8)
        menu = PopupMenuButton(items=[
            PopupMenuItem(content="编辑", icon=icons.EDIT,
                          on_click=lambda e, x=p: self._edit_plan(x)),
            PopupMenuItem(content="删除", icon=icons.DELETE,

                          on_click=lambda e, x=p: self._del_plan(x)),
        ], icon=icons.MORE_VERT)
        return Container(
            content=Row([Column([title, sub], spacing=4, expand=True), menu],
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=CrossAxisAlignment.CENTER),
            bgcolor=t.surface_variant, border_radius=t.radius_md,
            padding=pad.symmetric(horizontal=14, vertical=10),
        )

    def _add_plan(self, e):
        self._open_dialog(None)

    def _edit_plan(self, p):
        self._open_dialog(p)

    def _open_dialog(self, plan):
        dlg = _PlanDialog(self, plan)
        self.page.show_dialog(dlg.build())

    def _del_plan(self, p):
        dlg = AlertDialog(
            title=Text("删除计划"), content=Text(f"确认删除『{p['title']}』？"),
            actions=[
                TextButton("取消", on_click=lambda e: self._close(dlg)),
                TextButton("删除", on_click=lambda e: self._do_del(dlg, p)),
            ], modal=True)
        self.page.show_dialog(dlg)

    def _do_del(self, dlg, p):
        self.dao.delete(p["id"])
        self.page.pop_dialog()
        self.refresh()

    def _close(self, dlg):
        self.page.pop_dialog()


class _PlanDialog:
    def __init__(self, page_ref, plan):
        self.page_ref = page_ref
        self.t = page_ref.t
        self.plan = plan

    def build(self):
        t = self.t
        self.ed_title = text_field(t, "事项名称", value=self.plan["title"] if self.plan else "")
        default = (self.plan["target_date"] if self.plan
                   else datetime.date.today() + datetime.timedelta(days=30))
        self.picker = DatePicker(value=default)
        self.ed_remark = text_field(t, "备注", value=self.plan.get("remark") or "" if self.plan else "",
                                    multiline=True)
        form = Column([self.ed_title, self.picker, self.ed_remark], spacing=12, width=380)
        return AlertDialog(
            title=Text("编辑计划" if self.plan else "新建未来计划"),
            content=form, modal=True,
            actions=[
                TextButton("取消", on_click=lambda e: self._cancel()),
                TextButton("保存", on_click=lambda e: self._save()),
            ])

    def _cancel(self):
        self.page_ref.page.pop_dialog()

    def _save(self):
        title = self.ed_title.value.strip()
        if not title:
            self.ed_title.error_text = "请输入事项名称"
            self.ed_title.update()
            return
        target = self.picker.value or datetime.date.today()
        if self.plan:
            self.page_ref.dao.update(self.plan["id"], title, target, self.ed_remark.value.strip() or None)
        else:
            self.page_ref.dao.create(title, target, self.ed_remark.value.strip() or None)
        self.page_ref.page.pop_dialog()
        self.page_ref.refresh()
