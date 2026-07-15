"""设置页面（Flet）：主题切换、个人信息、目标、白名单、锁屏、数据管理。"""
import datetime
import json

from flet import (
    Column, Row, Text, Container, TextField, TextButton, ListView, AlertDialog,
    Dropdown, dropdown, IconButton, PopupMenuButton, PopupMenuItem, SnackBar,
    padding, Icons as icons, FontWeight, MainAxisAlignment, CrossAxisAlignment, ControlEvent,
)
from src.ui_flet.pad import pad

from src.database import dao
from src.theme import Theme, THEMES
from src.ui_flet.widgets import card, section_title, primary_button, ghost_button, text_field

SECTION_ICONS = {
    "个人信息": "👤", "外观主题": "🎨", "习惯养成": "🎯",
    "专注白名单": "🛡", "定时锁屏": "🔒", "本地数据": "💾",
}


class SettingsPage(Column):
    def __init__(self, state):
        super().__init__(expand=True, scroll=None, spacing=0)
        self.state = state
        self.t = state.theme
        self.user_dao = dao.UserDAO(state.db)
        self.settings_dao = dao.SettingsDAO(state.db)
        self.goal_dao = dao.GoalDAO(state.db)
        self.wl_dao = dao.WhitelistDAO(state.db)
        self.lock_dao = dao.LockScheduleDAO(state.db)
        self._build()
        state.subscribe(self._on_theme)

    def _build(self):
        self.controls.clear()
        t = self.t
        self.controls.append(section_title(t, "设置", "⚙"))
        self.controls.append(Text("调墨色、定目标、守专注 · 随心而设", size=13, color=t.text_muted,
                                   margin=pad.only(bottom=14, top=2)))
        self.controls.append(self._sec_user())
        self.controls.append(Container(height=14))
        self.controls.append(self._sec_theme())
        self.controls.append(Container(height=14))
        self.controls.append(self._sec_goal())
        self.controls.append(Container(height=14))
        self.controls.append(self._sec_wl())
        self.controls.append(Container(height=14))
        self.controls.append(self._sec_lock())
        self.controls.append(Container(height=14))
        self.controls.append(self._sec_data())
        self.controls.append(Container(height=20))

    def did_mount(self):
        self.refresh()

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        self.refresh()

    # ---------------- 分区 ----------------
    def _section(self, title, *children):
        t = self.t
        return card(t, Column([section_title(t, title, SECTION_ICONS.get(title, "◆")),
                               Container(height=10)] + list(children), spacing=8), padding_=18)

    def _sec_user(self):
        t = self.t
        self.ed_nick = text_field(t, "昵称", width=240)
        return self._section("个人信息", Row([
            self.ed_nick,
            primary_button(t, "保存昵称", on_click=self._save_nick),
        ], spacing=10))

    def _sec_theme(self):
        t = self.t
        self.cb_theme = Dropdown(
            label="界面风格", width=260,
            options=[dropdown.Option(text=v.label, key=v.name) for v in THEMES.values()],
            value=self.state.theme_name,
            bgcolor=t.surface_variant, color=t.text, border_color=t.border,
            focused_border_color=t.primary, label_style=TextStyleC(t), border_radius=t.radius_md,
            on_select=self._on_theme_change,
        )
        preview = Row([
            _swatch(t, self.state.theme.bg, "背景"),
            _swatch(t, self.state.theme.surface, "卡片"),
            _swatch(t, self.state.theme.primary, "主色"),
        ], spacing=10)
        return self._section("外观主题", Row([self.cb_theme], spacing=10),
                             Text("一键切换白色 / 黑色风格，立即全局生效。", size=13, color=t.text_muted),
                             preview)

    def _sec_goal(self):
        t = self.t
        self.sp_daily = _num(t, 0, 1440, " 分钟/天")
        self.sp_weekly = _num(t, 0, 10080, " 分钟/周")
        self.sp_monthly = _num(t, 0, 44640, " 分钟/月")
        return self._section("习惯养成", Column([
            Row([Text("每日目标：", color=t.text_muted, width=90), self.sp_daily]),
            Row([Text("每周目标：", color=t.text_muted, width=90), self.sp_weekly]),
            Row([Text("每月目标：", color=t.text_muted, width=90), self.sp_monthly]),
            Container(height=4),
            primary_button(t, "保存目标", on_click=self._save_goals),
        ], spacing=10))

    def _sec_wl(self):
        t = self.t
        self.list_wl = ListView(height=120, spacing=6)
        return self._section("专注白名单", self.list_wl, Row([
            primary_button(t, "添加白名单", on_click=self._add_wl),
            ghost_button(t, "删除选中", on_click=self._del_wl),
        ], spacing=10))

    def _sec_lock(self):
        t = self.t
        self.ed_lock_start = text_field(t, "开始 (HH:MM)", value="23:00", width=140)
        self.ed_lock_end = text_field(t, "结束 (HH:MM)", value="07:00", width=140)
        self.list_lock = ListView(height=100, spacing=6)
        return self._section("定时锁屏", Row([
            self.ed_lock_start, self.ed_lock_end,
            primary_button(t, "添加时段", on_click=self._add_lock),
            ghost_button(t, "删除选中", on_click=self._del_lock),
        ], spacing=10), self.list_lock)

    def _sec_data(self):
        t = self.t
        self.lbl_db = Text("", size=13, color=t.text_muted)
        return self._section("本地数据", Row([
            primary_button(t, "导出备份 (JSON)", on_click=self._export),
            ghost_button(t, "修改数据库连接", on_click=self._change_db),
        ], spacing=10), self.lbl_db)

    # ---------------- 刷新 ----------------
    def refresh(self):
        t = self.t
        user = self.user_dao.get()
        if user:
            self.ed_nick.value = user["nickname"]
        for g in self.goal_dao.list():
            if g["title"] is None and g["target_duration"] is not None:
                mins = g["target_duration"] // 60
                if g["goal_type"] == 0:
                    self.sp_daily.value = str(mins)
                elif g["goal_type"] == 1:
                    self.sp_weekly.value = str(mins)
                elif g["goal_type"] == 2:
                    self.sp_monthly.value = str(mins)
        self._reload_wl()
        self._reload_lock()
        cfg = self.state.app_config.load()
        self.lbl_db.value = f"当前连接：{cfg.user}@{cfg.host}:{cfg.port}/{cfg.database}" if cfg else ""
        self.update()

    def _reload_wl(self):
        t = self.t
        self.list_wl.controls.clear()
        for w in self.wl_dao.list():
            self.list_wl.controls.append(_chip(t, f"{w['app_name']} ({w['process_name']}) #{w['id']}"))
        self.update()

    def _reload_lock(self):
        t = self.t
        self.list_lock.controls.clear()
        for l in self.lock_dao.list():
            en = "启用" if l["enabled"] else "停用"
            self.list_lock.controls.append(_chip(t, f"{l['start_time']} - {l['end_time']} [{en}] #{l['id']}"))
        self.update()

    # ---------------- 动作 ----------------
    def _save_nick(self, e):
        name = self.ed_nick.value.strip()
        if name:
            self.user_dao.update_nickname(name)
            self._toast("昵称已保存")

    def _on_theme_change(self, e):
        name = self.cb_theme.value
        self.state.set_theme(name)
        self.settings_dao.set("theme", name)
        self._toast(f"已切换为「{self.state.theme.label}」")

    def _save_goals(self, e):
        self.goal_dao.upsert_duration_goal(0, int(self.sp_daily.value or 0) * 60)
        self.goal_dao.upsert_duration_goal(1, int(self.sp_weekly.value or 0) * 60)
        self.goal_dao.upsert_duration_goal(2, int(self.sp_monthly.value or 0) * 60)
        self._toast("专注目标已保存")

    def _add_wl(self, e):
        dlg = AlertDialog(title=Text("添加白名单"),
            content=Column([TextField(label="应用名称"), TextField(label="进程名 (如 chrome.exe)")], spacing=10),
            actions=[TextButton("取消", on_click=lambda e: self._close(dlg)),
                     TextButton("保存", on_click=lambda e, d=dlg: self._save_wl(d))], modal=True)
        self.page.show_dialog(dlg)

    def _save_wl(self, dlg):
        name = dlg.content.controls[0].value.strip()
        proc = dlg.content.controls[1].value.strip() or name
        if name:
            self.wl_dao.add(name, proc)
        self.page.pop_dialog()
        self._reload_wl()

    def _del_wl(self, e):
        if self.list_wl.controls:
            last = self.list_wl.controls[-1]
            wid = int(last.controls[0].value.rsplit("#", 1)[-1])
            self.wl_dao.delete(wid)
            self._reload_wl()

    def _add_lock(self, e):
        self.lock_dao.create(start_time=self.ed_lock_start.value + ":00",
                             end_time=self.ed_lock_end.value + ":00")
        self._reload_lock()

    def _del_lock(self, e):
        if self.list_lock.controls:
            lid = int(self.list_lock.controls[-1].controls[0].value.rsplit("#", 1)[-1])
            self.lock_dao.delete(lid)
            self._reload_lock()

    def _export(self, e):
        from flet import FilePicker
        fp = FilePicker()
        try:
            self.page.services.append(fp)
        except Exception:
            self.page.overlay.append(fp)
        self.page.update()
        try:
            path = fp.save_file(file_name="qingning_backup.json",
                                allowed_extensions=["json"])
        except Exception as ex:
            self._toast(f"导出失败：{ex}")
            return
        self._write_export(path)

    def _write_export(self, path):
        if not path:
            return
        try:
            tables = ["user", "todo_group", "todo", "focus_record", "goal",
                      "future_plan", "checkin_record", "achievement",
                      "focus_whitelist", "lock_schedule", "settings"]
            dump = {tb: self.state.db.query_all(f"SELECT * FROM `{tb}`") for tb in tables}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, default=str, indent=2)
            self._toast(f"已导出到：{path}")
        except Exception as ex:
            self._toast(f"导出失败：{ex}")

    def _change_db(self, e):
        self._toast("请在重启应用后修改数据库连接（保持数据一致）。")

    def _close(self, dlg):
        self.page.pop_dialog()

    def _toast(self, msg):
        if self.page:
            self.page.show_dialog(SnackBar(Text(msg)))


def _num(t: Theme, min_v, max_v, suffix):
    return TextField(value="0", width=200, suffix=suffix,
        keyboard_type="number", bgcolor=t.surface_variant, color=t.text,
        border_color=t.border, focused_border_color=t.primary, border_radius=t.radius_md)


def _swatch(t: Theme, color, label):
    return Column([
        Container(width=46, height=30, border_radius=8, bgcolor=color,
                  border=_b(t, t.border)),
        Text(label, size=11, color=t.text_subtle),
    ], spacing=4, horizontal_alignment=CrossAxisAlignment.CENTER)


def _chip(t: Theme, text):
    return Container(content=Text(text, size=13, color=t.text),
                     bgcolor=t.surface_variant, border_radius=t.radius_sm,
                     padding=pad.symmetric(horizontal=12, vertical=7))


def _b(t: Theme, color):
    from flet import border, BorderSide
    s = BorderSide(1, color)
    return border.Border(left=s, top=s, right=s, bottom=s)


def TextStyleC(t: Theme):
    from flet import TextStyle
    return TextStyle(color=t.text_muted)
