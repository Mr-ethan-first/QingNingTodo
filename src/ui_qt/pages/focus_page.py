"""专注计时页面（PyQt6 / QTimer 驱动）。

支持循环计时、倒计时自动转正计时、暂停超时自动放弃、自定义格言、
休息前询问、自定义休息时长、打断详情记录等功能。
"""
import datetime
import os
import shutil
import sys
import time

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from src.audio_player import get_player
from src.theme import get_current_theme, _on_color, hex_rgba
from src.ui_qt.icons import icon
from src.ui_qt.pages import PageBase
from src.ui_qt.toast import show_toast
from src.ui_qt.widgets import CircularTimer, hero_banner

TIMER_TYPES = {0: "普通番茄钟", 1: "正计时", 2: "倒计时", 3: "严格模式"}
HABIT_TIMER_TYPES = {0: "倒计时", 1: "正计时", 2: "不计时"}
IDLE, RUNNING, PAUSED, RESTING, STOPWATCH = "idle", "running", "paused", "resting", "stopwatch"


class FocusPage(PageBase):
    def __init__(self, state):
        self.focus_dao = state.focus_record_dao
        self.interrupt_dao = state.interrupt_detail_dao
        self.ach_dao = state.achievement_dao
        self.noise_dao = state.white_noise_dao
        self.todo_dao = state.todo_dao
        self.settings_dao = state.settings_dao
        self.fstate = IDLE
        self.current_todo = None
        self.remaining = 0
        self.elapsed = 0
        self.planned = 1500
        self.start_time = None
        self.timer_type = 0
        self.noise_player = get_player()
        # 循环计时相关
        self.current_loop = 1  # 当前轮次（1-based）
        self.total_loops = 1   # 总轮次
        # 暂停超时相关
        self._pause_start: datetime.datetime | None = None
        # 自动转正计时已保存记录标记（避免重复保存）
        self._stopwatch_record_saved = False
        # 学霸模式：进程监控器与违规记录
        self._guard = None
        self._guard_violations = []
        # 离开提醒去重标记：同一次离开只提醒一次，回到专注后重置
        self._guard_notified = False
        # super().__init__ 必须先于 QTimer(self) 调用（PyQt 规则）
        super().__init__(state)
        # 订阅背景海报变更，设置页修改 app_background 后即时刷新
        state.subscribe_background(self._on_background_changed)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.setInterval(1000)

    # ---------- 设置读取辅助 ----------

    def _get_setting(self, key: str, default: str = "") -> str:
        """从 settings 表读取配置，异常时返回默认值。"""
        try:
            val = self.settings_dao.get(key, default) or default
            return str(val)
        except Exception:
            return default

    def _random_motto(self) -> str:
        """从内置1000句诗文中随机选取一句（最长31字，单行展示）。"""
        try:
            from src.data.mottos import MOTTOS
            import random
            # 筛选不超过31字的格言，确保单行完整展示
            short_mottos = [m for m in MOTTOS if len(m) <= 31]
            if short_mottos:
                return random.choice(short_mottos)
            return random.choice(MOTTOS)
        except Exception:
            return "专注是成功的基石"

    def _effective_motto(self) -> str:
        """优先使用用户在设置中自定义的番茄钟格言，未设置则随机。"""
        val = (self._get_setting("focus_motto", "") or "").strip()
        return val or self._random_motto()

    def _refresh_motto(self):
        """刷新格言显示（每次开始专注时调用）。"""
        if hasattr(self, 'lbl_motto'):
            self.lbl_motto.setText(self._effective_motto())

    def _refresh_hero_subtitle(self):
        """刷新顶部横幅副标题为随机诗文（每次开始专注时调用）。"""
        if hasattr(self, '_hero') and self._hero is not None:
            # 找到 hero banner 中的副标题 QLabel
            subtitle = self._hero.findChild(QLabel, "heroSubtitle")
            if subtitle:
                subtitle.setText(self._random_motto())

    def _get_effective_break_duration(self) -> int:
        """获取有效休息时长：优先使用待办自定义，其次全局设置。"""
        if self.current_todo and self.current_todo.get("custom_break_duration"):
            return int(self.current_todo["custom_break_duration"])
        return int(self._get_setting("default_break_duration", "300"))

    # ---------- 构建界面 ----------

    def _build(self):
        t = self._t
        # 整页背景层：图在最底、遮罩居中、内容在最上（须先于内容控件创建）。
        # 直接挂在 viewport 上并按视口几何铺满，避免内容(_inner)比视口矮时
        # 背景只覆盖内容区、四周露出默认底色。
        vp = self.viewport()
        self._bg_mask = QWidget(vp)
        self._bg_mask.setObjectName("focusBgMask")
        self._bg_mask.lower()
        # 创建即隐藏：避免几何尚未同步（默认尺寸）时先以错误大小闪现一帧，
        # 是否显示统一交由 _apply_focus_background 决定。
        self._bg_mask.hide()
        self._bg_label = QLabel(vp)
        self._bg_label.setObjectName("focusBg")
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.lower()
        self._bg_label.hide()
        # _inner 透明：背景层在 _inner 之下，透明后图片（及玻璃态卡片/横幅）
        # 才能透出；无背景时退化为视口默认底色，外观不变。
        self._inner.setStyleSheet("background:transparent;")
        # 专注页顶部横幅：标题固定，副标题使用随机诗文（每次进入页面随机）
        self._hero_subtitle = self._random_motto()
        self._hero = hero_banner("专注当下", self._hero_subtitle)
        self._lay.addWidget(self._hero)

        self.lbl_task = QLabel("请选择待办开始专注")
        self.lbl_task.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_task.setStyleSheet(
            f"font-size:20px; font-weight:700; color:{t.text};")

        # 循环轮次标签（计时器上方）
        self.lbl_loop = QLabel("")
        self.lbl_loop.setStyleSheet(
            f"font-size:14px; font-weight:600; color:{t.primary};")
        self.lbl_loop.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_state = QLabel("空闲")
        self.lbl_state.setStyleSheet(f"font-size:14px; color:{t.text_muted};")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_timer = CircularTimer()
        self.lbl_timer.set_text("25:00")

        # 格言标签（优先使用用户在设置中自定义的番茄钟格言）
        # 单行展示，最长31字，宽度放宽
        motto = self._effective_motto()
        self.lbl_motto = QLabel(motto)
        self.lbl_motto.setStyleSheet(
            f"font-size:15px; color:{t.text_muted}; font-style:italic; "
            f"padding:0 12px;")
        self.lbl_motto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_motto.setWordWrap(False)
        self.lbl_motto.setMaximumWidth(600)
        self.lbl_motto.setMinimumHeight(24)

        # 自动转正计时提示标签
        self.lbl_stopwatch_hint = QLabel("")
        self.lbl_stopwatch_hint.setStyleSheet(
            f"font-size:12px; color:{t.primary}; font-style:italic;")
        self.lbl_stopwatch_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_stopwatch_hint.setVisible(False)

        # 操作按钮：统一「胶囊图标按钮」，按语义色区分，选中/激活态高亮填充
        # 开始=主色，暂停=警告色，完成=成功色，放弃=危险色，白噪音=主色
        self.btn_start = QPushButton("开始")
        self.btn_start.setProperty("accent", "primary")
        self.btn_start.setProperty("fill", True)  # 主操作：默认即填充高亮
        self.btn_start.clicked.connect(self._on_start)

        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setProperty("accent", "warning")
        self.btn_pause.clicked.connect(self._on_pause)

        self.btn_finish = QPushButton("提取完成")
        self.btn_finish.setProperty("accent", "success")
        self.btn_finish.clicked.connect(self._on_finish)

        self.btn_giveup = QPushButton("放弃")
        self.btn_giveup.setProperty("accent", "danger")
        self.btn_giveup.clicked.connect(self._on_giveup)

        # 白噪音按钮：文字 + 图标，选中（正在播放）时高亮填充，与其它按钮统一
        self.btn_music = QPushButton("白噪音")
        self.btn_music.setProperty("accent", "primary")
        self.btn_music.setCheckable(True)
        self.btn_music.setToolTip("白噪音设置")
        self.btn_music.clicked.connect(self._open_noise_dialog)

        for _b, _icon in (
            (self.btn_start, "play"), (self.btn_pause, "pause"),
            (self.btn_finish, "check"), (self.btn_giveup, "stop"),
            (self.btn_music, "music"),
        ):
            _b.setProperty("iconName", _icon)
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
            _b.setMinimumHeight(40)
            _b.setMinimumWidth(96)
        self._style_action_buttons()
        self._update_music_button()

        # 面板卡片（计时器 + 白噪音在同一个 card 容器中）
        panel = self._focus_card = QFrame()
        panel.setObjectName("card")

        pl = QVBoxLayout(panel)
        pl.setContentsMargins(28, 28, 28, 28)
        pl.setSpacing(12)

        # 循环轮次标签在计时器上方
        pl.addWidget(self.lbl_loop, alignment=Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.lbl_task, alignment=Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.lbl_state, alignment=Qt.AlignmentFlag.AlignCenter)
        pl.addSpacing(8)
        pl.addWidget(self.lbl_timer, alignment=Qt.AlignmentFlag.AlignCenter)
        # 格言：margin-top:16
        pl.addSpacing(16)
        pl.addWidget(self.lbl_stopwatch_hint,
                      alignment=Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.lbl_motto, alignment=Qt.AlignmentFlag.AlignCenter)

        # 白噪音：内嵌铺开的面板已移除，仅保留音乐按钮入口
        # （点击 btn_music 打开白噪音弹窗），计时区更紧凑。
        # 以下属性保留供白噪音逻辑/测试复用，无 UI 副作用。
        self._noise_tabs = {}
        self._noise_tab_btns = []
        self._noise_btns = {}
        self._noise_btn_refs = {}
        self._current_noise_id = None
        self._current_noise_category = None

        # 分割线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{t.border};")
        pl.addWidget(sep)

        # 操作按钮（主/次视觉层级，spacing=12）
        pl.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_finish)
        btn_row.addWidget(self.btn_giveup)
        btn_row.addWidget(self.btn_music)
        btn_row.addStretch(1)
        pl.addLayout(btn_row)

        self._lay.addWidget(panel)
        self._update_buttons()
        self._update_loop_label()
        # 应用背景海报（待办级优先，否则全局）
        try:
            self._apply_focus_background(self._resolve_focus_background())
            # 延迟到布局完成后再同步一次，确保首次显示时几何/缩放正确
            QTimer.singleShot(0, self._sync_bg)
        except (RuntimeError, AttributeError):
            pass

    def _rebuild(self):
        """主题切换时重建界面并恢复运行时状态。"""
        # 整页背景层不在 _lay 中，重建时不会被自动清理，需先移除旧层。
        # 注意：不能调用 setParent(None)——那会让子控件瞬间变成独立顶层窗口，
        # 在 deleteLater 真正销毁前，Qt 可能已将其显示到屏幕左上角，
        # 造成初始化 / 主题切换时“浮动小窗口频繁闪烁”。
        # 正确做法：先 hide() 保持在原父级下，再 deleteLater() 异步销毁。
        for w in (getattr(self, "_bg_label", None), getattr(self, "_bg_mask", None)):
            if w is not None:
                w.hide()
                w.deleteLater()
        self._bg_label = None
        self._bg_mask = None
        super()._rebuild()
        self._restore_display()

    # ---------- 背景海报 ----------
    def _resolve_bg_path(self, path: str) -> str:
        """解析背景图路径，兼容绝对路径与项目相对路径。"""
        if not path:
            return ""
        path = path.strip()
        if os.path.isabs(path) and os.path.isfile(path):
            return path
        # 尝试相对路径（相对于项目根目录）
        base = getattr(sys, '_MEIPASS', None)
        if base:
            project_root = base
        else:
            # focus_page.py 位于 src/ui_qt/pages/，向上 4 层到项目根
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))))
        abs_path = os.path.join(project_root, path)
        if os.path.isfile(abs_path):
            return abs_path
        # 兼容：若原路径直接存在也尝试
        if os.path.isfile(path):
            return path
        return ""

    def _resolve_focus_background(self) -> str:
        """解析专注页背景图路径：待办级 background_path 优先，否则全局 app_background。"""
        if self.current_todo:
            bp = (self.current_todo.get("background_path") or "").strip()
            if bp:
                resolved = self._resolve_bg_path(bp)
                if resolved:
                    return resolved
        return (self._get_setting("app_background", "") or "").strip()

    def _apply_todo_background(self):
        """切换待办时调用：如果有 background_path 就设置页面背景。

        优先使用待办级 background_path，其次回退到全局 app_background。
        """
        try:
            self._apply_focus_background(self._resolve_focus_background())
        except (RuntimeError, AttributeError):
            # 页面控件尚未初始化（纯逻辑测试场景）时安全跳过
            pass

    def _apply_focus_background(self, path: str):
        """将图片作为专注页整页背景（铺满 + 半透明遮罩 + 玻璃态内容）。

        - 有合法图片：整页铺满、加半透明遮罩压暗、卡片/横幅转玻璃态；
        - 无图片：清除背景，恢复默认卡片/横幅样式。
        """
        if not hasattr(self, "_bg_label") or not hasattr(self, "_focus_card"):
            return
        t = get_current_theme()
        self._bg_pixmap = None
        # 计算 hero 文字颜色：保证在任意背景上清晰可读
        if path and os.path.isfile(path):
            # 玻璃态：深色主题用亮字，浅色主题用深色字（避免白底白字看不清）
            title_color = "#FFFFFF" if t.name == "dark" else "#1E252B"
        else:
            # 主色渐变背景：暗色主题强制白色，亮色主题按主色亮度自适应
            title_color = "#FFFFFF" if t.name == "dark" else _on_color(t.primary)
        self._set_hero_text_color(title_color)

        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self._bg_pixmap = pix
                self._bg_label.setVisible(True)
                # 整页半透明遮罩：压暗背景图，保证任意图上文字可读
                mask_alpha = 95 if t.name == "dark" else 120
                from PyQt6.QtGui import QPalette
                pal = self._bg_mask.palette()
                pal.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, mask_alpha))
                self._bg_mask.setAutoFillBackground(True)
                self._bg_mask.setPalette(pal)
                self._bg_mask.setVisible(True)
                # 玻璃态：半透明，露出背景图
                glass = ("rgba(255,255,255,0.16)" if t.name == "dark"
                         else "rgba(255,255,255,0.55)")
                self._focus_card.setStyleSheet(
                    f"#card{{background:{glass}; border:1px solid {t.border};"
                    f"border-radius:{t.radius_lg}px;}}")
                self._hero.setStyleSheet(
                    f"#heroBanner{{background:{glass}; border:1px solid {t.border};"
                    f"border-radius:{t.radius_lg}px;}}")
                if hasattr(self, "_noise_container"):
                    self._noise_container.setStyleSheet(
                        f"#panel{{background:{glass}; border:1px solid {t.border};"
                        f"border-radius:{t.radius_md}px;}}")
                # 延迟同步：本函数常在 load_todo/refresh 中同步调用，
                # 此时视口几何尚未重算，直接 _sync_bg 会因 rect 为 0 提前返回。
                QTimer.singleShot(0, self._sync_bg)
                return
        # 无背景：恢复默认卡片/横幅（与待办清单 hero_banner 保持一致）
        self._bg_label.setVisible(False)
        self._bg_mask.setVisible(False)
        self._focus_card.setStyleSheet(
            f"#card{{background:{t.surface}; border:1px solid {t.border};"
            f"border-radius:{t.radius_lg}px;}}")
        if t.name == "dark":
            # 暗色主题：多段渐变（primary → secondary → accent），与待办清单一致
            hero_grad = (
                f"qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {hex_rgba(t.primary, 0.85)},"
                f"stop:0.5 {hex_rgba(t.secondary, 0.70)},"
                f"stop:1 {hex_rgba(t.accent, 0.85)})")
        else:
            hero_grad = (
                f"qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {t.primary}, stop:0.5 {t.primary_hover},"
                f"stop:1 {t.accent})")
        self._hero.setStyleSheet(
            f"#heroBanner{{ background:{hero_grad};"
            f" border:none; border-radius:{t.radius_lg}px; }}")

    def _set_hero_text_color(self, color: str):
        """按背景明暗设置 hero 标题 / 副标题文字颜色，保证可读性。"""
        title = self._hero.findChild(QLabel, "heroTitle")
        sub = self._hero.findChild(QLabel, "heroSubtitle")
        if title:
            title.setStyleSheet(
                f"color:{color}; font-size:22px; font-weight:700;")
        if sub:
            sub.setStyleSheet(
                f"color:{color}; font-size:13px; opacity:0.9;")
        if hasattr(self, "_noise_container"):
            self._noise_container.setStyleSheet("")

    def _sync_bg(self):
        """将背景层与遮罩层几何同步到视口，并按视口尺寸缩放图片铺满（居中裁剪）。"""
        if not hasattr(self, "_bg_label") or not hasattr(self, "_inner"):
            return
        vp = self.viewport()
        if vp is None:
            return
        rect = vp.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._bg_label.setGeometry(rect)
        self._bg_mask.setGeometry(rect)
        pix = getattr(self, "_bg_pixmap", None)
        if pix is not None and not pix.isNull():
            scaled = pix.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self._bg_label.setPixmap(scaled)

    def showEvent(self, ev):
        """页面首次/每次显示时，待布局几何就绪后再同步背景图。"""
        super().showEvent(ev)
        # 延迟到下一事件循环：此时视口尺寸已稳定，避免首屏空白默认背景
        QTimer.singleShot(0, self._sync_bg)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._sync_bg()

    def _on_theme(self, theme):
        """专注页换肤：重建后重新应用背景海报（遮罩色需随主题更新）。"""
        try:
            super()._on_theme(theme)
            # P0 修复: 主题切换后重新生成操作按钮样式, 避免颜色残留
            self._style_action_buttons()
            self._apply_focus_background(self._resolve_focus_background())
        except (RuntimeError, AttributeError):
            pass

    def _on_background_changed(self):
        """设置页修改背景海报后即时刷新专注页背景。"""
        try:
            self._apply_focus_background(self._resolve_focus_background())
        except (RuntimeError, AttributeError):
            pass

    def _restore_display(self):
        """主题切换后恢复当前运行时状态到新控件上。"""
        if self.current_todo:
            self.lbl_task.setText(self.current_todo["title"])
            if self.fstate == IDLE:
                todo_type = self.current_todo.get("type", 0)
                if todo_type == 1 and self.timer_type == 2:
                    self.lbl_state.setText("就绪 · 不计时")
                elif todo_type == 1:
                    self.lbl_state.setText(
                        f"就绪 · {HABIT_TIMER_TYPES.get(self.timer_type, '未知')}")
                else:
                    self.lbl_state.setText(
                        f"就绪 · {TIMER_TYPES.get(self.timer_type, '未知')}")
            else:
                self.lbl_state.setText(
                    "专注中…" if self.fstate == RUNNING else
                    "已暂停" if self.fstate == PAUSED else
                    "休息一下" if self.fstate == RESTING else
                    "正计时中…" if self.fstate == STOPWATCH else "空闲")
        # 恢复计时器显示
        if self.remaining > 0:
            self._render(self.remaining)
        elif self.elapsed > 0:
            self._render(self.elapsed)
        # 恢复按钮状态
        self._update_buttons()
        # 恢复循环轮次
        self._update_loop_label()
        # 恢复正计时提示
        if self.fstate == STOPWATCH:
            self.lbl_stopwatch_hint.setVisible(True)
            self.lbl_stopwatch_hint.setText("已自动转正计时")

    def _noises(self):
        try:
            return self.noise_dao.list()
        except Exception:
            return []

    # ---------- 加载待办 ----------

    def load_todo(self, todo: dict):
        if self.fstate in (RUNNING, PAUSED, STOPWATCH):
            return
        self.current_todo = todo
        self.planned = todo["duration"]
        self.timer_type = todo["timer_type"]
        self.total_loops = max(1, int(todo.get("loop_count", 1) or 1))
        self.current_loop = 1
        self.lbl_task.setText(todo["title"])
        self._stopwatch_record_saved = False
        self._pause_start = None
        self.lbl_stopwatch_hint.setVisible(False)
        if self.timer_type == 1:
            # 正计时模式
            self.elapsed = 0
            self.lbl_timer.set_text("00:00")
        elif self.timer_type == 2:
            # 不计时模式（养习惯）
            self.elapsed = 0
            self.remaining = 0
            self.lbl_timer.set_text("00:00")
        else:
            self.remaining = self.planned
            self._render(self.remaining)
        self.fstate = IDLE
        # 显示就绪状态
        todo_type = todo.get("type", 0)
        if todo_type == 1 and self.timer_type == 2:
            self.lbl_state.setText("就绪 · 不计时")
        elif todo_type == 1:
            self.lbl_state.setText(f"就绪 · {HABIT_TIMER_TYPES.get(self.timer_type, '未知')}")
        else:
            self.lbl_state.setText(f"就绪 · {TIMER_TYPES.get(self.timer_type, '未知')}")
        self._update_buttons()
        self._update_loop_label()
        # 待办加载后刷新背景海报（待办级优先于全局）
        self._apply_todo_background()

    # ---------- 轮次显示 ----------

    def _update_loop_label(self):
        """更新循环轮次标签。"""
        if self.total_loops > 1:
            self.lbl_loop.setText(f"第 {self.current_loop}/{self.total_loops} 轮")
            self.lbl_loop.setVisible(True)
        else:
            self.lbl_loop.setText("")
            self.lbl_loop.setVisible(False)

    # ---------- 开始 ----------

    def _on_start(self):
        if self.fstate == RESTING:
            self._end_rest()
            return  # 休息结束后由 _end_rest 内部逻辑控制后续流程
        if self.current_todo is None:
            self._pick_todo()
            return
        if self.timer_type == 1 or self.timer_type == 2:
            # 正计时 / 不计时模式：不设置 remaining 倒计时
            self.elapsed = 0
        else:
            self.remaining = self.planned
        self._stopwatch_record_saved = False
        self._pause_start = None
        self.lbl_stopwatch_hint.setVisible(False)
        self._start()

    def _start(self):
        if self._timer.isActive():
            self._timer.stop()
        self.start_time = datetime.datetime.now()
        # 不计时模式(timer_type==2)和正计时模式(timer_type==1)都走正计时
        if self.timer_type == 2:
            self.fstate = STOPWATCH
        else:
            self.fstate = RUNNING
        self.lbl_state.setText("专注中…")
        self._update_buttons()
        self._timer.start()
        # 刷新格言（下方标签 + 顶部横幅副标题均随机更新）
        self._refresh_motto()
        self._refresh_hero_subtitle()
        # 计时开始自动播放白噪音（开启背景音 或 计时开始自动播放 任一开启即播放）
        if (self._get_setting("auto_play_on_start", "false") == "true" or
                self._get_setting("bg_music_enabled", "false") == "true"):
            self._auto_play_noise()
        # 学霸模式：启动前台进程监控
        self._start_guard()

    def _auto_play_noise(self):
        """计时开始时自动播放白噪音。

        优先播放上次选中的音源（last_noise_id）；若从未显式选过但已开启背景音，
        则默认取列表中第一条可用音源，确保「开启白噪音」配置真正生效。
        """
        try:
            last_id = int(self._get_setting("last_noise_id", "0") or "0")
            noises = self._noises()
            target = None
            if last_id > 0:
                for n in noises:
                    if n["id"] == last_id and n.get("file_path"):
                        target = n
                        break
            # 未显式选择音源但开启了背景音：默认取第一条可用音源
            if target is None:
                for n in noises:
                    if n.get("file_path"):
                        target = n
                        break
            if target is not None:
                path = target.get("file_path", "")
                if path and self.noise_player.play_file(path):
                    self._current_noise_id = target["id"]
                    try:
                        self.settings_dao.set(
                            "last_noise_id", str(target["id"]))
                    except Exception:
                        pass
            self._update_music_button()
        except Exception:
            pass

    # ---------- 学霸模式（前台进程监控） ----------
    def _start_guard(self):
        """专注进行中且开启学霸模式时，启动前台进程监控。

        以下情形不启动：学霸模式总开关关闭、当前待办被标记为"始终关闭学霸模式"。
        """
        if self.fstate not in (RUNNING, STOPWATCH):
            return
        if self._get_setting("enable_focus_guard", "true").lower() != "true":
            return
        if self.current_todo and self.current_todo.get("is_amway_mode_exempted"):
            # 该待办豁免学霸模式
            return
        if self._guard is None:
            from src.ui_qt.focus_guard import FocusGuard
            self._guard = FocusGuard(
                self.state.whitelist_dao, self.settings_dao, parent=self)
            self._guard.violation.connect(self._on_guard_violation)
            self._guard.restored.connect(self._on_guard_restored)
        # 新一轮专注开始时允许离开提醒一次
        self._guard_notified = False
        self._guard.start()

    def _stop_guard(self):
        """停止学霸模式监控（专注结束/放弃/暂停超时时调用）。"""
        self._guard_notified = False
        if self._guard is not None:
            try:
                self._guard.stop()
            except Exception:
                pass

    def _on_guard_violation(self, proc: str, strict: bool):
        """处理违规：非严格模式→提醒一次并继续；严格模式→直接结束专注。

        提醒使用桌面右下角滑出式通知（show_toast），即使青柠待办被切到后台
        （例如在学霸模式下离开到了其它应用）也能在 Windows 桌面右下角看到。

        为避免频繁重复提醒：每次「离开→回归」仅提醒一次；同一离开期间（仍停留在
        非白名单应用）守门员每 2 秒轮询上报也不再弹窗，直到用户回到专注
        （restored）后再次离开才会重新提醒。通知右上角可手动关闭。
        """
        if strict:
            self._abort_by_guard(proc)
            return
        # 同一次离开只提醒一次，避免轮询持续上报导致频繁弹窗
        if self._guard_notified:
            return
        self._guard_notified = True
        if proc not in self._guard_violations:
            self._guard_violations.append(proc)
        show_toast(
            "学霸模式提醒",
            f"检测到离开专注（{proc}），请回到青柠待办",
            duration=8000,
            on_click=self._bring_to_front,
        )

    def _on_guard_restored(self):
        """前台回到白名单：重置提醒标记，允许下次离开再提醒一次。"""
        self._guard_notified = False

    def _abort_by_guard(self, proc: str):
        """严格模式下，因切换到非白名单应用而结束本次专注。"""
        try:
            self._timer.stop()
        except Exception:
            pass
        self._stop_guard()
        actual = self._current_actual_duration()
        reason = f"学霸模式：切换到 {proc}"
        self._guard_violations.append(proc)
        self._save_record(actual, 0, reason)
        self._reset_loop_state()
        self.fstate = IDLE
        self.lbl_state.setText("学霸模式已结束")
        self._reset_display()
        self._update_buttons()
        show_toast(
            "学霸模式已结束",
            f"已切换到非白名单应用（{proc}），本次专注已结束",
            duration=6000,
            on_click=self._bring_to_front,
        )
        if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
            self.state.on_focus_finished()

    def _current_actual_duration(self) -> int:
        """按当前状态计算已专注秒数。"""
        if self.fstate == STOPWATCH:
            return self.planned + self.elapsed
        if self.timer_type == 1:
            return self.elapsed
        return max(0, self.planned - self.remaining)

    def _flush_guard_violations(self, focus_record_id):
        """把学霸模式期间记录的离开行为写入打断详情。"""
        if not self._guard_violations:
            return
        for proc in self._guard_violations:
            try:
                self.interrupt_dao.create(
                    focus_record_id=focus_record_id,
                    process_name=proc,
                    occurred_at=datetime.datetime.now())
            except Exception:
                pass
        self._guard_violations = []

    def _open_noise_dialog(self):
        """打开白噪音弹窗。"""
        from src.ui_qt.dialogs import WhiteNoiseDialog
        dlg = WhiteNoiseDialog(
            self.noise_dao, self.settings_dao, self.noise_player,
            self._current_noise_id, parent=self)
        dlg.exec()
        # 弹窗关闭后同步当前选中状态
        self._current_noise_id = dlg.selected_noise_id
        if dlg.selected_noise_id and dlg.selected_noise_id > 0:
            try:
                self.settings_dao.set("last_noise_id", str(dlg.selected_noise_id))
            except Exception:
                pass
        # 根据是否正在播放白噪音，更新音乐按钮高亮态
        self._update_music_button()

    def _update_music_button(self):
        """根据当前是否选中白噪音，更新音乐按钮选中态（视觉反馈）。

        选中态复用统一的操作按钮样式机制：白噪音按钮为 checkable，
        checked=True 时由 _style_action_buttons 渲染为高亮填充。
        """
        playing = bool(getattr(self, "_current_noise_id", None))
        btn = getattr(self, "btn_music", None)
        if btn is None:
            return
        btn.blockSignals(True)
        btn.setChecked(playing)
        btn.blockSignals(False)
        # 选中态由 _style_action_buttons 根据 isChecked() 渲染为填充高亮，
        # 重新生成该按钮样式即可（含图标着色），无需依赖 QSS :checked。
        self._style_action_buttons()

    # ---------- 暂停（含超时检测） ----------

    def _on_pause(self):
        # 休息期间不允许暂停
        if self.fstate == RESTING:
            from src.ui_qt.toast import show_toast
            show_toast("休息中", "休息期间无法暂停，请享受休息时光。", duration=3000)
            return
        if self.fstate == RUNNING:
            self.fstate = PAUSED
            self.lbl_state.setText("已暂停")
            self._timer.stop()
            # 记录暂停开始时间
            self._pause_start = datetime.datetime.now()
            # 启动暂停提醒定时器：1分钟后提醒用户继续
            try:
                self._pause_notify_timer = QTimer(self)
            except RuntimeError:
                self._pause_notify_timer = QTimer()
            self._pause_notify_timer.setSingleShot(True)
            self._pause_notify_timer.timeout.connect(self._notify_pause_timeout)
            self._pause_notify_timer.start(60 * 1000)  # 1分钟后提醒
        elif self.fstate == PAUSED:
            # 恢复时检查暂停是否超时
            if self._pause_start and not self._check_pause_timeout():
                return  # 超时自动放弃，已处理
            self.fstate = RUNNING
            self.lbl_state.setText("专注中…")
            self._pause_start = None
            # 停止暂停提醒定时器
            if hasattr(self, '_pause_notify_timer') and self._pause_notify_timer:
                self._pause_notify_timer.stop()
                self._pause_notify_timer = None
            if hasattr(self, '_timer') and self._timer:
                self._timer.start()
        self._update_buttons()

    def _notify_pause_timeout(self):
        """暂停超过1分钟后，发送右下角通知提醒用户继续专注。"""
        if self.fstate != PAUSED:
            return
        from src.ui_qt.toast import show_toast
        max_minutes = float(self._get_setting("max_pause_minutes", "3"))
        remaining_seconds = max(0, max_minutes * 60 - 60)
        if remaining_seconds > 0:
            msg = f"你已暂停1分钟，还有{int(remaining_seconds / 60)}分钟将自动放弃。点击继续专注。"
        else:
            msg = "暂停即将超时，请尽快继续专注。"
        show_toast(
            "青柠待办 · 暂停提醒",
            msg,
            duration=8000,
            on_click=self._bring_to_front,
        )

    def _check_pause_timeout(self) -> bool:
        """检查暂停时长是否超过上限，超时则自动放弃并返回 False。"""
        max_minutes = float(self._get_setting("max_pause_minutes", "3"))
        if max_minutes <= 0:
            return True  # 不限制
        elapsed_pause = (datetime.datetime.now() - self._pause_start).total_seconds()
        if elapsed_pause > max_minutes * 60:
            # 暂停超时，自动放弃
            self._timer.stop()
            self._stop_guard()
            if self.fstate == STOPWATCH:
                actual = self.planned + self.elapsed
            elif self.timer_type == 1:
                actual = self.elapsed
            else:
                actual = self.planned - self.remaining
            reason = f"暂停超时（{elapsed_pause / 60:.1f}分钟）"
            self._save_record(actual, 0, reason)
            self._reset_loop_state()
            self.fstate = IDLE
            self.lbl_state.setText("已放弃")
            self._toast("暂停超时，本次计时已自动放弃")
            self._reset_display()
            self._update_buttons()
            if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
                self.state.on_focus_finished()
            return False
        return True

    # ---------- 完成 ----------

    def _on_finish(self):
        if self.fstate not in (RUNNING, PAUSED, STOPWATCH, RESTING):
            return
        self._stop_guard()
        if self.fstate == RESTING:
            self._end_rest()
            return
        if self.fstate == STOPWATCH:
            # 正计时模式下点击"提取完成"，保存额外时长
            self._save_stopwatch_extra()
            self._play_complete_sound()
            self._reset_loop_state()
            self.fstate = IDLE
            self.lbl_state.setText("已完成")
            self._reset_display()
            self._update_buttons()
            return
        actual = self.elapsed if self.timer_type == 1 else (
            self.planned - self.remaining)
        self._save_record(actual, 1)
        self._toast(f"本次专注 {actual // 60} 分 {actual % 60} 秒，已记录！")
        self._after_focus_completed()

    def _save_stopwatch_extra(self):
        """保存正计时模式下的额外时长记录。"""
        if self._stopwatch_record_saved:
            return
        self._stopwatch_record_saved = True
        actual = self.planned + self.elapsed
        try:
            rid = self.focus_dao.create(
                todo_id=self.current_todo["id"] if self.current_todo else None,
                timer_type=self.timer_type,
                planned_duration=self.planned,
                actual_duration=max(0, actual),
                start_time=self.start_time or datetime.datetime.now(),
                end_time=datetime.datetime.now(),
                is_completed=1,
                record_name=self.current_todo["title"] if self.current_todo else "专注",
            )
            self.ach_dao.evaluate()
            self._flush_guard_violations(rid)
            self._toast(f"正计时 {actual // 60} 分 {actual % 60} 秒，已记录！")
            if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
                self.state.on_focus_finished()
        except Exception as e:
            self._toast(f"记录保存失败：{e}")

    # ---------- 放弃 ----------

    def _on_giveup(self):
        if self.fstate not in (RUNNING, PAUSED, STOPWATCH):
            return
        self._stop_guard()
        # 二次确认
        ret = QMessageBox.question(
            None, "确认终止",
            "确定要终止本次专注吗？终止后记录将标记为未完成。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._timer.stop()
        if self.fstate == STOPWATCH:
            # 正计时模式下放弃，丢弃额外时长
            self._reset_loop_state()
            self.fstate = IDLE
            self.lbl_state.setText("已放弃")
            self._reset_display()
            self._update_buttons()
            if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
                self.state.on_focus_finished()
            return
        actual = self.elapsed if self.timer_type == 1 else (
            self.planned - self.remaining)
        reason, ok = QInputDialog.getText(self, "打断原因",
                                           "记录原因（可选）：")
        reason_text = reason if ok and reason else None
        self._save_record(actual, 0, reason_text)
        # 如果有打断原因，同时记录打断详情
        if reason_text:
            self._save_interrupt_detail(reason_text)
        self._reset_loop_state()
        self.fstate = IDLE
        self.lbl_state.setText("已放弃")
        if self.timer_type != 1:
            self.remaining = self.planned
            self._render(self.remaining)
        else:
            self.lbl_timer.set_text("00:00")
        self._update_buttons()
        if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
            self.state.on_focus_finished()

    def _save_interrupt_detail(self, reason: str):
        """保存打断详情记录到 interrupt_details 表。"""
        try:
            # 获取最新创建的专注记录 id
            recent = self.focus_dao.list_recent(limit=1)
            if recent and self.current_todo:
                self.interrupt_dao.create(
                    focus_record_id=recent[0]["id"],
                    process_name=reason,
                    occurred_at=datetime.datetime.now(),
                )
        except Exception:
            pass  # 打断详情保存失败不影响主流程

    # ---------- 计时 tick ----------

    def _on_tick(self):
        if self.fstate == RUNNING and self.timer_type == 1:
            # 正计时模式
            self.elapsed += 1
            self._render(self.elapsed)
        elif self.fstate == RUNNING:
            # 倒计时/番茄钟/严格模式
            self.remaining -= 1
            self._render(max(0, self.remaining))
            if self.remaining <= 0:
                self._timer.stop()
                self._try_auto_switch_stopwatch()
        elif self.fstate == STOPWATCH:
            # 倒计时结束后自动转入的正计时模式
            self.elapsed += 1
            self._render(self.elapsed)
        elif self.fstate == RESTING:
            self.rest_remaining -= 1
            self._render(max(0, self.rest_remaining))
            if self.rest_remaining <= 0:
                self._timer.stop()
                self._on_rest_finished()

    # ---------- 专注完成后的流程 ----------

    def _play_complete_sound(self):
        """计时完成后按设置播放提示音（focus_complete_sound=none 时不播放）。"""
        try:
            val = self._get_setting("focus_complete_sound", "default")
            if val and val != "none":
                from PyQt6.QtWidgets import QApplication
                if QApplication.instance() is not None:
                    QApplication.beep()
        except Exception:
            pass

    def _after_focus_completed(self):
        """专注完成后的流程：休息前询问 -> 进入休息 / 结束。"""
        self._play_complete_sound()
        self._ask_before_rest_or_direct()

    def _ask_before_rest_or_direct(self):
        """根据设置决定是否弹出休息询问对话框。"""
        ask = self._get_setting("ask_before_break", "true").lower() == "true"
        break_dur = self._get_effective_break_duration()
        if break_dur <= 0 or not ask:
            # 不需要休息或不需要询问，直接决定
            if break_dur <= 0:
                self._on_no_rest()
            else:
                self._enter_rest()
            return
        # 弹出询问对话框
        self._show_break_dialog()

    def _show_break_dialog(self):
        """弹出休息询问对话框。"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("休息确认")
        msg_box.setText("是否进入休息？")
        msg_box.setInformativeText(
            f"休息时长：{self._get_effective_break_duration() // 60} 分钟")
        btn_rest = msg_box.addButton("进入休息",
                                      QMessageBox.ButtonRole.AcceptRole)
        btn_skip = msg_box.addButton("跳过休息",
                                      QMessageBox.ButtonRole.RejectRole)
        btn_giveup = msg_box.addButton("放弃本次",
                                        QMessageBox.ButtonRole.DestructiveRole)
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == btn_rest:
            self._enter_rest()
        elif clicked == btn_skip:
            self._on_no_rest()
        elif clicked == btn_giveup:
            self._on_rest_giveup()

    def _on_no_rest(self):
        """跳过休息后的处理。"""
        has_next = self.current_loop < self.total_loops
        if has_next:
            # 自动开始下一轮
            self.current_loop += 1
            self._update_loop_label()
            self.remaining = self.planned
            self._stopwatch_record_saved = False
            self.lbl_stopwatch_hint.setVisible(False)
            self._start()
            self._toast(f"自动开始第 {self.current_loop}/{self.total_loops} 轮")
        else:
            # 全部完成
            self._all_loops_done()

    def _on_rest_giveup(self):
        """在休息前选择"放弃本次"——放弃当前整轮记录。"""
        # 注意：当前轮次的记录已经保存（completed=1），这里仅重置循环状态
        self._stop_guard()
        self._reset_loop_state()
        self.fstate = IDLE
        self.lbl_state.setText("已放弃")
        self._reset_display()
        self._update_buttons()

    def _all_loops_done(self):
        """所有循环完成，触发 finished 信号。"""
        self._stop_guard()
        self.fstate = IDLE
        self.lbl_state.setText("全部完成！")
        self._reset_display()
        self._update_buttons()
        if hasattr(self.state, "on_focus_finished") and self.state.on_focus_finished:
            self.state.on_focus_finished()

    # ---------- 休息 ----------

    def _enter_rest(self):
        self.fstate = RESTING
        self.rest_remaining = self._get_effective_break_duration()
        if self.rest_remaining <= 0:
            # 无休息，直接处理下一轮
            self._on_rest_finished()
            return
        self.lbl_state.setText("休息一下")
        self._render(self.rest_remaining)
        self._timer.start()
        self._update_buttons()

    def _on_rest_finished(self):
        """休息结束后的处理。"""
        self._timer.stop()
        if self.current_loop < self.total_loops:
            # 自动开始下一轮
            self.current_loop += 1
            self._update_loop_label()
            self.remaining = self.planned
            self.elapsed = 0
            self._stopwatch_record_saved = False
            self.lbl_stopwatch_hint.setVisible(False)
            self.fstate = IDLE
            self.lbl_state.setText(f"第 {self.current_loop}/{self.total_loops} 轮就绪")
            self._reset_display()
            self._update_buttons()
            # 自动开始下一轮专注
            self._start()
            self._toast(f"自动开始第 {self.current_loop}/{self.total_loops} 轮")
        else:
            # 所有循环完成
            self._all_loops_done()

    def _end_rest(self):
        """手动结束休息（用户点击"结束休息"按钮）。"""
        self._timer.stop()
        if self.current_loop < self.total_loops:
            # 有下一轮，回到就绪状态
            self.current_loop += 1
            self._update_loop_label()
            self.fstate = IDLE
            self.lbl_state.setText(f"第 {self.current_loop}/{self.total_loops} 轮就绪")
            self._reset_display()
            self._update_buttons()
        else:
            self._all_loops_done()

    # ---------- 倒计时自动转正计时 ----------

    def _try_auto_switch_stopwatch(self):
        """尝试从倒计时自动切换为正计时模式。"""
        enabled = self._get_setting("auto_switch_stopwatch", "false").lower() == "true"
        if not enabled:
            # 未开启自动转正计时，走正常流程
            self._save_record(self.planned, 1)
            self._toast("本次番茄钟完成！")
            self._after_focus_completed()
            return
        # 切换为正计时模式
        self.fstate = STOPWATCH
        self.elapsed = 0
        self.lbl_stopwatch_hint.setVisible(True)
        self.lbl_stopwatch_hint.setText("已自动转正计时")
        self.lbl_state.setText("正计时中…")
        self._render(0)
        self._timer.start()
        self._update_buttons()

    # ---------- 重置辅助 ----------

    def _reset_loop_state(self):
        """重置循环相关状态。"""
        self.current_loop = 1
        self._stopwatch_record_saved = False
        self._pause_start = None
        self.lbl_stopwatch_hint.setVisible(False)
        self._update_loop_label()

    def _reset_display(self):
        if self.current_todo and self.timer_type in (1, 2):
            # 正计时 / 不计时模式：归零
            self.lbl_timer.set_text("00:00")
        elif self.current_todo:
            self.remaining = self.planned
            self._render(self.planned)

    def _render(self, secs):
        secs = max(0, int(secs))
        self.lbl_timer.set_text(f"{secs // 60:02d}:{secs % 60:02d}")

    # ---------- 数据持久化 ----------

    def _save_record(self, actual, completed, reason=None):
        try:
            start = self.start_time or datetime.datetime.now()
            # 午夜模式：开启时凌晨 0-4 点的记录归属前一天（由设置项控制）
            midnight = self._get_setting("midnight_shift", "false") == "true"
            belong_date = (self.focus_dao._belong_date(start)
                           if midnight else start.date())
            rid = self.focus_dao.create(
                todo_id=self.current_todo["id"] if self.current_todo else None,
                timer_type=self.timer_type,
                planned_duration=self.planned,
                actual_duration=max(0, actual),
                start_time=start,
                end_time=datetime.datetime.now(),
                is_completed=completed,
                record_name=self.current_todo["title"] if self.current_todo else "专注",
                interrupt_reason=reason,
                belong_date=belong_date,
            )
            self.ach_dao.evaluate()
            # 学霸模式期间的离开行为写入打断详情
            self._flush_guard_violations(rid)
            return rid
        except Exception as e:
            self._toast(f"记录保存失败：{e}")
            return None

    # ---------- 选择待办 ----------

    def _pick_todo(self):
        todos = [t for t in self.todo_dao.list(status=0) if t.get("status") != 1]
        items = [(t["title"], t) for t in todos]
        if not items:
            items = [("默认 25 分钟番茄钟", None)]
        item, ok = QInputDialog.getItem(self, "选择待办开始专注",
                                         "待办：", [i[0] for i in items], 0, False)
        if ok and item:
            td = next((t for n, t in items if n == item), None)
            if td is None:
                td = {"id": None, "title": "默认番茄钟", "duration": 1500,
                       "timer_type": 0, "break_duration": 300, "loop_count": 1,
                       "custom_break_duration": None}
            self.load_todo(td)
            self._start()

    # ---------- 白噪音 ----------

    def _build_noise_buttons(self):
        """构建每个分类的白噪音按钮。"""
        noises = self._noises()
        for cat in ["自然音", "氛围音"]:
            self._noise_tabs[cat] = [n for n in noises if n.get("category") == cat]

    def _switch_noise_tab(self, category):
        """切换白噪音分类Tab。"""
        for cat, btn in self._noise_tab_btns:
            btn.setChecked(cat == category)
        self._show_noise_tab(category)

    def _show_noise_tab(self, category):
        """显示指定分类的白噪音按钮列表。"""
        # 每次刷新时重新从数据库获取，避免数据陈旧
        self._build_noise_buttons()
        self._current_noise_category = category

        # 彻底清空现有按钮和子布局
        while self._noise_items_lay.count():
            item = self._noise_items_lay.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    while sub.count():
                        sub_item = sub.takeAt(0)
                        if sub_item is not None and sub_item.widget() is not None:
                            sw = sub_item.widget()
                            sw.setParent(None)
                            sw.deleteLater()

        t = get_current_theme()
        items = self._noise_tabs.get(category, [])

        # 构建"关闭"按钮 + 音源按钮列表
        all_items = [{"id": 0, "name": "关闭", "file_path": None, "category": category}]
        all_items.extend(items)

        # 存储按钮引用，用于切换时直接更新选中状态
        self._noise_btn_refs = {}

        # 使用2列布局
        row = None
        for i, noise in enumerate(all_items):
            if i % 2 == 0:
                row = QHBoxLayout()
                row.setSpacing(6)
                self._noise_items_lay.addLayout(row)

            btn = QPushButton(noise["name"])
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            nid = noise["id"]
            is_off = (nid == 0)
            if is_off:
                btn.setObjectName("chipMuted")
            else:
                btn.setObjectName("chip")
            if (is_off and self._current_noise_id is None) or \
               (not is_off and self._current_noise_id == nid):
                btn.setChecked(True)
            # 禁止自动切换checked状态，由_update_noise_checked统一管理
            btn.setAutoExclusive(False)
            btn.clicked.connect(lambda checked, n=noise: self._toggle_noise(n))
            self._noise_btn_refs[nid] = btn
            row.addWidget(btn)

        # 如果最后一行只有一个按钮，补一个stretch
        if row and len(all_items) % 2 == 1:
            row.addStretch(1)

        # 自定义上传按钮（虚线边框，区别于音源按钮）
        upload_row = QHBoxLayout()
        upload_row.setSpacing(6)
        self._noise_items_lay.addLayout(upload_row)

        upload_btn = QPushButton("+ 自定义音频")
        upload_btn.setObjectName("chipDashed")
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.setFixedHeight(30)
        upload_btn.clicked.connect(self._upload_custom_noise)
        upload_row.addWidget(upload_btn)
        upload_row.addStretch(1)

    def _upload_custom_noise(self):
        """上传自定义音频文件，复制到项目目录并加入数据库。"""
        if not self._current_noise_category:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            "",
            "音频文件 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac);;所有文件 (*)",
        )
        if not file_path:
            return

        # 计算项目根目录
        base = getattr(sys, '_MEIPASS', None)
        if base:
            project_root = base
        else:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))))
            )
        custom_dir = os.path.join(project_root, "assets", "sounds", "custom")
        os.makedirs(custom_dir, exist_ok=True)

        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        timestamp = time.strftime("%Y%m%d%H%M%S")

        if ext_lower == '.wav':
            # WAV 直接复制
            dest_filename = f"{name}_{timestamp}.wav"
            dest_path = os.path.join(custom_dir, dest_filename)
            try:
                shutil.copy2(file_path, dest_path)
            except Exception as ex:
                QMessageBox.warning(self, "上传失败", f"复制文件失败：{ex}")
                return
        else:
            # 非 WAV 格式（MP3/OGG/FLAC/M4A 等）统一转换为 WAV
            # 使用 ffmpeg 转换，确保 winsound 可循环播放
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                import subprocess
                dest_filename = f"{name}_{timestamp}.wav"
                dest_path = os.path.join(custom_dir, dest_filename)
                cmd = [
                    ffmpeg, "-y", "-i", file_path,
                    "-ar", "44100", "-ac", "1", "-sample_fmt", "s16",
                    dest_path,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr[-300:])
            except ImportError:
                # 回退到 soundfile（不支持 MP3，但支持 OGG/FLAC）
                try:
                    import soundfile as sf
                    import numpy as np
                    data, sr = sf.read(file_path)
                    if len(data.shape) > 1:
                        data = data.mean(axis=1)
                    dest_filename = f"{name}_{timestamp}.wav"
                    dest_path = os.path.join(custom_dir, dest_filename)
                    sf.write(dest_path, data, sr, subtype='PCM_16')
                except ImportError:
                    QMessageBox.warning(
                        self, "格式不支持",
                        "仅支持 WAV 格式。请安装 imageio-ffmpeg 或 soundfile 库以支持更多格式。")
                    return
                except Exception as ex:
                    QMessageBox.warning(
                        self, "格式转换失败",
                        f"音频格式转换失败：{ex}\n请尝试上传 WAV 格式。")
                    return
            except Exception as ex:
                QMessageBox.warning(
                    self, "格式转换失败",
                    f"音频格式转换失败：{ex}\n请尝试上传 WAV 格式。")
                return

        rel_path = f"assets/sounds/custom/{dest_filename}"
        display_name = name

        try:
            self.noise_dao.add(display_name, rel_path,
                               self._current_noise_category, is_builtin=0)
        except Exception as ex:
            QMessageBox.warning(self, "上传失败", f"保存到数据库失败：{ex}")
            return

        # 刷新当前分类按钮列表
        self._show_noise_tab(self._current_noise_category)

    def _update_noise_checked(self):
        """直接更新所有白噪音按钮的选中状态，不重建界面。

        通过 unpolish/polish 强制 Qt 立即重算样式表，避免旧按钮高亮
        延迟消失的问题。
        """
        for nid in list(self._noise_btn_refs.keys()):
            btn = self._noise_btn_refs.get(nid)
            if btn is None:
                continue
            try:
                should_check = (nid == 0 and self._current_noise_id is None) or \
                               (nid != 0 and self._current_noise_id == nid)
                # blockSignals 避免触发 clicked
                btn.blockSignals(True)
                btn.setChecked(should_check)
                btn.blockSignals(False)
                # 强制 Qt 立即重算样式表并重绘，消除高亮延迟
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()
            except RuntimeError:
                # 按钮已被 Qt 回收（deleteLater），从引用中移除
                self._noise_btn_refs.pop(nid, None)

    def _toggle_noise(self, noise):
        """切换白噪音播放/停止。"""
        nid = noise["id"]
        if nid == 0:
            # "关闭"按钮：停止播放
            self.noise_player.stop()
            self._current_noise_id = None
            self._update_noise_checked()
            return
        if self._current_noise_id == nid:
            # 再次点击同一个则停止
            self.noise_player.stop()
            self._current_noise_id = None
            self._update_noise_checked()
        else:
            self.noise_player.stop()
            path = noise.get("file_path", "")
            if path:
                self.noise_player.play_file(path)
            self._current_noise_id = nid
            self._update_noise_checked()

    # ---------- 操作按钮样式 ----------

    def _accent_colors(self, accent: str):
        """按语义名返回 (主色, 悬停色, 浅底色, 文字色)。"""
        t = get_current_theme()
        table = {
            "primary": (t.primary, t.primary_hover, t.primary_soft, t.on_primary),
            "success": (t.success, t.success_hover, t.success_soft, t.on_success),
            "warning": (t.warning, t.warning_pressed, t.warning_soft, t.on_warning),
            "danger": (t.danger, t.danger_hover, t.danger_soft, t.on_danger),
        }
        return table.get(accent, table["primary"])

    def _style_action_buttons(self):
        """为专注操作按钮统一生成「胶囊图标按钮」样式。

        视觉规则（统一、精致、语义化）：
        - 默认态：浅色语义底 + 语义色描边 + 语义色文字（低调可辨）；
        - 悬停态：填充语义主色（提示可点）；
        - 选中/激活态（checked，如白噪音播放中）：填充语义主色高亮；
        - 按下态：更深一档语义色；
        - 禁用态：灰化，去描边，弱化文字。
        统一圆角、内边距、字重、字号，图标与文字并排。
        """
        t = get_current_theme()
        r = t.radius_md
        for btn in (self.btn_start, self.btn_pause, self.btn_finish,
                    self.btn_giveup, self.btn_music):
            accent = btn.property("accent") or "primary"
            base, hover, soft, on_c = self._accent_colors(accent)
            checked = btn.isCheckable() and btn.isChecked()
            fill = bool(btn.property("fill")) or checked  # 是否默认填充高亮
            # 图标颜色：填充态用 on_color（白/深字），描边态用语义主色
            icon_name = btn.property("iconName")
            if icon_name:
                btn.setIcon(icon(icon_name, on_c if fill else base, 18))
                btn.setIconSize(QSize(18, 18))
            # 注意：Qt QSS 无法给 QIcon 重新着色，故描边态 hover 不做整体填充
            # 变色（否则语义色图标会与填充背景同色而“消失”）；hover 仅加粗描边。
            # 填充态（主操作 / 选中）图标已着色为 on_color，可安全用填充高亮。
            if fill:
                btn.setStyleSheet(
                    f"QPushButton{{"
                    f"background:{base}; color:{on_c};"
                    f"border:1.5px solid {base}; border-radius:{r}px;"
                    f"padding:9px 20px; font-size:14px; font-weight:700;"
                    f"}}"
                    f"QPushButton:hover{{background:{hover}; border-color:{hover};}}"
                    f"QPushButton:pressed{{background:{hover};}}"
                    f"QPushButton:disabled{{"
                    f"background:{t.surface_variant}; color:{t.text_subtle};"
                    f"border:1.5px solid {t.border};}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton{{"
                    f"background:{soft}; color:{base};"
                    f"border:1.5px solid {base}; border-radius:{r}px;"
                    f"padding:9px 20px; font-size:14px; font-weight:700;"
                    f"}}"
                    f"QPushButton:hover{{background:{soft}; border:2px solid {base};}}"
                    f"QPushButton:pressed{{background:{base}; color:{on_c};}}"
                    f"QPushButton:disabled{{"
                    f"background:{t.surface_variant}; color:{t.text_subtle};"
                    f"border:1.5px solid {t.border};}}"
                )

    # ---------- 按钮状态 ----------

    def _update_buttons(self):
        running = self.fstate == RUNNING
        paused = self.fstate == PAUSED
        resting = self.fstate == RESTING
        stopwatch = self.fstate == STOPWATCH
        self.btn_start.setEnabled(self.fstate in (IDLE, RESTING))
        strict = self.current_todo and self.current_todo.get("timer_type") == 3
        self.btn_pause.setEnabled((running or paused) and not strict)
        self.btn_pause.setText("继续" if paused else "暂停")
        self.btn_finish.setText("结束休息" if resting else "提取完成")
        self.btn_finish.setEnabled(running or paused or resting or stopwatch)
        self.btn_giveup.setEnabled(running or paused or stopwatch)

    # ---------- Toast ----------

    def _bring_to_front(self):
        """将主窗口提到最前面。"""
        parent = self.window()
        if parent:
            parent.showNormal()
            parent.raise_()
            parent.activateWindow()

    def _toast(self, msg):
        """P0 修复: 统一调用 src.ui_qt.toast.show_toast,
        使用全局右下角滑出通知 (与其他页面一致).
        """
        from src.ui_qt.toast import show_toast
        show_toast("提示", msg, duration=2500)

    def refresh(self):
        # 切回专注页时重新应用背景海报（全局 / 待办级），确保设置生效
        try:
            self._apply_focus_background(self._resolve_focus_background())
        except (RuntimeError, AttributeError):
            pass