"""专注计时页面（番茄钟核心，Flet）。"""
import datetime
import threading

from flet import (
    Column, Row, Text, Container, ElevatedButton, OutlinedButton, Dropdown,
    dropdown, IconButton, AlertDialog, TextField, TextButton, TextAlign,
    alignment, padding, Icons as icons, FontWeight, MainAxisAlignment, CrossAxisAlignment,
    Colors, ControlEvent,
)
from src.ui_flet.pad import pad

from src.database import dao
from src.theme import Theme
from src.ui_flet.widgets import card, hero_banner, section_title, primary_button

TIMER_TYPES = ["普通番茄钟", "正计时", "倒计时", "严格模式"]
IDLE, RUNNING, PAUSED, RESTING = "idle", "running", "paused", "resting"


class FocusPage(Column):
    def __init__(self, state):
        super().__init__(expand=True, scroll=None, spacing=0,
                         horizontal_alignment=CrossAxisAlignment.CENTER)
        self.state = state
        self.t = state.theme
        self.focus_dao = dao.FocusRecordDAO(state.db)
        self.ach_dao = dao.AchievementDAO(state.db)
        self.noise_dao = dao.WhiteNoiseDAO(state.db)

        self.fstate = IDLE
        self.current_todo = None
        self.remaining = 0
        self.elapsed = 0
        self.planned = 1500
        self.start_time = None
        self._timer = None
        self._stop = threading.Event()
        self._build()
        state.subscribe(self._on_theme)

    def _build(self):
        self.controls.clear()
        t = self.t
        self.lbl_task = Text("请选择待办开始专注", size=20, weight=FontWeight.BOLD,
                             color=t.text, text_align=TextAlign.CENTER)
        self.lbl_state = Text("空闲", size=14, color=t.text_muted)
        self.lbl_timer = Text("25:00", size=72, weight=FontWeight.BOLD, color=t.primary,
                              text_align=TextAlign.CENTER)

        self.cb_noise = dropdown_field(t, "白噪音",
            [("0", "关闭")] + [(str(n["id"]), n["name"]) for n in self._noises()],
            value="0", width=220)

        self.btn_start = primary_button(t, "开始", icon=icons.PLAY_ARROW, on_click=self._on_start)
        self.btn_pause = OutlinedButton(content=Text("暂停", color=t.primary), icon=icons.PAUSE,
            on_click=self._on_pause, style=_ob(t))
        self.btn_finish = OutlinedButton(content=Text("提取完成", color=t.primary), icon=icons.CHECK_CIRCLE,
            on_click=self._on_finish, style=_ob(t))
        self.btn_giveup = OutlinedButton(content=Text("放弃", color=t.primary), icon=icons.STOP_CIRCLE,
            on_click=self._on_giveup, style=_ob(t))

        panel = Column([
            self.lbl_task,
            Text("焚香静坐，专注当下 · 一番茄钟，半刻清欢", size=13, color=t.text_muted),
            self.lbl_state,
            Container(height=18),
            self.lbl_timer,
            Container(height=12),
            Row([self.cb_noise], alignment=MainAxisAlignment.CENTER),
            Container(height=20),
            Row([self.btn_start, self.btn_pause, self.btn_finish, self.btn_giveup],
                alignment=MainAxisAlignment.CENTER, spacing=12),
        ], horizontal_alignment=CrossAxisAlignment.CENTER, spacing=6)

        self.controls.append(hero_banner(t, "专注当下", "一念清净，万般从容"))
        self.controls.append(card(t, panel, padding_=28))
        self._update_buttons()

    def _noises(self):
        try:
            return self.noise_dao.list()
        except Exception:
            return []

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        self.update()

    # ---------------- 外部加载 ----------------
    def load_todo(self, todo: dict):
        if self.fstate in (RUNNING, PAUSED):
            self._toast("当前正在专注中，请先结束本次专注。")
            return
        self.current_todo = todo
        self.planned = todo["duration"]
        self.lbl_task.value = todo["title"]
        self.timer_type = todo["timer_type"]
        if self.timer_type == 1:
            self.elapsed = 0
            self.lbl_timer.value = "00:00"
        else:
            self.remaining = self.planned
            self._render(self.remaining)
        self.fstate = IDLE
        self.lbl_state.value = f"就绪 · {TIMER_TYPES[self.timer_type]}"
        self._update_buttons()
        self.update()

    # ---------------- 计时 ----------------
    def _start_loop(self):
        self._stop.clear()
        self.start_time = datetime.datetime.now()
        self.fstate = RUNNING
        self.lbl_state.value = "专注中…"
        self._update_buttons()
        self.update()
        self._timer = threading.Thread(target=self._run, daemon=True)
        self._timer.start()

    def _run(self):
        while not self._stop.is_set():
            self._stop.wait(1)
            if self._stop.is_set():
                return
            self._tick()

    def _tick(self):
        if self.fstate == RUNNING:
            if self.timer_type == 1:
                self.elapsed += 1
                self._render(self.elapsed)
            else:
                self.remaining -= 1
                self._render(max(0, self.remaining))
                if self.remaining <= 0:
                    self._save_record(self.planned, 1)
                    self._toast("本次番茄钟完成！")
                    self._enter_rest()
        elif self.fstate == RESTING:
            self.rest_remaining -= 1
            self._render(max(0, self.rest_remaining))
            if self.rest_remaining <= 0:
                self._end_rest()

    def _stop_timer(self):
        self._stop.set()
        if self._timer and self._timer.is_alive():
            self._timer.join(timeout=2)
        self._timer = None

    def _on_start(self, e):
        if not self.current_todo:
            self._toast("请先在『待办清单』选择待办。")
            return
        if self.timer_type == 1:
            self.elapsed = 0
        else:
            self.remaining = self.planned
        self._start_loop()

    def _on_pause(self, e):
        if self.fstate == RUNNING:
            self._stop_timer()
            self.fstate = PAUSED
            self.lbl_state.value = "已暂停"
        elif self.fstate == PAUSED:
            self._start_loop()
            self.lbl_state.value = "专注中…"
        self._update_buttons()
        self.update()

    def _on_finish(self, e):
        if self.fstate not in (RUNNING, PAUSED, RESTING):
            return
        self._stop_timer()
        if self.fstate == RESTING:
            self._end_rest()
            return
        actual = self.elapsed if self.timer_type == 1 else (self.planned - self.remaining)
        self._save_record(actual, 1)
        self._toast(f"本次专注 {actual//60} 分 {actual%60} 秒，已记录！")
        self._enter_rest()

    def _on_giveup(self, e):
        if self.fstate not in (RUNNING, PAUSED):
            return
        self._stop_timer()
        actual = self.elapsed if self.timer_type == 1 else (self.planned - self.remaining)
        reason = self._ask_reason()
        self._save_record(actual, 0, reason)
        self.fstate = IDLE
        self.lbl_state.value = "已放弃"
        if self.timer_type != 1:
            self.remaining = self.planned
            self._render(self.remaining)
        else:
            self.elapsed = 0
            self.lbl_timer.value = "00:00"
        self._update_buttons()
        self.update()

    def _enter_rest(self):
        self.fstate = RESTING
        self.rest_remaining = (self.current_todo["break_duration"] if self.current_todo else 0)
        if self.rest_remaining <= 0:
            self.fstate = IDLE
            self.lbl_state.value = "已完成"
            self._reset_display()
            self._update_buttons()
            return
        self.lbl_state.value = "休息一下 ☕"
        self._render(self.rest_remaining)
        self._start_loop()
        self._update_buttons()

    def _end_rest(self):
        self._stop_timer()
        self.fstate = IDLE
        self.lbl_state.value = "休息结束，可开始下个番茄钟"
        self._reset_display()
        self._update_buttons()
        self.update()

    def _reset_display(self):
        if self.current_todo and self.timer_type == 1:
            self.elapsed = 0
            self.lbl_timer.value = "00:00"
        elif self.current_todo:
            self.remaining = self.planned
            self._render(self.remaining)
        self.update()

    def _render(self, secs):
        secs = max(0, int(secs))
        try:
            on_page = self.lbl_timer is not None and self.lbl_timer.page is not None
        except RuntimeError:
            on_page = False
        if on_page:
            self.lbl_timer.value = f"{secs//60:02d}:{secs%60:02d}"
            self.lbl_timer.update()

    def _save_record(self, actual, completed, reason=None):
        try:
            self.focus_dao.create(
                todo_id=self.current_todo["id"],
                timer_type=self.current_todo["timer_type"],
                planned_duration=self.planned,
                actual_duration=max(0, actual),
                start_time=self.start_time or datetime.datetime.now(),
                end_time=datetime.datetime.now(),
                is_completed=completed,
                record_name=self.current_todo["title"],
                interrupt_reason=reason,
            )
            self.ach_dao.evaluate()
            if hasattr(self.state, "on_focus_finished"):
                self.state.on_focus_finished()
        except Exception as e:
            self._toast(f"记录保存失败：{e}")

    def _ask_reason(self):
        dlg = AlertDialog(
            title=Text("打断原因"), content=TextField(label="可选", multiline=True),
            actions=[TextButton("确定", on_click=lambda e: self._close_reason(dlg))], modal=True)
        self.page.show_dialog(dlg)
        return getattr(dlg.content, "value", None)

    def _close_reason(self, dlg):
        self.page.pop_dialog()

    def _update_buttons(self):
        running = self.fstate == RUNNING
        paused = self.fstate == PAUSED
        resting = self.fstate == RESTING
        self.btn_start.disabled = not (self.fstate == IDLE and self.current_todo is not None)
        strict = self.current_todo and self.current_todo.get("timer_type") == 3
        self.btn_pause.disabled = not ((running or paused) and not strict)
        self.btn_finish.disabled = not (running or paused or resting)
        self.btn_giveup.disabled = not (running or paused)

    def _toast(self, msg):
        if self.page:
            from flet import SnackBar
            self.page.show_dialog(SnackBar(Text(msg)))

    def refresh(self):
        pass


def _ob(t: Theme):
    from flet import ButtonStyle, RoundedRectangleBorder, BorderSide
    return ButtonStyle(
        color=t.primary, bgcolor=t.surface, overlay_color=t.soft(),
        side=BorderSide(1, t.primary),
        padding=pad.symmetric(horizontal=18, vertical=10),
        shape=RoundedRectangleBorder(radius=t.radius_md),
    )


def dropdown_field(t: Theme, label, options, value=None, width=None):
    from flet import Dropdown, dropdown
    return Dropdown(label=label, options=[dropdown.Option(text=o[1], key=str(o[0])) for o in options],
        value=value, width=width, bgcolor=t.surface_variant, color=t.text,
        border_color=t.border, focused_border_color=t.primary,
        label_style=TextStyle2(t), border_radius=t.radius_md)


def TextStyle2(t: Theme):
    from flet import TextStyle
    return TextStyle(color=t.text_muted)
