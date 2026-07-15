"""数据统计页面（Flet）。"""
import datetime

from flet import (
    Column, Row, Text, Container, ListView, ScrollMode, MainAxisAlignment,
    CrossAxisAlignment, padding, FontWeight, GridView, TextAlign, alignment,
)
from src.ui_flet.pad import pad

from src.database import dao
from src.theme import Theme
from src.ui_flet.widgets import card, section_title, hero_banner, badge


def fmt_minutes(seconds: int) -> str:
    m = seconds // 60
    if m >= 60:
        return f"{m//60}小时{m%60}分"
    return f"{m}分钟"


class StatsPage(Column):
    def __init__(self, state):
        super().__init__(expand=True, scroll=ScrollMode.AUTO, spacing=0)
        self.state = state
        self.t = state.theme
        self.stats = dao.StatsDAO(state.db)
        self.focus_dao = dao.FocusRecordDAO(state.db)
        self.ach_dao = dao.AchievementDAO(state.db)
        self._build()
        state.subscribe(self._on_theme)

    def _build(self):
        self.controls.clear()
        t = self.t
        self.controls.append(section_title(t, "数据统计", "📊"))
        self.controls.append(
            Text("观专注之积淀，察时日之勤勉", size=13, color=t.text_muted,
                 margin=pad.only(bottom=14, top=2)))

        # 概览卡片
        self.card_total = _stat_card(t, "累计专注", "0")
        self.card_today = _stat_card(t, "今日专注", "0")
        self.card_count = _stat_card(t, "累计次数", "0")
        self.card_streak = _stat_card(t, "连续天数", "0")
        grid = Row([self.card_total, self.card_today, self.card_count, self.card_streak],
                   spacing=12, alignment=MainAxisAlignment.SPACE_BETWEEN)
        self.controls.append(grid)

        # 热力图
        self.controls.append(Container(height=16))
        self.controls.append(section_title(t, "近30天专注热力图", "🗓"))
        self.heat = _Heatmap(t)
        self.controls.append(card(t, self.heat, padding_=18))

        self.controls.append(Container(height=14))
        self.controls.append(section_title(t, "高效时间区间（按小时）", "⏰"))
        self.lbl_hours = Text("暂无数据", size=14, color=t.text_muted)
        self.controls.append(card(t, self.lbl_hours, padding_=16))

        self.controls.append(Container(height=14))
        self.controls.append(section_title(t, "专注时长分布（按待办集）", "📚"))
        self.lbl_groups = Text("暂无数据", size=14, color=t.text_muted)
        self.controls.append(card(t, self.lbl_groups, padding_=16))

        self.controls.append(Container(height=14))
        self.controls.append(section_title(t, "成就徽章", "🏅"))
        self.lbl_badges = Text("", size=14, color=t.text_muted)
        self.controls.append(card(t, self.lbl_badges, padding_=16))

        self.controls.append(Container(height=14))
        self.controls.append(section_title(t, "历史记录（时间轴）", "📜"))
        self.table = _RecordsTable(t)
        self.controls.append(card(t, self.table, padding_=6))
        self.controls.append(Container(height=20))

    def did_mount(self):
        self.refresh()

    def _on_theme(self, theme: Theme):
        self.t = theme
        self._build()
        self.refresh()

    def refresh(self):
        t = self.t
        total = self.stats.total_focus()
        today = self.stats.today_focus()
        self.card_total.set(fmt_minutes(total["total_seconds"]))
        self.card_today.set(fmt_minutes(today["total_seconds"]))
        self.card_count.set(str(total["count"]))
        self.card_streak.set(f"{self.stats.streak_days()} 天")

        self.heat.set_data(self.stats.daily_distribution(30), t.heat_base, t)

        hours = self.stats.hour_distribution()
        if hours:
            parts = [f"{h['hour']:02d}时: {fmt_minutes(int(h['total']))}" for h in hours if int(h["total"]) > 0]
            self.lbl_hours.value = "　".join(parts) if parts else "暂无数据"
        else:
            self.lbl_hours.value = "暂无数据"

        groups = self.stats.group_distribution()
        if groups:
            parts = [f"{g['name']}: {fmt_minutes(int(g['total']))}" for g in groups if int(g["total"]) > 0]
            self.lbl_groups.value = "　".join(parts) if parts else "暂无数据"
        else:
            self.lbl_groups.value = "暂无数据"

        badges = self.ach_dao.list()
        self.lbl_badges.value = "　".join(
            f"{'🏅' if b['unlocked'] else '🔒'} {b['badge_name']}" for b in badges)

        self.table.set_rows(self.focus_dao.list_recent(50), t)
        self.update()


class _StatCard(Container):
    def __init__(self, t: Theme, title, value):
        self._val = Text(value, size=24, weight=FontWeight.BOLD, color=t.primary,
                         text_align=TextAlign.CENTER)
        super().__init__(
            content=Column([
                self._val,
                Text(title, size=13, color=t.text_muted, text_align=TextAlign.CENTER),
            ], spacing=4, horizontal_alignment=CrossAxisAlignment.CENTER),
            bgcolor=t.surface, border_radius=t.radius_md, padding=pad.all(16),
            border=_b(t, t.border), width=200,
            shadow=_sh(t),
        )

    def set(self, value):
        self._val.value = value
        self._val.update()


def _stat_card(t: Theme, title, value):
    return _StatCard(t, title, value)


class _Heatmap(Container):
    def __init__(self, t: Theme):
        super().__init__(padding=pad.all(6))
        self.content = Row(spacing=4, wrap=True, alignment=MainAxisAlignment.START)

    def set_data(self, rows, base, t):
        today = datetime.date.today()
        vals = {r["belong_date"]: int(r["total"]) for r in rows}
        # 过去30天
        cells = []
        for i in range(30):
            d = today - datetime.timedelta(days=29 - i)
            v = vals.get(d, 0)
            color = self._shade(base, v, t)
            cells.append(Container(width=18, height=18, border_radius=4, bgcolor=color,
                                   tooltip=f"{d} · {fmt_minutes(v)}"))
        self.content.controls = cells
        self.update()

    @staticmethod
    def _shade(base, v, t):
        if v == 0:
            return t.surface_variant
        # 由主色透明度表达强度
        ratio = min(1.0, v / 7200)  # 2小时封顶
        alpha = int(70 + ratio * 185)
        from flet import Colors
        return Colors.with_opacity(alpha / 255.0, base)


class _RecordsTable(Column):
    def __init__(self, t: Theme):
        super().__init__(spacing=0, scroll=ScrollMode.AUTO)

    def set_rows(self, records, t):
        self.controls.clear()
        self.controls.append(_rec_header(t))
        for r in records:
            name = r.get("record_name") or "专注"
            status = "完成" if r["is_completed"] else "放弃"
            self.controls.append(_rec_row(t, name, fmt_minutes(r["actual_duration"]),
                                          str(r["start_time"]), status))
        self.update()


def _rec_header(t: Theme):
    return _rec_row(t, "名称", "时长", "开始时间", "状态", header=True)


def _rec_row(t: Theme, name, dur, start, status, header=False):
    color = t.text_muted if header else t.text
    weight = FontWeight.BOLD if header else FontWeight.NORMAL
    bg = t.surface_variant if header else None
    return Container(
        content=Row([
            Text(name, size=13, color=color, weight=weight, expand=2),
            Text(dur, size=13, color=color, weight=weight, expand=1),
            Text(start, size=13, color=color, weight=weight, expand=2),
            Text(status, size=13, color=(t.success if status == "完成" else t.danger),
                 weight=weight, expand=1),
        ], spacing=8),
        padding=pad.symmetric(horizontal=12, vertical=9),
        bgcolor=bg, border_radius=t.radius_sm,
    )


def _b(t: Theme, color):
    from flet import border, BorderSide
    s = BorderSide(1, color)
    return border.Border(left=s, top=s, right=s, bottom=s)


def _sh(t: Theme):
    from flet import BoxShadow
    return BoxShadow(blur_radius=t.shadow.get("blur_radius", 12),
                     color=t.shadow.get("color", "#00000010"),
                     offset=t.shadow.get("offset", (0, 3)))
