"""对话框（PyQt6）：待办 / 待办集 / 未来计划 / 更多待办设置 / 数据库连接 / 白噪音。

所有对话框使用卡片容器并继承全局 QSS 主题；青柠主色取自当前主题令牌。
"""
import datetime
import os
import shutil
import sys
import time

from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from src.config import DBConfig
from src.database.connection import test_connection
from src.theme import get_current_theme
from src.tokens import type_scale
from src.ui_qt.icons import icon
from src.ui_qt.widgets import (
    CalendarDateEdit, combo_box, fade_in, ghost_button, glass_card, line_edit,
    primary_button, section_title, TweenSlider, ToggleSwitch, PlusMinusSpinBox,
)

TIMER_TYPES = ["普通番茄钟", "正计时", "倒计时", "严格模式"]
HABIT_TIMER_TYPES = ["倒计时", "正计时", "不计时"]
REPEAT_TYPES = ["不重复", "每日", "每周", "每月"]
PRIORITY = ["普通", "重要", "紧急"]
FREQUENCY_TYPES = ["每天", "每周", "每月"]
HABIT_UNITS = ["分钟", "次", "页", "章", "篇", "个"]

# Tab 类型定义
TAB_TYPES = [
    (0, "普通番茄钟", "timer"),
    (1, "养习惯", "habit"),
    (2, "定目标", "goal_flag"),
]


class _CardDialog(QDialog):
    """带卡片容器与标题的无边框对话框基类（可拖拽）。"""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        # 去掉原生标题栏：使用 FramelessWindowHint + Window（非 Dialog，避免强制标题栏）
        # P0 修复: 移除 WindowStaysOnTopHint, 避免弹窗一直置顶遮挡其他应用
        # 模态性已足以保证用户先处理弹窗
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowTitle(title)
        t = get_current_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        card_f = glass_card(self)
        lay = QVBoxLayout(card_f)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(8)

        # 标题行：标题 + 副标题 + 关闭按钮（替代原生标题栏）
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        if title:
            ti = QLabel(title)
            ti.setStyleSheet(f"font-size:18px; font-weight:700; color:{t.text};")
            title_row.addWidget(ti)
        if subtitle:
            su = QLabel(subtitle)
            su.setObjectName("muted")
            su.setStyleSheet(f"font-size:12px; color:{t.text_muted};")
            title_row.addWidget(su)
        title_row.addStretch(1)
        # 自定义关闭按钮
        btn_close = QPushButton()
        btn_close.setObjectName("iconBtn")
        btn_close.setIcon(icon("close", t.text_muted, 16))
        btn_close.setFixedSize(28, 28)
        btn_close.setFlat(True)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        title_row.addWidget(btn_close)
        lay.addLayout(title_row)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        lay.addLayout(self.body)
        root.addWidget(card_f)
        self._card = card_f

        # 拖拽支持
        self._drag_pos: QPoint | None = None
        # 克制的入场动效（透明度淡入）
        fade_in(self)
        # P1 修复: Esc 关闭, Enter 确认, 统一快捷键行为
        from PyQt6.QtGui import QShortcut, QKeySequence
        self._sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._sc_esc.activated.connect(self.reject)
        self._sc_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self._sc_enter.activated.connect(self.accept)
        self._sc_enter2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        self._sc_enter2.activated.connect(self.accept)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.pos()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and (ev.buttons() & Qt.MouseButton.LeftButton):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None


class TodoDialog(_CardDialog):
    def __init__(self, state, todo=None, parent=None):
        super().__init__("编辑待办" if todo else "新建待办", "设定专注方式与节奏")
        self.state = state
        self.todo = todo
        self.t = get_current_theme()
        self._current_tab = 0
        # 加宽以完整展示「选择图片」行（标签+预览+文件名+按钮）不被裁切
        self.setFixedWidth(540)
        self._build()
        self.on_saved = None

    def _build(self):
        t = self.t
        td = self.todo or {}
        # 从已有数据推断初始 Tab
        existing_type = td.get("type", 0)
        if existing_type in (0, 1, 2):
            self._current_tab = existing_type

        # 更多设置的当前值（初始从 td 读取，所有Tab共享）
        self._extra = {
            "hide_after_complete": td.get("hide_after_complete", 0),
            "is_amway_mode_exempted": td.get("is_amway_mode_exempted", 0),
            "custom_break_duration": td.get("custom_break_duration"),
            "loop_enabled": int(int(td.get("loop_count", 1) or 1) > 1),
        }

        # --- Tab 栏（模拟真实 Tab：左右有不同圆角方向） ---
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(2)  # Tab 之间紧凑间距，模拟连续标签
        self._tab_buttons = []
        for i, (type_val, label, icon_name) in enumerate(TAB_TYPES):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("segTab")
            btn.setIcon(icon(icon_name, t.primary, 14))
            btn.setIconSize(QSize(14, 14))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(36)
            btn.setProperty("tab_index", type_val)
            btn.setProperty("tab_position", i)  # 0=左 1=中 2=右
            btn.clicked.connect(lambda checked, idx=type_val: self._switch_tab(idx))
            tab_bar.addWidget(btn)
            self._tab_buttons.append(btn)

        self._tab_container = QFrame()
        self._tab_container.setObjectName("panel")
        tab_container_lay = QVBoxLayout(self._tab_container)
        tab_container_lay.setContentsMargins(16, 12, 16, 12)
        tab_container_lay.setSpacing(10)

        # --- 普通番茄钟面板 ---
        self._normal_panel = QWidget()
        self._build_normal_panel(td)
        tab_container_lay.addWidget(self._normal_panel)

        # --- 养习惯面板 ---
        self._habit_panel = QWidget()
        self._build_habit_panel(td)
        self._habit_panel.setVisible(False)
        tab_container_lay.addWidget(self._habit_panel)

        # --- 定目标面板 ---
        self._goal_panel = QWidget()
        self._build_goal_panel(td)
        self._goal_panel.setVisible(False)
        tab_container_lay.addWidget(self._goal_panel)

        # 共享设置区：待办背景图（所有类型待办通用，进入专注计时时作为默认背景）
        # 放入 tab 容器内部，高度自适应计入面板，避免固定估算导致的样式错乱
        tab_container_lay.addWidget(self._build_background_picker())

        self.body.addLayout(tab_bar)
        self.body.addWidget(self._tab_container)
        self._buttons()
        self._update_tab_style()
        self._adjust_size_for_tab(self._current_tab)

    # ---------- 共享：待办背景图 ----------
    def _build_background_picker(self):
        """构建待办级背景图选择区（普通/养习惯/定目标通用）。"""
        t = self.t
        td = self.todo or {}
        self._bg_path = td.get("background_path", "") or ""
        container = QFrame()
        container.setObjectName("bgPicker")
        container.setStyleSheet(
            f"#bgPicker{{background:{t.surface_variant}; "
            f"border:1px solid {t.border}; border-radius:{t.radius_md}px;}}")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        lbl = QLabel("背景图")
        lbl.setStyleSheet(
            f"color:{t.text}; font-size:{type_scale.base}px; font-weight:500;")
        lbl.setFixedWidth(52)
        lay.addWidget(lbl)

        # 预览缩略图
        self._bg_preview = QLabel()
        self._bg_preview.setFixedSize(72, 44)
        self._bg_preview.setScaledContents(False)
        self._bg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_preview.setStyleSheet(
            f"border:1px solid {t.border}; border-radius:6px; "
            f"background:{t.surface_variant};")
        lay.addWidget(self._bg_preview)

        # 文件名（可压缩，过长时由布局吸收，避免挤压按钮）
        self._bg_name = QLabel("未设置")
        self._bg_name.setStyleSheet(f"color:{t.text_muted}; font-size:13px;")
        self._bg_name.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._bg_name.setMinimumWidth(40)
        lay.addWidget(self._bg_name, 1)

        # 操作按钮：按内容自适配宽度（Minimum 策略 = 恰好容纳图标+文字），
        # 既不截断文字，也不会相互重叠；多余空间由文件名标签吸收。
        btn_select = ghost_button("选择图片", icon_name="image",
                                  on_click=self._pick_bg)
        btn_clear = ghost_button("清除", icon_name="close",
                                 on_click=self._clear_bg)
        btn_select.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn_clear.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        lay.addWidget(btn_select)
        lay.addWidget(btn_clear)

        self._refresh_bg_preview()
        return container

    def _refresh_bg_preview(self):
        """根据当前 _bg_path 刷新预览与文件名（按比例缩放，完整展示）。"""
        t = self.t
        path = self._bg_path
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                # 按比例缩放并居中绘制，避免拉伸/裁切导致展示不完整
                scaled = pix.scaled(
                    self._bg_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                self._bg_preview.setPixmap(scaled)
                self._bg_name.setText(os.path.basename(path))
                return
        self._bg_preview.clear()
        self._bg_preview.setStyleSheet(
            f"border:1px solid {t.border}; border-radius:6px;"
            f" background:{t.surface_variant};")
        self._bg_name.setText("未设置")

    def _pick_bg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择待办背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._bg_path = path
            self._refresh_bg_preview()

    def _clear_bg(self):
        self._bg_path = ""
        self._refresh_bg_preview()

    # ---------- 普通番茄钟面板 ----------
    def _build_normal_panel(self, td):
        panel = self._normal_panel
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)  # 统一行间距

        self.ed_title = line_edit("待办名称", value=td.get("title", ""))
        self.ed_title.setFixedHeight(34)
        groups = self.state.group_dao.list()
        self.cb_group = combo_box(
            [("0", "未分类")] + [(str(g["id"]), g["name"]) for g in groups],
            value=str(td.get("group_id") or "0"))
        self.cb_timer = combo_box(
            [(str(i), v) for i, v in enumerate(TIMER_TYPES)],
            value=str(td.get("timer_type", 0)))
        self.sp_duration = self._num("专注时长",
                                     td.get("duration", 1500) // 60, 1, 600, "分钟")
        self.sp_break = self._num("休息时长",
                                   td.get("break_duration", 300) // 60, 0, 120, "分钟")
        self.sp_loop = self._num("循环次数", td.get("loop_count", 1), 1, None, "次")
        self.cb_priority = combo_box(
            [(str(i), v) for i, v in enumerate(PRIORITY)],
            value=str(td.get("priority", 0)))
        self.cb_repeat = combo_box(
            [(str(i), v) for i, v in enumerate(REPEAT_TYPES)],
            value=str(td.get("repeat_type", 0)))

        lay.addWidget(self.ed_title)
        row1 = QHBoxLayout(); row1.setSpacing(8)
        row1.addWidget(self.cb_group, 1); row1.addWidget(self.cb_timer, 1)
        lay.addLayout(row1)
        # 时长设置：滑块+输入框，垂直排列避免拥挤
        lay.addWidget(self.sp_duration)
        lay.addWidget(self.sp_break)
        lay.addWidget(self.sp_loop)
        row3 = QHBoxLayout(); row3.setSpacing(8)
        row3.addWidget(self.cb_priority, 1); row3.addWidget(self.cb_repeat, 1)
        lay.addLayout(row3)

        # "更多设置" 链接按钮
        self.btn_more_settings_normal = self._make_more_settings_btn()
        lay.addWidget(self.btn_more_settings_normal)

    # ---------- 养习惯面板 ----------
    def _build_habit_panel(self, td):
        panel = self._habit_panel
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)  # 统一行间距

        self.ed_habit_title = line_edit("事项名称",
                                         value=td.get("title", ""))
        self.ed_habit_title.setFixedHeight(34)

        # 频率
        self.cb_frequency = combo_box(
            [(str(i), v) for i, v in enumerate(FREQUENCY_TYPES)],
            value=str(td.get("habit_frequency", 0)))

        # 完成量 + 单位
        self.ed_habit_amount = line_edit("目标量",
                                         value=str(td.get("habit_target") or ""))
        self.ed_habit_amount.setPlaceholderText("目标量")
        self.cb_habit_unit = combo_box(
            [(u, u) for u in HABIT_UNITS],
            value=td.get("habit_unit") or "分钟")

        # 计时模式
        self.cb_timer_habit = combo_box(
            [(str(i), v) for i, v in enumerate(HABIT_TIMER_TYPES)],
            value=str(td.get("habit_timer_type", 0)))

        # 时长
        self.sp_duration_habit = self._num("专注时长",
                                           td.get("duration", 1500) // 60, 1, 600, "分钟")

        # "更多设置" 链接按钮
        self.btn_more_settings = self._make_more_settings_btn()

        lay.addWidget(self.ed_habit_title)

        row_freq = QHBoxLayout(); row_freq.setSpacing(8)
        row_freq.addWidget(self._field_label("频率"), 0)
        row_freq.addWidget(self.cb_frequency, 1)
        lay.addLayout(row_freq)

        # 目标量移到标签位置，与频率/计时模式对齐一致
        row_amount = QHBoxLayout(); row_amount.setSpacing(8)
        row_amount.addWidget(self._field_label("目标量"), 0)
        row_amount.addWidget(self.ed_habit_amount, 1, Qt.AlignmentFlag.AlignVCenter)
        row_amount.addWidget(self.cb_habit_unit, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(row_amount)

        row_timer = QHBoxLayout(); row_timer.setSpacing(8)
        row_timer.addWidget(self._field_label("计时模式"), 0)
        row_timer.addWidget(self.cb_timer_habit, 1)
        lay.addLayout(row_timer)

        lay.addWidget(self.sp_duration_habit)
        lay.addWidget(self.btn_more_settings)

    # ---------- 定目标面板 ----------
    def _build_goal_panel(self, td):
        panel = self._goal_panel
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.ed_goal_title = line_edit("目标名称",
                                        value=td.get("title", ""))
        self.ed_goal_title.setFixedHeight(34)

        # 目标类型：每日专注时长目标
        self.cb_goal_type = combo_box(
            [("0", "每日专注时长"), ("1", "每周专注时长"), ("2", "每月专注时长")],
            value=str(td.get("goal_type", 0)))

        # 目标时长
        self.sp_goal_duration = self._num("目标时长",
                                           td.get("duration", 120) // 60, 10, 1200, "分钟")

        # 计时模式
        self.cb_goal_timer = combo_box(
            [(str(i), v) for i, v in enumerate(TIMER_TYPES)],
            value=str(td.get("timer_type", 0)))

        lay.addWidget(self.ed_goal_title)

        row_type = QHBoxLayout(); row_type.setSpacing(8)
        row_type.addWidget(self._field_label("目标类型"), 0)
        row_type.addWidget(self.cb_goal_type, 1)
        lay.addLayout(row_type)

        lay.addWidget(self.sp_goal_duration)

        row_gtimer = QHBoxLayout(); row_gtimer.setSpacing(8)
        row_gtimer.addWidget(self._field_label("计时模式"), 0)
        row_gtimer.addWidget(self.cb_goal_timer, 1)
        lay.addLayout(row_gtimer)

        # "更多设置" 链接按钮
        self.btn_more_settings_goal = self._make_more_settings_btn()
        lay.addWidget(self.btn_more_settings_goal)

    # ---------- 公共控件工厂 ----------
    def _field_label(self, text):
        """统一字段标签：左对齐、基础字号(14px)、中等字重，与输入框/下拉框字体一致。"""
        t = self.t
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{t.text}; font-size:{type_scale.base}px; font-weight:500; "
            f"qproperty-alignment:AlignLeft|AlignVCenter;")
        lbl.setFixedWidth(60)
        return lbl

    # ---------- Tab 切换 ----------
    def _make_more_settings_btn(self):
        """创建"更多设置"链接按钮（所有面板共用）。"""
        t = self.t
        btn = QPushButton("  更多设置")
        btn.setIcon(icon("settings", t.primary, 14))
        btn.setIconSize(QSize(14, 14))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(
            f"color:{t.primary}; font-size:13px; font-weight:600; "
            f"background:transparent; padding:6px 0; text-align:left; "
            f"border:none; text-decoration:underline;")
        btn.clicked.connect(self._open_more_settings)
        return btn

    def _switch_tab(self, index):
        self._current_tab = index
        self._normal_panel.setVisible(index == 0)
        self._habit_panel.setVisible(index == 1)
        self._goal_panel.setVisible(index == 2)
        self._update_tab_style()
        # 切换Tab后调整对话框高度
        self._adjust_size_for_tab(index)

    def _adjust_size_for_tab(self, index):
        """根据当前Tab内容高度精确调整对话框大小。

        采用 adjustSize() 让 Qt 基于当前可见内容（仅当前面板 + 背景图 +
        Tab栏 + 按钮栏）自动计算自然高度，避免固定常数估算导致的裁切/留白。
        """
        # 确保仅当前面板参与高度计算（隐藏面板不计入布局 sizeHint）
        self._normal_panel.setVisible(index == 0)
        self._habit_panel.setVisible(index == 1)
        self._goal_panel.setVisible(index == 2)
        # 临时放开固定高度，让 Qt 依据可见内容计算自然高度
        self.setFixedHeight(16777215)  # QWIDGETSIZE_MAX
        self.adjustSize()
        h = self.height()
        # 加一点安全边距，避免内容被裁切（尤其含 PlusMinusSpinBox 的行）
        h += 8
        # 限制最小/最大高度
        h = max(h, 440)
        h = min(h, 800)
        self.setFixedHeight(h)

    def _update_tab_style(self):
        # 选中态由全局 #segTab:checked 状态机统一驱动，不再内联重写 hover
        for btn in self._tab_buttons:
            idx = btn.property("tab_index")
            btn.setChecked(idx == self._current_tab)

    # ---------- 更多设置对话框 ----------
    def _open_more_settings(self):
        dlg = MoreTodoSettingsDialog(self.t, self._extra, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._extra = dlg.values

    # ---------- 公共控件工厂 ----------
    def _num(self, label, value, lo, hi, unit=""):
        """创建滑块+数字输入框组合控件。

        布局：[标签(固定80px)] [滑块(弹性)] [输入框(固定80px)] [单位(固定30px)]
        当 hi=None 时，滑块上限使用 lo*100 作为兜底（保证可用），
        而输入框不设上限，允许任意正整数。
        """
        t = self.t
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        # 左侧标签
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{t.text}; font-size:{type_scale.base}px; font-weight:500;")
        lbl.setFixedWidth(80)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 滑块上限：hi 为 None 时用 lo*100 兜底（仅作滑块可视化范围）
        slider_hi = hi if hi is not None else max(lo * 100, 100)

        # 中间滑块
        slider = TweenSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, slider_hi)
        slider.setValue(min(value, slider_hi))

        # 右侧输入框（+/- 按钮）
        sb = PlusMinusSpinBox()
        if hi is not None:
            sb.setRange(lo, hi)
        else:
            sb.setRange(lo, 999999)
        sb.setValue(value)
        sb.setFixedWidth(130)

        # 单位标签（放在+按钮右侧，与数值框有间距）
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color:{t.text_muted}; font-size:13px; padding-left: 8px;")
        unit_lbl.setFixedWidth(44)
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 滑块↔输入框联动：当 hi=None 时，输入框值超出滑块范围则不更新滑块
        if hi is not None:
            slider.valueChanged.connect(sb.setValue)
            sb.valueChanged.connect(slider.setValue)
        else:
            def _on_slider(v):
                sb.blockSignals(True)
                sb.setValue(v)
                sb.blockSignals(False)
            def _on_spinbox(v):
                slider.blockSignals(True)
                if v <= slider_hi:
                    slider.setValue(v)
                slider.blockSignals(False)
            slider.valueChanged.connect(_on_slider)
            sb.valueChanged.connect(_on_spinbox)

        h.addWidget(lbl)
        h.addWidget(slider, 1)
        h.addWidget(sb)
        h.addWidget(unit_lbl)
        container._spinbox = sb  # 保存引用，方便取值
        return container

    # ---------- 底部按钮 ----------
    def _buttons(self):
        t = self.t
        # 分割线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{t.border};")
        self.body.addWidget(sep)
        # 按钮右对齐，spacing=12
        h = QHBoxLayout()
        h.setSpacing(12)
        h.addStretch(1)
        cancel = ghost_button("取消", on_click=self.reject, min_w=88)
        ok = primary_button("确认", on_click=self._save, min_w=88)
        h.addWidget(cancel, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(ok, 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addLayout(h)

    # ---------- 保存 ----------
    def _save(self):
        t = self.t
        todo_type = self._current_tab

        if todo_type == 0:
            # 普通番茄钟
            title = self.ed_title.text().strip()
            if not title:
                self.ed_title.setStyleSheet(
                    f"border:1px solid {t.danger}; border-radius:{t.radius_md}px;"
                    f"padding:8px 12px; background:{t.surface_variant};")
                return
            values = dict(
                title=title,
                group_id=(int(self.cb_group.currentData()) if self.cb_group.currentData() != "0" else None),
                timer_type=int(self.cb_timer.currentData()),
                duration=int(self.sp_duration._spinbox.value()) * 60,
                break_duration=int(self.sp_break._spinbox.value()) * 60,
                loop_count=int(self.sp_loop._spinbox.value()),
                priority=int(self.cb_priority.currentData()),
                repeat_type=int(self.cb_repeat.currentData()),
                hide_after_complete=self._extra.get("hide_after_complete", 0),
                is_amway_mode_exempted=self._extra.get("is_amway_mode_exempted", 0),
                custom_break_duration=self._extra.get("custom_break_duration"),
                background_path=self._bg_path or None,
                type=0,
            )
        elif todo_type == 1:
            # 养习惯
            title = self.ed_habit_title.text().strip()
            if not title:
                self.ed_habit_title.setStyleSheet(
                    f"border:1px solid {t.danger}; border-radius:{t.radius_md}px;"
                    f"padding:8px 12px; background:{t.surface_variant};")
                return
            loop_count = 2 if self._extra.get("loop_enabled", 0) else 1
            values = dict(
                title=title,
                timer_type=int(self.cb_timer_habit.currentData()),
                duration=int(self.sp_duration_habit._spinbox.value()) * 60,
                type=1,
                habit_target=self.ed_habit_amount.text().strip() or None,
                habit_unit=self.cb_habit_unit.currentData(),
                loop_count=loop_count,
                hide_after_complete=self._extra.get("hide_after_complete", 0),
                is_amway_mode_exempted=self._extra.get("is_amway_mode_exempted", 0),
                custom_break_duration=self._extra.get("custom_break_duration"),
                background_path=self._bg_path or None,
            )
        elif todo_type == 2:
            # 定目标
            title = self.ed_goal_title.text().strip()
            if not title:
                self.ed_goal_title.setStyleSheet(
                    f"border:1px solid {t.danger}; border-radius:{t.radius_md}px;"
                    f"padding:8px 12px; background:{t.surface_variant};")
                return
            goal_type = int(self.cb_goal_type.currentData())
            target_duration = int(self.sp_goal_duration._spinbox.value()) * 60
            values = dict(
                title=title,
                timer_type=int(self.cb_goal_timer.currentData()),
                duration=target_duration,
                background_path=self._bg_path or None,
                type=2,
            )
            # 同时创建/更新 goal 表中的时长目标
            try:
                self.state.goal_dao.upsert_duration_goal(
                    goal_type, target_duration)
            except Exception:
                pass

        if self.todo:
            self.state.todo_dao.update(self.todo["id"], **values)
        else:
            self.state.todo_dao.create(**values)
        if self.on_saved:
            self.on_saved()
        self.accept()


class MoreTodoSettingsDialog(_CardDialog):
    """更多待办设置对话框（复用统一卡片风格，按钮样式与全局一致）。

    包含：完成后第二天不再显示、始终关闭学霸模式、循环计时、自定义休息时长。
    """

    def __init__(self, theme, init_values=None, parent=None):
        # 复用 _CardDialog 的卡片容器 + 右上角关闭按钮，保证与全局风格一致
        super().__init__("更多待办设置", "设定此待办的高级选项", parent)
        self.t = theme
        self.values = dict(init_values or {})
        self.setMinimumWidth(460)
        self._build()

    def _build(self):
        t = self.t
        body = self.body
        body.setSpacing(14)

        # 开关胶囊样式由全局 #switch 状态机统一驱动（见 theme.build_qss）

        def row(icon_name, label, control):
            """统一行：左侧 [图标块 + 文字]，右侧控件。"""
            r = QHBoxLayout()
            r.setSpacing(12)
            ico = QLabel()
            ico.setPixmap(icon(icon_name, t.primary, 16).pixmap(30, 30))
            ico.setFixedSize(30, 30)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet(
                f"background:{t.primary_soft}; border-radius:{t.radius_sm}px;")
            col = QVBoxLayout()
            col.setSpacing(2)
            lab = QLabel(label)
            lab.setStyleSheet(f"font-size:14px; font-weight:500; color:{t.text};")
            col.addWidget(lab)
            r.addWidget(ico)
            r.addLayout(col, 1)
            if isinstance(control, QWidget):
                r.addWidget(control)
            else:
                r.addLayout(control)
            return r

        # --- 分区1：行为设置 ---
        card1 = QFrame()
        card1.setObjectName("sCard1")
        card1.setStyleSheet(
            f"#sCard1{{background:{t.surface_variant}; "
            f"border:1px solid {t.border}; border-radius:{t.radius_md}px;}}")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(16, 14, 16, 14)
        c1.setSpacing(8)
        c1.addWidget(section_title("行为设置"))
        c1.addSpacing(2)

        self.sw_hide_after = ToggleSwitch(
            checked=bool(self.values.get("hide_after_complete", 0)))
        c1.addLayout(
            row("eye-off", "完成后第二天不再显示", self.sw_hide_after))

        self.sw_exempt_amway = ToggleSwitch(
            checked=bool(self.values.get("is_amway_mode_exempted", 0)))
        c1.addLayout(
            row("shield", "此待办始终关闭学霸模式", self.sw_exempt_amway))

        self.sw_loop = ToggleSwitch(
            checked=bool(self.values.get("loop_enabled", 0)))
        c1.addLayout(row("loop", "循环计时", self.sw_loop))
        body.addWidget(card1)

        # --- 分区2：休息时长 ---
        card2 = QFrame()
        card2.setObjectName("sCard2")
        card2.setStyleSheet(
            f"#sCard2{{background:{t.surface_variant}; "
            f"border:1px solid {t.border}; border-radius:{t.radius_md}px;}}")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(16, 14, 16, 14)
        c2.setSpacing(8)
        c2.addWidget(section_title("休息时长"))
        c2.addSpacing(2)

        self._cb_custom_break = ToggleSwitch(
            checked=self.values.get("custom_break_duration") is not None)
        c2.addLayout(
            row("clock", "自定义此待办休息时长", self._cb_custom_break))

        row_break = QHBoxLayout()
        row_break.setSpacing(10)
        row_break.setContentsMargins(42, 2, 0, 0)

        self.sp_custom_break = PlusMinusSpinBox()
        self.sp_custom_break.setRange(1, 120)
        val = self.values.get("custom_break_duration")
        if val is not None:
            self.sp_custom_break.setValue(val // 60)
        else:
            self.sp_custom_break.setValue(5)
        self.sp_custom_break.setEnabled(bool(val is not None))
        self.sp_custom_break.setFixedWidth(130)

        self._slider_break = TweenSlider(Qt.Orientation.Horizontal)
        self._slider_break.setRange(1, 120)
        self._slider_break.setValue(self.sp_custom_break.value())
        self._slider_break.setEnabled(bool(val is not None))

        lbl_break_unit = QLabel("分钟")
        lbl_break_unit.setStyleSheet(f"color:{t.text_muted}; font-size:13px;")
        lbl_break_unit.setFixedWidth(36)

        self.sp_custom_break.valueChanged.connect(self._slider_break.setValue)
        self._slider_break.valueChanged.connect(self.sp_custom_break.setValue)
        self._cb_custom_break.toggled.connect(self._slider_break.setEnabled)
        self._cb_custom_break.toggled.connect(self.sp_custom_break.setEnabled)
        row_break.addWidget(self._slider_break, 1)
        row_break.addWidget(self.sp_custom_break)
        row_break.addWidget(lbl_break_unit)
        c2.addLayout(row_break)
        body.addWidget(card2)

        body.addStretch(1)

        # --- 底部按钮 ---
        h = QHBoxLayout()
        h.setSpacing(12)
        h.addStretch(1)
        close_btn = ghost_button("关闭", on_click=self.reject, min_w=88)
        save_btn = primary_button("保存", on_click=self._on_confirm, min_w=88)
        h.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(h)

    def _on_confirm(self):
        custom_break = None
        if self._cb_custom_break.isChecked():
            custom_break = int(self.sp_custom_break.value()) * 60
        self.values.update({
            "hide_after_complete": int(self.sw_hide_after.isChecked()),
            "is_amway_mode_exempted": int(self.sw_exempt_amway.isChecked()),
            "loop_enabled": int(self.sw_loop.isChecked()),
            "custom_break_duration": custom_break,
        })
        self.accept()


class GroupDialog(_CardDialog):
    def __init__(self, state, parent=None):
        super().__init__("新建待办集", "归类你的待办")
        self.state = state
        self.t = get_current_theme()
        self.ed_name = line_edit("待办集名称")
        self.body.addWidget(self.ed_name)
        h = QHBoxLayout(); h.addStretch(1)
        h.addWidget(ghost_button("取消", on_click=self.reject, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(primary_button("保存", on_click=self._save, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addLayout(h)
        self.on_saved = None

    def _save(self):
        name = self.ed_name.text().strip()
        if not name:
            return
        self.state.group_dao.create(name)
        if self.on_saved:
            self.on_saved()
        self.accept()


class PlanDialog(_CardDialog):
    def __init__(self, state, plan=None, parent=None):
        super().__init__("编辑计划" if plan else "新建未来计划",
                         "重要之事，铭刻于心")
        self.state = state
        self.plan = plan
        self.t = get_current_theme()
        self._build()
        self.on_saved = None

    def _build(self):
        p = self.plan or {}
        self.ed_title = line_edit("事项名称", value=p.get("title", ""))
        self.dp_date = CalendarDateEdit()
        self.dp_date.setDisplayFormat("yyyy-MM-dd")
        self.dp_date.setMinimumWidth(160)
        default = p.get("target_date") or (datetime.date.today() + datetime.timedelta(days=30))
        if isinstance(default, str):
            try:
                default = datetime.date.fromisoformat(default)
            except ValueError:
                default = datetime.date.today()
        self.dp_date.setDate(default)
        self.ed_remark = line_edit("备注", value=p.get("remark", ""))
        self.body.addWidget(self.ed_title)
        self.body.addWidget(self.dp_date)
        self.body.addWidget(self.ed_remark)
        h = QHBoxLayout(); h.addStretch(1)
        h.addWidget(ghost_button("取消", on_click=self.reject, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(primary_button("保存", on_click=self._save, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addLayout(h)

    def _save(self):
        title = self.ed_title.text().strip()
        if not title:
            return
        target = self.dp_date.date().toPyDate()
        if self.plan:
            self.state.plan_dao.update(self.plan["id"], title, target,
                                        self.ed_remark.text().strip() or None)
        else:
            self.state.plan_dao.create(title, target,
                                      self.ed_remark.text().strip() or None)
        if self.on_saved:
            self.on_saved()
        self.accept()


class DBConfigDialog(_CardDialog):
    def __init__(self, db_config: DBConfig = None, on_result=None, parent=None):
        super().__init__("数据库连接设置",
                         "请填写本地 MySQL 连接信息，首次连接将自动创建数据库与数据表。")
        self.on_result = on_result
        cfg = db_config or DBConfig()
        self.t = get_current_theme()
        self.ed_host = line_edit("主机地址", value=cfg.host)
        # P1 修复: 端口加数字校验器, 防止用户输入 "abc" 导致 int() 抛异常
        from PyQt6.QtGui import QIntValidator
        self.ed_port = line_edit("端口", value=str(cfg.port))
        self.ed_port.setValidator(QIntValidator(1, 65535, self.ed_port))
        self.ed_port.setMaxLength(5)
        self.ed_user = line_edit("用户名", value=cfg.user)
        self.ed_pwd = line_edit("密码", value=cfg.password, password=True)
        self.ed_db = line_edit("数据库名", value=cfg.database)
        self.body.addWidget(self.ed_host)
        self.body.addWidget(self.ed_port)
        self.body.addWidget(self.ed_user)
        self.body.addWidget(self.ed_pwd)
        self.body.addWidget(self.ed_db)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("muted")
        self.body.addWidget(self.lbl_status)
        h = QHBoxLayout(); h.addStretch(1)
        h.addWidget(ghost_button("测试连接", on_click=self._on_test, icon_name="refresh"))
        h.addWidget(ghost_button("取消", on_click=self.reject, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(primary_button("保存并连接", on_click=self._on_ok, min_w=88), 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addLayout(h)

    def current_config(self) -> DBConfig:
        return DBConfig(
            host=self.ed_host.text().strip() or "127.0.0.1",
            port=int(self.ed_port.text() or 3306),
            user=self.ed_user.text().strip() or "root",
            password=self.ed_pwd.text(),
            database=self.ed_db.text().strip() or "qingning_todo",
        )

    def _set_status(self, msg, ok=None):
        color = self.t.text_muted
        if ok is True:
            color = self.t.success
        elif ok is False:
            color = self.t.danger
        self.lbl_status.setStyleSheet(f"color:{color}; font-size:13px;")
        self.lbl_status.setText(msg)

    def _on_test(self):
        cfg = self.current_config()
        self._set_status("正在测试连接...", None)
        ok, msg = test_connection(cfg, check_database=False)
        self._set_status(("✓ " if ok else "✗ ") + msg, ok)

    def _on_ok(self):
        cfg = self.current_config()
        ok, msg = test_connection(cfg, check_database=False)
        if not ok:
            self._set_status("✗ " + msg, False)
            return
        if self.on_result:
            self.on_result(cfg)
        self.accept()


class WhiteNoiseDialog(_CardDialog):
    """白噪音弹窗：包含开关设置 + 分类Tab + 音源列表 + 自定义上传。

    功能：
    - "开启背景音"开关：控制白噪音总开关
    - "计时开始自动播放"开关：计时开始时自动播放上次选中的白噪音
    - 两个分类Tab（自然音/氛围音）
    - 每个分类下显示音源按钮（2列布局）
    - 支持自定义音频上传
    """

    def __init__(self, noise_dao, settings_dao, noise_player,
                 current_noise_id=None, parent=None):
        super().__init__("白噪音", "选择专注时播放的背景音")
        self.noise_dao = noise_dao
        self.settings_dao = settings_dao
        self.noise_player = noise_player
        self.selected_noise_id = current_noise_id
        self._current_category = "自然音"
        self._noise_btn_refs = {}
        self._noise_tabs = {}
        self._noise_tab_btns = []
        t = get_current_theme()

        # ---- 开关区域 ----
        sw_row = QVBoxLayout()
        sw_row.setSpacing(8)

        # 开启背景音
        self.cb_bg_enabled = QCheckBox("  开启背景音")
        self.cb_bg_enabled.setChecked(
            settings_dao.get("bg_music_enabled", "false") == "true")
        self.cb_bg_enabled.setStyleSheet(
            f"QCheckBox{{font-size:13px; color:{t.text}; padding:6px 0;}}"
            f"QCheckBox::indicator{{width:18px; height:18px; border-radius:4px;"
            f" border:2px solid {t.border};}}"
            f"QCheckBox::indicator:checked{{background:{t.primary};"
            f" border-color:{t.primary};}}")
        sw_row.addWidget(self.cb_bg_enabled)

        # 计时开始自动播放
        self.cb_auto_play = QCheckBox("  计时开始自动播放")
        self.cb_auto_play.setChecked(
            settings_dao.get("auto_play_on_start", "false") == "true")
        self.cb_auto_play.setStyleSheet(
            f"QCheckBox{{font-size:13px; color:{t.text}; padding:6px 0;}}"
            f"QCheckBox::indicator{{width:18px; height:18px; border-radius:4px;"
            f" border:2px solid {t.border};}}"
            f"QCheckBox::indicator:checked{{background:{t.primary};"
            f" border-color:{t.primary};}}")
        sw_row.addWidget(self.cb_auto_play)

        # 分割线
        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background:{t.border};")
        sw_row.addWidget(sep1)
        self.body.addLayout(sw_row)

        # ---- 分类Tab ----
        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        for cat in ["自然音", "氛围音"]:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setObjectName("segTab")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, c=cat: self._switch_tab(c))
            tab_row.addWidget(btn)
            self._noise_tab_btns.append((cat, btn))
        tab_row.addStretch(1)
        self.body.addLayout(tab_row)

        # ---- 音源列表容器 ----
        self._items_widget = QWidget()
        self._items_lay = QVBoxLayout(self._items_widget)
        self._items_lay.setSpacing(4)
        self.body.addWidget(self._items_widget)

        # 初始化
        if self._noise_tab_btns:
            self._noise_tab_btns[0][1].setChecked(True)
            self._show_tab(self._noise_tab_btns[0][0])

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(ghost_button("关闭", on_click=self._on_close,
                                        icon_name="close"))
        self.body.addLayout(btn_row)

        self.setFixedWidth(420)
        self.setMaximumHeight(600)

    def _switch_tab(self, category):
        for cat, btn in self._noise_tab_btns:
            btn.setChecked(cat == category)
        self._show_tab(category)

    def _show_tab(self, category):
        self._current_category = category
        # 清空现有内容
        while self._items_lay.count():
            item = self._items_lay.takeAt(0)
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
        # 获取白噪音数据
        try:
            all_noises = self.noise_dao.list()
        except Exception:
            all_noises = []
        items = [n for n in all_noises if n.get("category") == category]

        all_items = [{"id": 0, "name": "关闭", "file_path": None}]
        all_items.extend(items)

        self._noise_btn_refs = {}
        row = None
        for i, noise in enumerate(all_items):
            if i % 2 == 0:
                row = QHBoxLayout()
                row.setSpacing(6)
                self._items_lay.addLayout(row)

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
            if (is_off and self.selected_noise_id is None) or \
               (not is_off and self.selected_noise_id == nid):
                btn.setChecked(True)
            btn.setAutoExclusive(False)
            btn.clicked.connect(lambda checked, n=noise: self._toggle(n))
            self._noise_btn_refs[nid] = btn
            row.addWidget(btn)

        if row and len(all_items) % 2 == 1:
            # 末尾单独的噪音按钮与上方 2 列按钮等宽（各占半列）
            btn = row.itemAt(0).widget()
            if btn is not None:
                row.setStretch(row.indexOf(btn), 1)
            row.addStretch(1)

        # 自定义上传按钮
        upload_row = QHBoxLayout()
        upload_row.setSpacing(6)
        self._items_lay.addLayout(upload_row)
        upload_btn = QPushButton("+ 自定义音频")
        upload_btn.setObjectName("chipDashed")
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.setFixedHeight(30)
        upload_btn.clicked.connect(self._upload)
        upload_row.addWidget(upload_btn, 1)
        upload_row.addStretch(1)

    def _toggle(self, noise):
        nid = noise["id"]
        if nid == 0 or nid == self.selected_noise_id:
            # 关闭或再次点击当前选中 → 停止
            self.noise_player.stop()
            self.selected_noise_id = None
        else:
            self.noise_player.stop()
            path = noise.get("file_path", "")
            if path and self.noise_player.play_file(path):
                self.selected_noise_id = nid
            # 播放失败时不更新 selected_noise_id
        self._update_checked()

    def _update_checked(self):
        for nid in list(self._noise_btn_refs.keys()):
            btn = self._noise_btn_refs.get(nid)
            if btn is None:
                continue
            try:
                should_check = (nid == 0 and self.selected_noise_id is None) or \
                               (nid != 0 and self.selected_noise_id == nid)
                btn.blockSignals(True)
                btn.setChecked(should_check)
                btn.blockSignals(False)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()
            except RuntimeError:
                self._noise_btn_refs.pop(nid, None)

    def _upload(self):
        if not self._current_category:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "",
            "音频文件 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac);;所有文件 (*)")
        if not file_path:
            return

        base = getattr(sys, '_MEIPASS', None)
        if base:
            project_root = base
        else:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        custom_dir = os.path.join(project_root, "assets", "sounds", "custom")
        os.makedirs(custom_dir, exist_ok=True)

        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        timestamp = time.strftime("%Y%m%d%H%M%S")

        if ext_lower == '.wav':
            dest_filename = f"{name}_{timestamp}.wav"
            dest_path = os.path.join(custom_dir, dest_filename)
            try:
                shutil.copy2(file_path, dest_path)
            except Exception as ex:
                QMessageBox.warning(self, "上传失败", f"复制文件失败：{ex}")
                return
        else:
            try:
                import imageio_ffmpeg
                import subprocess
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                dest_filename = f"{name}_{timestamp}.wav"
                dest_path = os.path.join(custom_dir, dest_filename)
                cmd = [ffmpeg, "-y", "-i", file_path,
                       "-ar", "44100", "-ac", "1", "-sample_fmt", "s16",
                       dest_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr[-300:])
            except ImportError:
                try:
                    import soundfile as sf
                    data, sr = sf.read(file_path)
                    if len(data.shape) > 1:
                        data = data.mean(axis=1)
                    dest_filename = f"{name}_{timestamp}.wav"
                    dest_path = os.path.join(custom_dir, dest_filename)
                    sf.write(dest_path, data, sr, subtype='PCM_16')
                except ImportError:
                    QMessageBox.warning(self, "格式不支持",
                        "仅支持 WAV 格式。请安装 imageio-ffmpeg 或 soundfile 库。")
                    return
                except Exception as ex:
                    QMessageBox.warning(self, "格式转换失败",
                        f"音频格式转换失败：{ex}\n请尝试上传 WAV 格式。")
                    return
            except Exception as ex:
                QMessageBox.warning(self, "格式转换失败",
                    f"音频格式转换失败：{ex}\n请尝试上传 WAV 格式。")
                return

        rel_path = f"assets/sounds/custom/{dest_filename}"
        try:
            self.noise_dao.add(name, rel_path, self._current_category, is_builtin=0)
        except Exception as ex:
            QMessageBox.warning(self, "上传失败", f"保存到数据库失败：{ex}")
            return

        self._show_tab(self._current_category)

    def _save_settings(self):
        """保存开关设置到数据库。"""
        try:
            self.settings_dao.set("bg_music_enabled",
                "true" if self.cb_bg_enabled.isChecked() else "false")
            self.settings_dao.set("auto_play_on_start",
                "true" if self.cb_auto_play.isChecked() else "false")
        except Exception:
            pass

    def reject(self):
        """X 按钮或 ESC 关闭时也保存设置。"""
        self._save_settings()
        super().reject()

    def _on_close(self):
        """关闭按钮：保存设置后关闭。"""
        self._save_settings()
        self.accept()


class CloseConfirmDialog(_CardDialog):
    """关闭窗口时的退出确认对话框（提醒窗口接口）。

    - 默认动作为"退出程序"（默认按钮，回车即触发）。
    - 提供"最小化到托盘"作为次选，保留托盘常驻能力。
    - 含"不再提醒"复选框：勾选后点击退出，下次点击叉号将直接退出，
      对应设置项 `confirm_on_close` 置为 "false"（可在设置页重新开启）。

    结果读取：
        dlg.exec()          # 阻塞
        dlg.action          # "exit" | "tray" | "cancel"
        dlg.dont_remind     # bool，是否勾选"不再提醒"
    """

    ACTION_EXIT = "exit"
    ACTION_TRAY = "tray"
    ACTION_CANCEL = "cancel"

    def __init__(self, parent=None):
        super().__init__("退出青柠待办", "确认要关闭窗口吗？")
        self.action = self.ACTION_CANCEL
        self.dont_remind = False
        t = get_current_theme()

        tip = QLabel("你可以直接退出程序，或最小化到系统托盘继续后台运行。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"font-size:13px; color:{t.text_muted};")
        self.body.addWidget(tip)

        # 不再提醒复选框
        self.cb_dont_remind = QCheckBox("  不再提醒（下次点击叉号直接退出）")
        self.cb_dont_remind.setStyleSheet(
            f"QCheckBox{{font-size:13px; color:{t.text}; padding:6px 0;}}"
            f"QCheckBox::indicator{{width:18px; height:18px; border-radius:4px;"
            f" border:2px solid {t.border};}}"
            f"QCheckBox::indicator:checked{{background:{t.primary};"
            f" border-color:{t.primary};}}")
        self.body.addWidget(self.cb_dont_remind)

        # 底部按钮：最小化到托盘（次选）+ 退出程序（默认）
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_tray = ghost_button("最小化到托盘", on_click=self._on_tray)
        btn_tray.setFixedHeight(32)
        btn_tray.setStyleSheet(
            f"QPushButton#ghost{{padding:0 12px; font-size:12px; min-width:0;}}")
        btn_row.addWidget(btn_tray)
        self._btn_exit = primary_button("退出程序", on_click=self._on_exit)
        self._btn_exit.setDefault(True)
        self._btn_exit.setAutoDefault(True)
        self._btn_exit.setFixedHeight(32)
        self._btn_exit.setStyleSheet(
            f"QPushButton#primary{{padding:0 12px; font-size:12px; min-width:0;}}")
        btn_row.addWidget(self._btn_exit)
        self.body.addLayout(btn_row)

        self.setFixedWidth(400)

    def _on_exit(self):
        self.action = self.ACTION_EXIT
        self.dont_remind = self.cb_dont_remind.isChecked()
        self.accept()

    def _on_tray(self):
        self.action = self.ACTION_TRAY
        self.dont_remind = self.cb_dont_remind.isChecked()
        self.accept()

    def reject(self):
        # 叉号/ESC 关闭对话框：视为取消，不退出也不最小化
        self.action = self.ACTION_CANCEL
        super().reject()
