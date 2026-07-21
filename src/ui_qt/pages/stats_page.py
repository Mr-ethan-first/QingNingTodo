"""数据统计页面（PyQt6 / QPainter 自绘图表）。

布局概览（从上到下）：
1. Hero 横幅 + 设置齿轮
2. 概览卡片（累计专注 / 今日专注）
3. 专注时长分布（日/周/月/自定义切换 + 饼图）
4. 本月专注时段分布（MonthHeatmap）
5. 月度数据（AreaLineChart）
6. 起床/睡眠打卡分布（可设置开关）
7. 月度打断原因分布（PieChart）
8. 年度数据（AreaLineChart）
"""
import calendar
import datetime

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.ui_qt.charts import (
    AreaLineChart, BarChart, MonthHeatmap,
    PieChart, StatCard, fmt_minutes,
)
from src.ui_qt.icons import icon
from src.ui_qt.pages import PageBase
from src.ui_qt.widgets import (
    CalendarDateEdit, card, hero_banner, section_title, ghost_button,
)


# ======================= 周期 Tab 常量 =======================
TAB_DAY, TAB_WEEK, TAB_MONTH, TAB_CUSTOM = 0, 1, 2, 3
TAB_LABELS = ["日", "周", "月", "自定"]


# ======================= 辅助函数 =======================
def _to_date(d):
    """安全将各种日期类型转为 datetime.date。"""
    if isinstance(d, datetime.date):
        return d
    if isinstance(d, str):
        try:
            return datetime.date.fromisoformat(d)
        except Exception:
            return datetime.date.today()
    return datetime.date.today()


def _md(d):
    """日期 → 'MM/DD'"""
    try:
        return f"{d.month:02d}/{d.day:02d}"
    except Exception:
        return str(d)[5:10]


def _days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def _week_range():
    """返回本周一和本周日的 date。"""
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return monday, sunday


def _month_range(year, month):
    """返回某月第一天和最后一天的 date。"""
    first = datetime.date(year, month, 1)
    last = datetime.date(year, month, _days_in_month(year, month))
    return first, last


# ======================= StatsPage =======================
class StatsPage(PageBase):
    def __init__(self, state):
        self.stats = state.stats_dao
        self.focus_dao = state.focus_record_dao
        self.checkin_dao = state.habit_checkin_dao
        self.interrupt_dao = state.interrupt_detail_dao
        self.settings_dao = state.settings_dao
        super().__init__(state)

    # ------------------------------------------------------------------ #
    #  构建界面
    # ------------------------------------------------------------------ #
    def _build(self):
        t = self._t

        # ---------- 读取统计设置 ----------
        self._load_settings()

        # ---------- Hero + 齿轮按钮 ----------
        hero_row = QHBoxLayout()
        hero = hero_banner("数据统计", "观专注之积淀，察时日之勤勉")
        hero_row.addWidget(hero, 1)
        self._gear_btn = QPushButton()
        self._gear_btn.setFixedSize(40, 40)
        self._gear_btn.setIcon(icon("gear", t.text_muted, 22))
        self._gear_btn.setIconSize(QSize(22, 22))
        self._gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gear_btn.setObjectName("iconBtn")
        self._gear_btn.clicked.connect(self._open_settings)
        hero_row.addWidget(self._gear_btn, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self._lay.addLayout(hero_row)

        # ---------- 概览卡片 ----------
        self._build_overview_cards()

        # ---------- 专注时长分布（日/周/月/自定义 + 饼图） ----------
        self._build_distribution_section()

        # ---------- 本月专注时段分布 ----------
        self._build_monthly_heatmap_section()

        # ---------- 月度数据 ----------
        self._build_monthly_trend_section()

        # ---------- 起床打卡分布 ----------
        self._build_checkin_section("wake", "起床打卡分布", 0)

        # ---------- 睡眠打卡分布 ----------
        self._build_checkin_section("sleep", "睡眠打卡分布", 1)

        # ---------- 月度打断原因分布 ----------
        self._build_interrupt_section()

        # ---------- 年度数据 ----------
        self._build_yearly_section()

        self._lay.addStretch(1)

    # -------------------------------------------------------------- #
    #  概览卡片
    # -------------------------------------------------------------- #
    def _build_overview_cards(self):
        t = self._t
        # 累计专注：次数、时长、日均
        self.card_total_count = StatCard("累计次数", "0", t.primary)
        self.card_total_duration = StatCard("累计时长", "0", t.primary)
        self.card_avg_daily = StatCard("日均时长", "0", t.primary)
        # 今日专注：次数、时长、放弃次数
        self.card_today_count = StatCard("今日次数", "0", t.success)
        self.card_today_duration = StatCard("今日时长", "0", t.success)
        self.card_today_abandoned = StatCard("今日放弃", "0", t.danger)

        # 统一 spacing=12
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        for c in [self.card_total_count, self.card_total_duration, self.card_avg_daily]:
            row1.addWidget(c, 1)
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        for c in [self.card_today_count, self.card_today_duration, self.card_today_abandoned]:
            row2.addWidget(c, 1)
        # 两行卡片之间间距
        self._lay.addLayout(row1)
        self._lay.addSpacing(12)
        self._lay.addLayout(row2)

    # -------------------------------------------------------------- #
    #  专注时长分布
    # -------------------------------------------------------------- #
    def _build_distribution_section(self):
        t = self._t

        # 标题行（使用 section_title 组件）
        title_row = QHBoxLayout()
        title_row.addWidget(section_title("专注时长分布", "chart"))
        # 日期导航
        self._dist_prev = QPushButton()
        self._dist_prev.setFixedSize(32, 32)
        self._dist_prev.setIcon(icon("left", t.text_muted, 18))
        self._dist_prev.setIconSize(QSize(18, 18))
        self._dist_prev.setObjectName("iconBtn")
        self._dist_prev.clicked.connect(self._dist_nav_prev)

        self._dist_date_label = QLabel()
        self._dist_date_label.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        self._dist_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dist_date_label.setMinimumWidth(140)

        self._dist_next = QPushButton()
        self._dist_next.setFixedSize(32, 32)
        self._dist_next.setIcon(icon("right", t.text_muted, 18))
        self._dist_next.setIconSize(QSize(18, 18))
        self._dist_next.setObjectName("iconBtn")
        self._dist_next.clicked.connect(self._dist_nav_next)

        title_row.addWidget(self._dist_prev)
        title_row.addWidget(self._dist_date_label)
        title_row.addWidget(self._dist_next)
        self._lay.addLayout(title_row)

        # 日期导航与 Tab 之间的间距
        self._lay.addSpacing(8)

        # Tab 切换
        self._dist_tab = TAB_DAY
        self._dist_date = datetime.date.today()  # 日视图用
        self._custom_start_date = datetime.date.today() - datetime.timedelta(days=7)
        self._custom_end_date = datetime.date.today()
        self._dist_tab_btns = []
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        for i, label in enumerate(TAB_LABELS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("segTab")
            btn.setChecked(i == self._dist_tab)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._switch_dist_tab(idx))
            self._dist_tab_btns.append(btn)
            tab_row.addWidget(btn)
        tab_row.addStretch(1)
        self._lay.addLayout(tab_row)

        # 自定义日期范围选择行（仅 TAB_CUSTOM 时显示）
        self._custom_range_row = QHBoxLayout()
        self._custom_range_row.setSpacing(8)
        today = datetime.date.today()
        lbl_from = QLabel("从")
        lbl_from.setStyleSheet(f"font-size:13px; color:{t.text_muted};")
        self._custom_start = CalendarDateEdit()
        self._custom_start.setDate(today - datetime.timedelta(days=7))
        self._custom_start.setDisplayFormat("yyyy-MM-dd")
        self._custom_start.setFixedHeight(36)
        self._custom_start.setMinimumWidth(140)
        lbl_to = QLabel("至")
        lbl_to.setStyleSheet(f"font-size:13px; color:{t.text_muted};")
        self._custom_end = CalendarDateEdit()
        self._custom_end.setDate(today)
        self._custom_end.setDisplayFormat("yyyy-MM-dd")
        self._custom_end.setFixedHeight(36)
        self._custom_end.setMinimumWidth(140)
        btn_apply = QPushButton("应用")
        btn_apply.setObjectName("primary")
        btn_apply.setFixedHeight(36)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.clicked.connect(self._apply_custom_range)
        self._custom_range_row.addWidget(lbl_from)
        self._custom_range_row.addWidget(self._custom_start)
        self._custom_range_row.addWidget(lbl_to)
        self._custom_range_row.addWidget(self._custom_end)
        self._custom_range_row.addWidget(btn_apply)
        self._custom_range_row.addStretch(1)
        self._custom_range_widget = QWidget()
        self._custom_range_widget.setLayout(self._custom_range_row)
        self._custom_range_widget.setVisible(False)
        self._lay.addWidget(self._custom_range_widget)

        # Tab 与图表之间间距
        self._lay.addSpacing(8)

        # 分布柱状图（card 容器）
        dist_card = card()
        dist_lay = QVBoxLayout(dist_card)
        dist_lay.setContentsMargins(16, 14, 16, 14)
        self._dist_chart = BarChart(t.primary)
        dist_lay.addWidget(self._dist_chart)
        self._lay.addWidget(dist_card)

        # 饼图（card 容器 + 图表标题）
        self._lay.addSpacing(12)
        pie_card = card()
        pie_lay = QVBoxLayout(pie_card)
        pie_lay.setContentsMargins(16, 14, 16, 14)
        pie_lay.setSpacing(8)
        pie_title = QLabel("专注时长占比")
        pie_title.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        pie_lay.addWidget(pie_title)
        self._dist_pie = PieChart()
        pie_lay.addWidget(self._dist_pie)
        self._lay.addWidget(pie_card)

        # "查看专注记录" 按钮
        self._lay.addSpacing(8)
        self._view_records_btn = QPushButton("查看专注记录")
        self._view_records_btn.setObjectName("ghost")
        self._view_records_btn.setFixedHeight(36)
        self._view_records_btn.clicked.connect(self._view_focus_records)
        self._lay.addWidget(self._view_records_btn)

    # -------------------------------------------------------------- #
    #  本月专注时段分布（MonthHeatmap）
    # -------------------------------------------------------------- #
    def _build_monthly_heatmap_section(self):
        self._heatmap_year = datetime.date.today().year
        self._heatmap_month = datetime.date.today().month

        # 标题行（使用 section_title）
        title_row = QHBoxLayout()
        title_row.addWidget(section_title("本月专注时段分布", "chart"))
        self._lay.addLayout(title_row)

        # 导航行
        nav_row = QHBoxLayout()
        nav_row.addStretch(1)
        self._hm_prev = QPushButton()
        self._hm_prev.setFixedSize(32, 32)
        self._hm_prev.setIcon(icon("left", self._t.text_muted, 18))
        self._hm_prev.setIconSize(QSize(18, 18))
        self._hm_prev.setObjectName("iconBtn")
        self._hm_prev.clicked.connect(self._hm_nav_prev)

        self._hm_title = QLabel()
        self._hm_title.setStyleSheet(f"font-size:14px; font-weight:600; color:{self._t.text};")
        nav_row.addWidget(self._hm_prev)
        nav_row.addWidget(self._hm_title)

        self._hm_next = QPushButton()
        self._hm_next.setFixedSize(32, 32)
        self._hm_next.setIcon(icon("right", self._t.text_muted, 18))
        self._hm_next.setIconSize(QSize(18, 18))
        self._hm_next.setObjectName("iconBtn")
        self._hm_next.clicked.connect(self._hm_nav_next)
        nav_row.addWidget(self._hm_next)
        nav_row.addStretch(1)
        self._lay.addLayout(nav_row)

        # 图表 card 容器
        self._lay.addSpacing(8)
        hm_card = card()
        hm_lay = QVBoxLayout(hm_card)
        hm_lay.setContentsMargins(16, 14, 16, 14)
        self._month_heatmap = MonthHeatmap()
        hm_lay.addWidget(self._month_heatmap)
        self._lay.addWidget(hm_card)

    # -------------------------------------------------------------- #
    #  月度数据
    # -------------------------------------------------------------- #
    def _build_monthly_trend_section(self):
        self._mt_year = datetime.date.today().year
        self._mt_month = datetime.date.today().month

        self._lay.addSpacing(12)
        # 使用 section_title 组件
        title_row = QHBoxLayout()
        self._mt_title = QLabel()
        self._mt_title.setStyleSheet(f"font-size:14px; font-weight:600; color:{self._t.text};")
        title_row.addWidget(section_title("月度数据", "chart"))
        title_row.addStretch(1)
        title_row.addWidget(self._mt_title)
        self._lay.addLayout(title_row)

        # 图表 card 容器
        self._lay.addSpacing(8)
        mt_card = card()
        mt_lay = QVBoxLayout(mt_card)
        mt_lay.setContentsMargins(16, 14, 16, 14)
        self._monthly_trend = AreaLineChart()
        mt_lay.addWidget(self._monthly_trend)
        self._lay.addWidget(mt_card)

    # -------------------------------------------------------------- #
    #  打卡分布（起床 / 睡眠 共用构建器）
    # -------------------------------------------------------------- #
    def _build_checkin_section(self, key: str, title: str, checkin_type: int):
        """构建起床或睡眠打卡分布区域。"""
        self._lay.addSpacing(12)
        t = self._t
        today = datetime.date.today()

        # 存储状态
        setattr(self, f"_{key}_year", today.year)
        setattr(self, f"_{key}_month", today.month)
        setattr(self, f"_{key}_type", checkin_type)

        # 使用 section_title 组件
        title_row = QHBoxLayout()
        title_row.addWidget(section_title(title, "chart"))
        self._lay.addLayout(title_row)

        # 导航行
        nav_row = QHBoxLayout()
        nav_row.addStretch(1)
        title_label = QLabel()
        title_label.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        setattr(self, f"_{key}_title", title_label)

        prev_btn = QPushButton()
        prev_btn.setFixedSize(32, 32)
        prev_btn.setIcon(icon("left", t.text_muted, 18))
        prev_btn.setIconSize(QSize(18, 18))
        prev_btn.setObjectName("iconBtn")
        prev_btn.clicked.connect(lambda _, k=key: self._checkin_nav(k, -1))
        nav_row.addWidget(prev_btn)

        nav_row.addWidget(title_label)

        next_btn = QPushButton()
        next_btn.setFixedSize(32, 32)
        next_btn.setIcon(icon("right", t.text_muted, 18))
        next_btn.setIconSize(QSize(18, 18))
        next_btn.setObjectName("iconBtn")
        next_btn.clicked.connect(lambda _, k=key: self._checkin_nav(k, 1))
        nav_row.addWidget(next_btn)
        nav_row.addStretch(1)
        self._lay.addLayout(nav_row)

        # 图表 card 容器
        self._lay.addSpacing(8)
        frame = QFrame()
        frame.setObjectName("card")
        chart_lay = QVBoxLayout(frame)
        chart_lay.setContentsMargins(16, 14, 16, 14)
        chart = BarChart(t.accent2)
        setattr(self, f"_{key}_chart", chart)
        chart_lay.addWidget(chart)
        setattr(self, f"_{key}_frame", frame)
        self._lay.addWidget(frame)

    # -------------------------------------------------------------- #
    #  月度打断原因分布
    # -------------------------------------------------------------- #
    def _build_interrupt_section(self):
        self._lay.addSpacing(12)
        self._int_year = datetime.date.today().year
        self._int_month = datetime.date.today().month

        t = self._t
        # 使用 section_title 组件
        title_row = QHBoxLayout()
        self._int_title = QLabel()
        self._int_title.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        title_row.addWidget(section_title("月度打断原因分布", "chart"))

        # 导航按钮
        self._int_prev = QPushButton()
        self._int_prev.setFixedSize(32, 32)
        self._int_prev.setIcon(icon("left", t.text_muted, 18))
        self._int_prev.setIconSize(QSize(18, 18))
        self._int_prev.setObjectName("iconBtn")
        self._int_prev.clicked.connect(self._int_nav_prev)

        self._int_next = QPushButton()
        self._int_next.setFixedSize(32, 32)
        self._int_next.setIcon(icon("right", t.text_muted, 18))
        self._int_next.setIconSize(QSize(18, 18))
        self._int_next.setObjectName("iconBtn")
        self._int_next.clicked.connect(self._int_nav_next)

        title_row.addStretch(1)
        title_row.addWidget(self._int_prev)
        title_row.addWidget(self._int_title)
        title_row.addWidget(self._int_next)
        self._lay.addLayout(title_row)

        # 图表 card 容器
        self._lay.addSpacing(8)
        self._int_frame = QFrame()
        self._int_frame.setObjectName("card")
        int_lay = QVBoxLayout(self._int_frame)
        int_lay.setContentsMargins(16, 14, 16, 14)
        self._int_pie = PieChart()
        int_lay.addWidget(self._int_pie)
        self._lay.addWidget(self._int_frame)

    # -------------------------------------------------------------- #
    #  年度数据
    # -------------------------------------------------------------- #
    def _build_yearly_section(self):
        self._yearly_year = datetime.date.today().year

        t = self._t
        # 使用 section_title 组件
        title_row = QHBoxLayout()
        self._yearly_title = QLabel()
        self._yearly_title.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        title_row.addWidget(section_title("年度数据", "chart"))

        # 导航按钮
        self._yearly_prev = QPushButton()
        self._yearly_prev.setFixedSize(32, 32)
        self._yearly_prev.setIcon(icon("left", t.text_muted, 18))
        self._yearly_prev.setIconSize(QSize(18, 18))
        self._yearly_prev.setObjectName("iconBtn")
        self._yearly_prev.clicked.connect(self._yearly_nav_prev)

        self._yearly_next = QPushButton()
        self._yearly_next.setFixedSize(32, 32)
        self._yearly_next.setIcon(icon("right", t.text_muted, 18))
        self._yearly_next.setIconSize(QSize(18, 18))
        self._yearly_next.setObjectName("iconBtn")
        self._yearly_next.clicked.connect(self._yearly_nav_next)

        title_row.addStretch(1)
        title_row.addWidget(self._yearly_prev)
        title_row.addWidget(self._yearly_title)
        title_row.addWidget(self._yearly_next)
        self._lay.addLayout(title_row)

        # 图表 card 容器
        self._lay.addSpacing(8)
        y_card = card()
        y_lay = QVBoxLayout(y_card)
        y_lay.setContentsMargins(16, 14, 16, 14)
        self._yearly_chart = AreaLineChart()
        y_lay.addWidget(self._yearly_chart)
        self._lay.addWidget(y_card)

    # ------------------------------------------------------------------ #
    #  导航回调
    # ------------------------------------------------------------------ #
    def _dist_nav_prev(self):
        if self._dist_tab == TAB_DAY:
            self._dist_date -= datetime.timedelta(days=1)
        elif self._dist_tab == TAB_WEEK:
            self._dist_date -= datetime.timedelta(weeks=1)
        elif self._dist_tab == TAB_MONTH:
            if self._dist_date.month == 1:
                self._dist_date = self._dist_date.replace(year=self._dist_date.year - 1, month=12)
            else:
                self._dist_date = self._dist_date.replace(month=self._dist_date.month - 1)
        self.refresh()

    def _dist_nav_next(self):
        if self._dist_tab == TAB_DAY:
            self._dist_date += datetime.timedelta(days=1)
        elif self._dist_tab == TAB_WEEK:
            self._dist_date += datetime.timedelta(weeks=1)
        elif self._dist_tab == TAB_MONTH:
            if self._dist_date.month == 12:
                self._dist_date = self._dist_date.replace(year=self._dist_date.year + 1, month=1)
            else:
                self._dist_date = self._dist_date.replace(month=self._dist_date.month + 1)
        self.refresh()

    def _switch_dist_tab(self, idx):
        self._dist_tab = idx
        self._dist_date = datetime.date.today()
        # 更新按钮样式
        for i, btn in enumerate(self._dist_tab_btns):
            btn.setChecked(i == idx)
        # 自定义模式：显示日期范围选择器，隐藏日期导航
        is_custom = (idx == TAB_CUSTOM)
        self._custom_range_widget.setVisible(is_custom)
        self._dist_prev.setVisible(not is_custom)
        self._dist_next.setVisible(not is_custom)
        if is_custom:
            self._dist_date_label.setText("自定义范围")
            # 强制布局重算，确保自定义日期选择器可见
            self._custom_range_widget.updateGeometry()
            self._lay.invalidate()
        self.refresh()

    def _apply_custom_range(self):
        """应用自定义日期范围。"""
        start = self._custom_start.date().toPyDate()
        end = self._custom_end.date().toPyDate()
        if start > end:
            start, end = end, start
            # 同步QDateEdit控件
            from PyQt6.QtCore import QDate
            self._custom_start.setDate(QDate(start))
            self._custom_end.setDate(QDate(end))
        self._custom_start_date = start
        self._custom_end_date = end
        self._dist_date_label.setText(f"{start.strftime('%m/%d')} - {end.strftime('%m/%d')}")
        self.refresh()

    def _hm_nav_prev(self):
        if self._heatmap_month == 1:
            self._heatmap_year -= 1
            self._heatmap_month = 12
        else:
            self._heatmap_month -= 1
        self.refresh()

    def _hm_nav_next(self):
        if self._heatmap_month == 12:
            self._heatmap_year += 1
            self._heatmap_month = 1
        else:
            self._heatmap_month += 1
        self.refresh()

    def _checkin_nav(self, key, direction):
        cur_year = getattr(self, f"_{key}_year")
        cur_month = getattr(self, f"_{key}_month")
        if direction == -1:
            if cur_month == 1:
                setattr(self, f"_{key}_year", cur_year - 1)
                setattr(self, f"_{key}_month", 12)
            else:
                setattr(self, f"_{key}_month", cur_month - 1)
        else:
            if cur_month == 12:
                setattr(self, f"_{key}_year", cur_year + 1)
                setattr(self, f"_{key}_month", 1)
            else:
                setattr(self, f"_{key}_month", cur_month + 1)
        self.refresh()

    def _int_nav_prev(self):
        if self._int_month == 1:
            self._int_year -= 1
            self._int_month = 12
        else:
            self._int_month -= 1
        self.refresh()

    def _int_nav_next(self):
        if self._int_month == 12:
            self._int_year += 1
            self._int_month = 1
        else:
            self._int_month += 1
        self.refresh()

    def _yearly_nav_prev(self):
        self._yearly_year -= 1
        self.refresh()

    def _yearly_nav_next(self):
        self._yearly_year += 1
        self.refresh()

    # ------------------------------------------------------------------ #
    #  查看专注记录
    # ------------------------------------------------------------------ #
    def _view_focus_records(self):
        """弹出对话框展示最近 50 条专注记录（卡片列表，主题化）。"""
        t = self._t
        records = self.focus_dao.list_recent(50)
        dlg = QDialog(self)
        dlg.setWindowTitle("最近专注记录")
        dlg.setMinimumSize(560, 460)
        dlg.setStyleSheet(
            f"background:{t.surface}; color:{t.text};"
            f"border-radius:{t.radius_lg}px;")
        root = QVBoxLayout(dlg)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel("最近专注记录")
        title.setStyleSheet(f"font-size:18px; font-weight:700; color:{t.text};")
        root.addWidget(title)

        # 可滚动卡片列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")
        list_widget = QWidget()
        list_lay = QVBoxLayout(list_widget)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(10)

        if not records:
            empty = QLabel("暂无专注记录")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{t.text_muted}; font-size:14px; padding:48px 0;")
            list_lay.addWidget(empty)
        else:
            for r in records:
                list_lay.addWidget(self._build_record_card(r, t))
            list_lay.addStretch(1)

        scroll.setWidget(list_widget)
        root.addWidget(scroll, 1)

        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(ghost_button("关闭", on_click=dlg.accept,
                                  icon_name="close"))
        root.addLayout(h)
        dlg.exec()

    def _build_record_card(self, r, t):
        """构建单条专注记录卡片（图标 + 名称/时间 + 时长 + 状态徽章）。"""
        card = QFrame()
        card.setObjectName("panel")
        card.setStyleSheet(
            f"#panel{{background:{t.surface_variant}; border:1px solid {t.border}; "
            f"border-radius:{t.radius_md}px;}}")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        ico = QLabel()
        ico.setPixmap(icon("timer", t.primary, 18).pixmap(30, 30))
        ico.setFixedSize(36, 36)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"background:{t.primary_soft}; border-radius:{t.radius_md}px;")
        lay.addWidget(ico)

        col = QVBoxLayout()
        col.setSpacing(3)
        name = r.get("record_name", "") or "专注"
        lab_name = QLabel(name[:24] + ("…" if len(name) > 24 else ""))
        lab_name.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        lab_date = QLabel(self._fmt_record_time(r.get("start_time")))
        lab_date.setStyleSheet(f"font-size:12px; color:{t.text_muted};")
        col.addWidget(lab_name)
        col.addWidget(lab_date)
        lay.addLayout(col, 1)

        actual = r.get("actual_duration", 0)
        mins = actual // 60
        secs = actual % 60
        lab_dur = QLabel(f"{mins}分{secs}秒")
        lab_dur.setStyleSheet(
            f"color:{t.primary}; font-weight:600; font-size:13px;")
        lab_dur.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lab_dur)

        is_completed = r.get("is_completed", 1)
        status_text = "已完成" if is_completed else "未完成"
        status_color = t.success if is_completed else t.warning
        lab_status = QLabel(status_text)
        lab_status.setStyleSheet(
            f"background:{status_color}; color:#fff; border-radius:999px; "
            f"padding:3px 10px; font-size:11px; font-weight:600;")
        lay.addWidget(lab_status)
        return card

    @staticmethod
    def _fmt_record_time(start):
        """将 start_time 统一格式化为 'YYYY-MM-DD HH:MM'。"""
        if not start:
            return ""
        if isinstance(start, datetime.datetime):
            return start.strftime("%Y-%m-%d %H:%M")
        try:
            return datetime.datetime.fromisoformat(str(start)).strftime(
                "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return str(start)[:16]

    # ------------------------------------------------------------------ #
    #  设置
    # ------------------------------------------------------------------ #
    def _load_settings(self):
        """从 settings 表加载统计设置。"""
        try:
            self._show_wake = self.settings_dao.get("stats_show_wake", "1") == "1"
            self._show_sleep = self.settings_dao.get("stats_show_sleep", "1") == "1"
            self._show_interrupt = self.settings_dao.get("stats_show_interrupt", "1") == "1"
            self._trend_smooth = self.settings_dao.get("stats_trend_smooth", "1") == "1"
            self._chart_unit = self.settings_dao.get("stats_chart_unit", "minute")
            self._monthly_range = self.settings_dao.get("stats_monthly_range", "month")
        except Exception:
            self._show_wake = True
            self._show_sleep = True
            self._show_interrupt = True
            self._trend_smooth = True
            self._chart_unit = "minute"
            self._monthly_range = "month"

    def _save_setting(self, key, value):
        self.settings_dao.set(key, value)

    def _open_settings(self):
        """弹出统计设置对话框。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("数据统计设置")
        dlg.setFixedSize(400, 360)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {self._t.surface};
                color: {self._t.text};
                border-radius: {self._t.radius_lg}px;
            }}
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # 标题
        title = QLabel("数据统计设置")
        title.setStyleSheet(f"font-size:18px; font-weight:700; color:{self._t.text};")
        lay.addWidget(title)

        # 起床打卡分布显示开关
        cb_wake = QCheckBox("显示起床打卡分布")
        cb_wake.setChecked(self._show_wake)
        cb_wake.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        lay.addWidget(cb_wake)

        # 睡眠打卡分布显示开关
        cb_sleep = QCheckBox("显示睡眠打卡分布")
        cb_sleep.setChecked(self._show_sleep)
        cb_sleep.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        lay.addWidget(cb_sleep)

        # 月度打断原因分布显示开关
        cb_interrupt = QCheckBox("显示月度打断原因分布")
        cb_interrupt.setChecked(self._show_interrupt)
        cb_interrupt.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        lay.addWidget(cb_interrupt)

        # 专注泡泡（Windows 不实现，保留开关）
        cb_bubble = QCheckBox("专注泡泡功能（Windows 暂不可用）")
        cb_bubble.setChecked(False)
        cb_bubble.setEnabled(False)
        cb_bubble.setStyleSheet(f"color:{self._t.text_subtle}; font-size:14px;")
        lay.addWidget(cb_bubble)

        # 趋势图线条
        row_line = QHBoxLayout()
        row_line.setSpacing(12)
        lbl_line = QLabel("趋势图线条：")
        lbl_line.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        row_line.addWidget(lbl_line)
        combo_line = QComboBox()
        combo_line.addItem("曲线", "curve")
        combo_line.addItem("直线", "line")
        combo_line.setCurrentIndex(0 if self._trend_smooth else 1)
        combo_line.setFixedWidth(120)
        row_line.addWidget(combo_line)
        row_line.addStretch(1)
        lay.addLayout(row_line)

        # 统计图单位
        row_unit = QHBoxLayout()
        row_unit.setSpacing(12)
        lbl_unit = QLabel("统计图单位：")
        lbl_unit.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        row_unit.addWidget(lbl_unit)
        combo_unit = QComboBox()
        combo_unit.addItem("分钟", "minute")
        combo_unit.addItem("小时", "hour")
        combo_unit.setCurrentIndex(0 if self._chart_unit == "minute" else 1)
        combo_unit.setFixedWidth(120)
        row_unit.addWidget(combo_unit)
        row_unit.addStretch(1)
        lay.addLayout(row_unit)

        # 月度数据展示范围
        row_range = QHBoxLayout()
        row_range.setSpacing(12)
        lbl_range = QLabel("月度数据展示范围：")
        lbl_range.setStyleSheet(f"color:{self._t.text}; font-size:14px;")
        row_range.addWidget(lbl_range)
        combo_range = QComboBox()
        combo_range.addItem("7天", "7days")
        combo_range.addItem("整月", "month")
        combo_range.setCurrentIndex(0 if self._monthly_range == "7days" else 1)
        combo_range.setFixedWidth(120)
        row_range.addWidget(combo_range)
        row_range.addStretch(1)
        lay.addLayout(row_range)

        lay.addStretch(1)

        # 确定按钮
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("primary")
        btn_ok.setFixedHeight(38)

        def _on_ok():
            self._show_wake = cb_wake.isChecked()
            self._show_sleep = cb_sleep.isChecked()
            self._show_interrupt = cb_interrupt.isChecked()
            self._trend_smooth = combo_line.currentData() == "curve"
            self._chart_unit = combo_unit.currentData()
            self._monthly_range = combo_range.currentData()
            # 持久化
            self._save_setting("stats_show_wake", "1" if self._show_wake else "0")
            self._save_setting("stats_show_sleep", "1" if self._show_sleep else "0")
            self._save_setting("stats_show_interrupt", "1" if self._show_interrupt else "0")
            self._save_setting("stats_trend_smooth", "1" if self._trend_smooth else "0")
            self._save_setting("stats_chart_unit", self._chart_unit)
            self._save_setting("stats_monthly_range", self._monthly_range)
            dlg.accept()
            self.refresh()

        btn_ok.clicked.connect(_on_ok)
        lay.addWidget(btn_ok)

        dlg.exec()

    # ------------------------------------------------------------------ #
    #  刷新数据
    # ------------------------------------------------------------------ #
    def refresh(self):
        t = self._t
        self._refresh_overview()
        self._refresh_distribution()
        self._refresh_monthly_heatmap()
        self._refresh_monthly_trend()
        self._refresh_checkin("wake")
        self._refresh_checkin("sleep")
        self._refresh_interrupt()
        self._refresh_yearly()
        self._apply_visibility()

    def _apply_visibility(self):
        """根据设置控制打卡/打断区域可见性。"""
        if hasattr(self, "_wake_frame"):
            self._wake_frame.setVisible(self._show_wake)
        if hasattr(self, "_sleep_frame"):
            self._sleep_frame.setVisible(self._show_sleep)
        if hasattr(self, "_int_frame"):
            self._int_frame.setVisible(self._show_interrupt)

    # ---------- 概览卡片 ---------- #
    def _refresh_overview(self):
        t = self._t
        total = self.stats.total_focus()
        today = self.stats.today_focus()
        avg_sec = self.stats.avg_daily_duration()
        abandoned = self.stats.today_abandoned()

        self.card_total_count.set_value(f"{total['count']} 次")
        self.card_total_duration.set_value(fmt_minutes(total["total_seconds"]))
        self.card_avg_daily.set_value(fmt_minutes(avg_sec))
        self.card_today_count.set_value(f"{today['count']} 次")
        self.card_today_duration.set_value(fmt_minutes(today["total_seconds"]))
        self.card_today_abandoned.set_value(f"{abandoned} 次")

    # ---------- 专注时长分布 ---------- #
    def _refresh_distribution(self):
        t = self._t
        tab = self._dist_tab
        d = self._dist_date

        # 更新日期标签
        if tab == TAB_DAY:
            self._dist_date_label.setText(d.strftime("%Y-%m-%d"))
            # 日视图：按小时分布
            hours = self.stats.hourly_range(d)
            items = [{"label": f"{h:02d}", "value": int(r["total"])} for h, r in
                     [(i, next((x for x in hours if int(x["hour"]) == i), {"total": 0}))
                      for i in range(24)]]
            self._dist_chart.set_data(items, t.primary)
            pie_data = self.stats.todo_distribution(d, d)
            self._dist_pie.set_data([{"name": r["name"], "value": int(r["total"])} for r in pie_data])

        elif tab == TAB_WEEK:
            # 使用 _dist_date 所在周
            monday = d - datetime.timedelta(days=d.weekday())
            sunday = monday + datetime.timedelta(days=6)
            self._dist_date_label.setText(f"{monday.strftime('%m/%d')} - {sunday.strftime('%m/%d')}")
            rows = self.stats.daily_range(monday, sunday)
            items = [{"label": _md(r["belong_date"]), "value": int(r["total"])} for r in rows]
            self._dist_chart.set_data(items, t.primary)
            pie_data = self.stats.todo_distribution(monday, sunday)
            self._dist_pie.set_data([{"name": r["name"], "value": int(r["total"])} for r in pie_data])

        elif tab == TAB_MONTH:
            y, m = d.year, d.month
            self._dist_date_label.setText(f"{y}-{m:02d}")
            first, last = _month_range(y, m)
            rows = self.stats.daily_range(first, last)
            items = [{"label": _md(r["belong_date"]), "value": int(r["total"])} for r in rows]
            self._dist_chart.set_data(items, t.primary)
            pie_data = self.stats.todo_distribution(first, last)
            self._dist_pie.set_data([{"name": r["name"], "value": int(r["total"])} for r in pie_data])

        elif tab == TAB_CUSTOM:
            # 自定义日期范围
            start = getattr(self, "_custom_start_date", None)
            end = getattr(self, "_custom_end_date", None)
            if start is None or end is None:
                start = datetime.date.today() - datetime.timedelta(days=7)
                end = datetime.date.today()
            self._dist_date_label.setText(f"{start.strftime('%m/%d')} - {end.strftime('%m/%d')}")
            rows = self.stats.daily_range(start, end)
            items = [{"label": _md(r["belong_date"]), "value": int(r["total"])} for r in rows]
            self._dist_chart.set_data(items, t.primary)
            pie_data = self.stats.todo_distribution(start, end)
            self._dist_pie.set_data([{"name": r["name"], "value": int(r["total"])} for r in pie_data])

        # 更新 Tab 按钮样式（选中态 primary，未选中态 surface_variant）
        total = len(self._dist_tab_btns)
        for i, btn in enumerate(self._dist_tab_btns):
            if i == tab:
                btn.setStyleSheet(
                    f"QPushButton{{background:{t.primary}; color:{t.on_primary}; "
                    f"border:none; border-radius:8px; font-weight:600; font-size:13px; padding:0 14px;}}"
                    f"QPushButton:hover{{background:{t.primary_hover};}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:{t.surface_variant}; color:{t.text_muted}; "
                    f"border:none; border-radius:8px; font-size:13px; padding:0 14px;}}"
                    f"QPushButton:hover{{background:{t.surface}; color:{t.text};}}")

    # ---------- 本月专注时段分布 ---------- #
    def _refresh_monthly_heatmap(self):
        y, m = self._heatmap_year, self._heatmap_month
        self._hm_title.setText(f"本月专注时段分布  {y}-{m:02d}")
        ym = f"{y}-{m:02d}"
        rows = self.stats.monthly_hour_heatmap(ym)
        dim = _days_in_month(y, m)
        self._month_heatmap.set_data(rows, dim)

    # ---------- 月度数据 ---------- #
    def _refresh_monthly_trend(self):
        y, m = self._mt_year, self._mt_month
        self._mt_title.setText(f"月度数据  {y}-{m:02d}")
        first, last = _month_range(y, m)
        rows = self.stats.daily_range(first, last)

        # 根据 monthly_range 设置决定展示范围
        if self._monthly_range == "7days":
            today = datetime.date.today()
            start = today - datetime.timedelta(days=6)
            rows = [r for r in rows if _to_date(r["belong_date"]) >= start]

        series = [int(r["total"]) for r in rows]
        labels = [_md(r["belong_date"]) for r in rows]
        self._monthly_trend.set_data(
            series, labels,
            accent=self._t.primary,
            smooth=self._trend_smooth,
            unit=self._chart_unit,
        )

    # ---------- 打卡分布 ---------- #
    def _refresh_checkin(self, key):
        y = getattr(self, f"_{key}_year")
        m = getattr(self, f"_{key}_month")
        ct = getattr(self, f"_{key}_type")
        title_label = getattr(self, f"_{key}_title")
        chart = getattr(self, f"_{key}_chart")

        title_label.setText(f"{'起床' if ct == 0 else '睡眠'}打卡分布  {y}-{m:02d}")
        ym = f"{y}-{m:02d}"
        rows = self.checkin_dao.monthly_distribution(ym, ct)
        items = [{"label": f"{r['hour']:02d}时", "value": int(r["cnt"])} for r in rows]
        chart.set_data(items, self._t.accent2)

    # ---------- 月度打断原因分布 ---------- #
    def _refresh_interrupt(self):
        y, m = self._int_year, self._int_month
        self._int_title.setText(f"月度打断原因分布  {y}-{m:02d}")
        ym = f"{y}-{m:02d}"
        rows = self.interrupt_dao.monthly_distribution(ym)
        items = [{"name": r["process_name"], "value": int(r["cnt"])} for r in rows]
        self._int_pie.set_data(items)

    # ---------- 年度数据 ---------- #
    def _refresh_yearly(self):
        y = self._yearly_year
        self._yearly_title.setText(f"年度数据  {y}")
        rows = self.stats.yearly_monthly(y)
        # 构造 12 个月的数据
        month_map = {int(r["month"]): int(r["total"]) for r in rows}
        series = [month_map.get(i, 0) for i in range(1, 13)]
        labels = [f"{i}月" for i in range(1, 13)]
        self._yearly_chart.set_data(
            series, labels,
            accent=self._t.accent2,
            smooth=self._trend_smooth,
            unit=self._chart_unit,
        )