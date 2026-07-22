"""待办清单页面（PyQt6）。

支持：普通待办、养习惯类型显示与操作、右键上下文菜单、拖拽排序、更多设置、自定义背景图。
"""
import datetime
import json
import os
import sys

from PyQt6.QtCore import Qt, QMimeData, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QTimeEdit, QToolButton,
    QVBoxLayout, QWidget, QFileDialog, QMessageBox,
)

from src.theme import get_current_theme
from src.ui_qt.dialogs import TodoDialog, GroupDialog, MoreTodoSettingsDialog
from src.ui_qt.icons import icon
from src.ui_qt.pages import PageBase
from src.ui_qt.widgets import (
    badge, combo_box, hero_banner, primary_button, ghost_button,
    section_title, line_edit, PlusMinusTimeEdit, RoundedCard,
)

TIMER_TYPES = {0: "普通番茄钟", 1: "正计时", 2: "倒计时", 3: "严格模式"}
HABIT_TIMER_TYPES = {0: "倒计时", 1: "正计时", 2: "不计时"}
TYPE_LABELS = {0: "普通", 1: "养习惯", 2: "定目标"}
TYPE_ICONS = {0: "timer", 1: "habit", 2: "goal_flag"}
PRIORITY = ["普通", "重要", "紧急"]  # 用于卡片描述行

# 拖拽 MIME 类型
_TODO_MIME = "application/x-todo-sort"


class _TodoCard(QFrame):
    """单个待办卡片，支持拖拽排序与右键菜单。"""

    def __init__(self, page, td, groups):
        super().__init__()
        self.page = page
        self.td = td
        self.groups = groups
        self.setAcceptDrops(True)
        # 禁止 Qt 自动填充背景，避免 paintEvent 之前绘制直角背景
        self.setAutoFillBackground(False)
        self._drag_start = None
        self._build_ui()

    def _build_ui(self):
        t = get_current_theme()
        td = self.td
        done = td["status"] == 1
        todo_type = td.get("type", 0)
        mins = td["duration"] // 60
        gname = self.groups.get(td.get("group_id")) or "未分类"

        # 优先加载自定义背景图：用于决定文字配色（有背景时统一白色系，保证可读性）
        self._bg_pixmap = self._load_bg_pixmap(td)
        has_bg = self._bg_pixmap is not None and not self._bg_pixmap.isNull()

        # 文字配色：有背景时用白色系，呈现透明卡片的通透效果
        if has_bg:
            title_color = "#FFFFFF"
            desc_color = "rgba(255,255,255,0.88)"
            menu_icon_color = "#FFFFFF"
        else:
            title_color = t.text
            desc_color = t.text_muted
            menu_icon_color = t.text_muted

        # 完成线：默认完成待办显示删除线；开启「不划完成线」则不显示
        try:
            no_strike = (self.page.state.settings_dao.get(
                "no_strikethrough", "false") == "true")
        except Exception:
            no_strike = False
        strike = done and not no_strike
        # 标题：font-size:15px, font-weight:600
        title = QLabel(td["title"])
        title.setStyleSheet(
            f"font-size:15px; font-weight:600; color:{title_color};"
            + ("text-decoration:line-through;" if strike else ""))

        # 描述行：计时类型、时长等，font-size:12px
        timer_label_text = (HABIT_TIMER_TYPES.get(td.get("timer_type", 0), "未知")
                            if todo_type == 1
                            else TIMER_TYPES.get(td.get("timer_type", 0), "未知"))
        desc_parts = [timer_label_text, f"{mins} 分钟"]
        priority = td.get("priority", 0) or 0
        if priority > 0 and priority < len(PRIORITY):
            desc_parts.insert(0, PRIORITY[priority])
        desc_text = "  ·  ".join(desc_parts)
        desc = QLabel(desc_text)
        desc.setObjectName("subtle")
        desc.setStyleSheet(f"font-size:12px; color:{desc_color};")

        # 徽章行（分组 + 类型）
        # 有背景图时使用 overlay 样式（半透明白底+白字），确保可读性
        badge_style = "overlay" if has_bg else "default"
        meta = QHBoxLayout()
        meta.setSpacing(8)
        meta.addWidget(badge(gname, style=badge_style))
        type_icon_name = TYPE_ICONS.get(todo_type, "timer")
        type_label = TYPE_LABELS.get(todo_type, "普通")
        if todo_type == 1:
            meta.addWidget(badge(type_label, style=badge_style))
            habit_unit = td.get("habit_unit") or ""
            habit_target = td.get("habit_target") or ""
            if habit_target:
                habit_lbl = QLabel(f"{habit_target} {habit_unit}")
                if has_bg:
                    habit_lbl.setStyleSheet(
                        f"font-size:12px; color:#FFFFFF; padding:2px 8px;"
                        f"background:rgba(255,255,255,0.22); border-radius:999px;"
                        f"border:1px solid rgba(255,255,255,0.35); max-height:20px;")
                else:
                    habit_lbl.setStyleSheet(
                        f"font-size:12px; color:{desc_color}; padding:2px 8px;"
                        f"background:{t.primary_soft}; border-radius:999px;"
                        f"border:none; max-height:20px;")
                habit_lbl.setFixedHeight(24)
                meta.addWidget(habit_lbl)
        meta.addWidget(badge(timer_label_text, style=badge_style))
        meta.addStretch(1)

        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(title)
        left.addWidget(desc)
        left.addLayout(meta)

        # 菜单按钮（紧凑）
        btn = QToolButton()
        btn.setIcon(icon("more", menu_icon_color, 20))
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setAutoRaise(True)
        btn.setFixedSize(32, 32)  # 紧凑尺寸
        # 隐藏QToolButton自带的下拉箭头，避免与三点图标重叠
        btn.setStyleSheet(
            f"QToolButton{{border:none; border-radius:6px; background:transparent;}}"
            f"QToolButton:hover{{background:{t.surface};}}"
            f"QToolButton::menu-indicator{{image:none; width:0px;}}")
        btn.setArrowType(Qt.ArrowType.NoArrow)
        menu = QMenu(btn)
        # 圆角卡片风格菜单
        menu.setStyleSheet(
            f"QMenu{{background:{t.surface}; border:1px solid {t.border}; "
            f"border-radius:{t.radius_md}px; padding:6px 4px;}}"
            f"QMenu::item{{padding:8px 20px; border-radius:{t.radius_sm}px; "
            f"font-size:13px;}}"
            f"QMenu::item:selected{{background:{t.primary_soft}; color:{t.text};}}"
            f"QMenu::separator{{height:1px; background:{t.divider}; "
            f"margin:4px 12px;}}")
        # 菜单项
        menu.addAction(icon("play", t.text_muted, 16), "开始专注",
                       lambda: self.page._start_focus(td))
        menu.addAction(icon("edit", t.text_muted, 16), "编辑",
                       lambda: self.page._edit_todo(td))
        menu.addAction(icon("check", t.text_muted, 16),
                       "标记完成" if not done else "标记进行中",
                       lambda: self.page._toggle_done(td))
        menu.addSeparator()
        # 更多设置
        menu.addAction(icon("settings", t.text_muted, 16), "更多设置",
                       lambda: self.page._open_more_settings(td))
        # 更换背景
        menu.addAction(icon("image", t.text_muted, 16), "更换背景",
                       lambda: self.page._change_background(td))
        # 定时提醒
        menu.addAction(icon("bell", t.text_muted, 16), "定时提醒",
                       lambda: self.page._set_remind(td))
        # 打卡（仅养习惯）
        if todo_type == 1:
            menu.addAction(icon("check", t.text_muted, 16), "打卡",
                           lambda: self.page._habit_checkin(td))
        # 专注历史记录
        menu.addAction(icon("history", t.text_muted, 16), "专注历史记录",
                       lambda: self.page._show_focus_history(td))
        menu.addSeparator()
        # 排序子菜单
        sort_menu = menu.addMenu(icon("sort", t.text_muted, 16), "排序|移动")
        sort_menu.addAction(icon("top", t.text_muted, 16), "置顶",
                           lambda: self.page._sort_todo(td, "top"))
        sort_menu.addAction(icon("up", t.text_muted, 16), "上移",
                           lambda: self.page._sort_todo(td, "up"))
        sort_menu.addAction(icon("down", t.text_muted, 16), "下移",
                           lambda: self.page._sort_todo(td, "down"))
        # 移动到...
        groups = self.page.group_dao.list()
        for g in groups:
            sort_menu.addAction(
                icon("move", t.text_muted, 16),
                f"移动到 {g['name']}",
                lambda gid=g['id']: self.page._move_to_group(td, gid))
        menu.addSeparator()
        menu.addAction(icon("trash", t.text_muted, 16), "删除",
                       lambda: self.page._delete_todo(td))
        btn.setMenu(menu)

        tick = QFrame()
        tick.setFixedSize(4, 48)  # 加长以匹配含 badge 行的内容高度
        tick.setStyleSheet(
            f"background:{t.primary}; border-radius:999px;"
        )

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(tick)
        row.addLayout(left, 1)
        row.addWidget(btn)

        self.setObjectName("todoCard")
        # 不使用 #panel 的 QSS 样式，避免 QSS border-radius 不能裁剪背景
        # 导致四角直角阴影；由 paintEvent 完全接管圆角背景和边框绘制
        self.setStyleSheet("QFrame#todoCard{background:transparent; border:none;}")
        # 统一内边距 14x12
        c_lay = QHBoxLayout(self)
        c_lay.setContentsMargins(14, 12, 12, 12)
        c_lay.addLayout(row)

        # 右键上下文菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu = menu

    def _show_context_menu(self, pos):
        """显示右键上下文菜单。"""
        self._context_menu.exec(self.mapToGlobal(pos))

    def _load_bg_pixmap(self, td):
        """加载待办自定义背景图，兼容绝对路径与项目相对路径。

        待办自身未设置背景时，回退使用全局背景海报（设置页 app_background），
        使背景海报能生效到待办列表每行。
        """
        bg_path = td.get("background_path")
        if not bg_path:
            try:
                bg_path = (self.page.state.settings_dao.get(
                    "app_background", "") or "")
            except Exception:
                bg_path = ""
        if not bg_path:
            return None
        if os.path.isabs(bg_path) and os.path.exists(bg_path):
            return QPixmap(bg_path)
        # 尝试相对路径（相对于项目根目录）
        base = getattr(sys, '_MEIPASS', None)
        if base:
            project_root = base
        else:
            # todo_page.py 位于 src/ui_qt/pages/，向上 4 层到项目根
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))))
        abs_path = os.path.join(project_root, bg_path)
        if os.path.exists(abs_path):
            return QPixmap(abs_path)
        # 兼容：若原路径直接存在也尝试加载
        if os.path.exists(bg_path):
            return QPixmap(bg_path)
        return None

    def paintEvent(self, ev):
        """有背景图时自绘圆角背景 + 半透明遮罩，呈现透明卡片风格。

        无背景图时，先设置圆角裁剪路径再调用 super().paintEvent()，
        确保 QSS 的 background 和 border 都被裁剪到圆角内，
        避免四角出现直角阴影。
        """
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                t = get_current_theme()
                radius = t.radius_md
                rect = QRectF(self.rect())
                # 先用父窗口背景色填充整个矩形，覆盖 Qt 在 paintEvent 之前
                # 可能绘制的直角背景，消除四角直角
                painter.fillRect(self.rect(), QColor(t.surface))
                path = QPainterPath()
                path.addRoundedRect(rect, radius, radius)
                painter.setClipPath(path)
                # 背景图（等比例缩放填充）
                scaled = self._bg_pixmap.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
                # 半透明遮罩（左深右浅），保证白色文字可读且保留通透感
                gradient = QLinearGradient(0, 0, float(self.width()), 0)
                gradient.setColorAt(0, QColor(0, 0, 0, 135))
                gradient.setColorAt(0.55, QColor(0, 0, 0, 80))
                gradient.setColorAt(1, QColor(0, 0, 0, 36))
                painter.fillRect(self.rect(), gradient)
                # 细描边提升质感
                painter.setClipping(False)
                pen = QPen(QColor(255, 255, 255, 46))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(
                    rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
            finally:
                painter.end()
        else:
            # 无背景图：完全手动绘制圆角背景和边框
            t = get_current_theme()
            radius = t.radius_md
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # 先用父窗口背景色填充整个矩形，覆盖 Qt 在 paintEvent 之前
            # 可能绘制的直角背景（surface_variant），消除四角直角
            painter.fillRect(self.rect(), QColor(t.surface))
            # 然后只在圆角路径内绘制卡片背景色
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), radius, radius)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.surface_variant))
            painter.drawPath(path)
            # 绘制边框
            pen = QPen(QColor(t.border), 1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                radius, radius)
            painter.end()

    # ---------- 双击进入专注 ----------
    def mouseDoubleClickEvent(self, ev):
        """双击卡片：进入该待办对应的专注计时页面。"""
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.page._start_focus(self.td)
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    # ---------- 拖拽排序 ----------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_start = ev.pos()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if not (ev.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start is None:
            return
        if (ev.pos() - self._drag_start).manhattanLength() < 20:
            return
        drag = self._create_drag()
        if drag:
            drag.exec(Qt.DropAction.MoveAction)

    def _create_drag(self):
        from PyQt6.QtGui import QDrag
        mime = QMimeData()
        mime.setData(_TODO_MIME, str(self.td["id"]).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        # 创建拖拽预览
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())
        return drag

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(_TODO_MIME):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(_TODO_MIME):
            return
        source_id = int(ev.mimeData().data(_TODO_MIME).data().decode())
        target_id = self.td["id"]
        if source_id == target_id:
            return
        ev.acceptProposedAction()
        self.page._reorder_todo(source_id, target_id)


class _GroupHeader(QFrame):
    """待办集分组标题（可点击折叠/展开）。"""

    def __init__(self, name, expanded, on_toggle, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._on_toggle = on_toggle
        self._build(name)

    def _build(self, name):
        from src.theme import get_current_theme
        t = get_current_theme()
        self.setObjectName("groupHeader")
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(36)
        # QSS 设为透明，由 paintEvent 绘制圆角背景和边框
        self.setStyleSheet("QFrame#groupHeader{background:transparent; border:none;}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        self._chevron = QLabel("▾" if self._expanded else "▸")
        self._chevron.setStyleSheet(f"font-size:14px; color:{t.text_muted};")
        self._name = QLabel(name)
        self._name.setStyleSheet(f"font-size:14px; font-weight:600; color:{t.text};")
        lay.addWidget(self._chevron)
        lay.addWidget(self._name)
        lay.addStretch(1)

    def mousePressEvent(self, ev):
        self._on_toggle()
        super().mousePressEvent(ev)

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._chevron.setText("▾" if expanded else "▸")

    def paintEvent(self, ev):
        """手动绘制圆角背景和边框，先用父窗口背景色覆盖整个矩形，
        再用 drawPath 只在圆角路径内绘制卡片背景色，消除四角直角。
        """
        t = get_current_theme()
        radius = t.radius_md
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 先用父窗口背景色填充整个矩形，覆盖 Qt 可能绘制的直角背景
        painter.fillRect(self.rect(), QColor(t.surface))
        # 然后只在圆角路径内绘制卡片背景色
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.surface_variant))
        painter.drawPath(path)
        # 绘制边框
        pen = QPen(QColor(t.border), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
            radius, radius)
        painter.end()


class TodoPage(PageBase):
    def __init__(self, state):
        self.todo_dao = state.todo_dao
        self.group_dao = state.group_dao
        self.focus_dao = state.focus_record_dao
        self.habit_checkin_dao = state.habit_checkin_dao
        self.filter_group = "all"
        self.filter_status = 0
        super().__init__(state)

    def _build(self):
        t = self._t
        # 标题 + 按钮
        header = QHBoxLayout()
        header.addWidget(section_title("待办清单", "checklist"))
        header.addStretch(1)
        header.addWidget(ghost_button("待办集",
                                       on_click=self._add_group, min_w=100),
                          0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(primary_button("新建待办",
                                         on_click=self._add_todo, min_w=100),
                          0, Qt.AlignmentFlag.AlignVCenter)
        self._lay.addLayout(header)

        # Hero
        self._lay.addWidget(hero_banner("规划今日之事，集于方寸之间",
                                        "井然有序，专注致远"))

        # 工具栏
        groups = [("all", "全部")] + [(str(g["id"]), g["name"])
                                      for g in self.group_dao.list()]
        self.cb_group = combo_box(groups, value=self.filter_group,
                                   on_change=self._on_filter, min_w=180)
        self.cb_status = combo_box([("0", "进行中"), ("1", "已完成"), ("2", "全部")],
                                    value=self.filter_status,
                                    on_change=self._on_filter, min_w=140)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        toolbar.addWidget(self.cb_group)
        toolbar.addWidget(self.cb_status)
        # 搜索框：默认隐藏，开启「待办较多时可下拉搜索」且列表超阈值时显示
        self.ed_search = line_edit("搜索待办…")
        self.ed_search.setMaximumWidth(200)
        self.ed_search.setVisible(False)
        self.ed_search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.ed_search)
        toolbar.addStretch(1)

        # 列表
        self.list_card = RoundedCard(radius=24)
        # 不使用 #card 的 QSS 样式，避免 QSS border-radius 与 paintEvent 冲突
        # 导致四角出现直角阴影；RoundedCard.paintEvent 已自行绘制圆角背景和边框
        self.list_lay = QVBoxLayout(self.list_card)
        self.list_lay.setContentsMargins(18, 18, 18, 18)
        self.list_lay.setSpacing(8)
        self.list_lay.insertLayout(0, toolbar)
        self._lay.addWidget(self.list_card)

        self._refresh_list()

    def refresh(self):
        self._refresh_list()

    def _on_filter(self):
        self.filter_group = self.cb_group.currentData()
        self.filter_status = int(self.cb_status.currentData())
        self._refresh_list()
        # 重置滚动位置到顶部，避免切换筛选后内容偏移
        self.verticalScrollBar().setValue(0)

    def _refresh_list(self):
        t = self._t
        # 清除列表（保留工具栏）
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(1)
            if item.widget():
                w = item.widget()
                w.setParent(None)  # 立即从父控件移除，避免布局残留
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        status = None if self.filter_status == 2 else self.filter_status
        gid = None if self.filter_group == "all" else int(self.filter_group)
        todos = self.todo_dao.list(status=status, group_id=gid)
        group_names = {g["id"]: g["name"] for g in self.group_dao.list()}
        self._current_todos = todos

        # 搜索框显隐：开启「待办较多时可下拉搜索」且当前列表数量超过阈值才显示
        try:
            search_enabled = self.state.settings_dao.get(
                "enable_search", "true") == "true"
        except Exception:
            search_enabled = True
        self.ed_search.setVisible(search_enabled and len(todos) > 8)

        # 固定排序：按优先级固定排序，新添加不置顶（覆盖默认的「新建置顶」）
        if self._get_setting("fixed_sort", "false") == "true":
            todos = sorted(
                todos,
                key=lambda td: (-(td.get("priority", 0) or 0),
                                td.get("sort_order", 0) or 0,
                                td["id"]))

        # 搜索过滤：标题包含关键字（不区分大小写）
        kw = (getattr(self, "_search_text", "") or "").strip().lower()
        if kw:
            todos = [td for td in todos
                     if kw in (td.get("title") or "").lower()]

        if not todos:
            # 空状态提示
            empty = QLabel("暂无待办，点击右上角「+」新建")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{t.text_muted}; font-size:14px; padding:40px 0;")
            self.list_lay.addWidget(empty)
            self.list_lay.addStretch(1)
            return

        # 指定单个待办集：直接平铺（gid 已约束范围，无需折叠分组）
        if gid is not None:
            for td in todos:
                card = _TodoCard(self, td, group_names)
                self.list_lay.addWidget(card)
            self.list_lay.addStretch(1)
            return

        # 全部视图：按待办集分组，可折叠（待办集展开记忆）
        self._render_grouped(todos, group_names)
        self.list_lay.addStretch(1)

    # ---------- 待办集分组折叠 + 展开记忆 ----------
    def _render_grouped(self, todos, group_names):
        """按待办集分组渲染可折叠区块。"""
        grouped = {}
        for td in todos:
            key = td.get("group_id") or 0
            grouped.setdefault(key, []).append(td)
        # 排序：已有待办集按 group_dao 顺序，未分类置后
        order = [g["id"] for g in self.group_dao.list() if g["id"] in grouped]
        if 0 in grouped:
            order.append(0)
        for k in list(grouped.keys()):
            if k not in order:
                order.append(k)

        remember = self._get_setting("remember_list_expand", "true") == "true"
        saved = self._load_expand_state() if remember else {}
        for gid_key in order:
            items = grouped.get(gid_key)
            if not items:
                continue
            name = "未分类" if gid_key == 0 else group_names.get(gid_key, "未分类")
            expanded = saved.get(str(gid_key), True) if remember else True
            self._build_group_section(gid_key, name, items, expanded, group_names)

    def _build_group_section(self, group_id, name, items, expanded, group_names):
        """构建一个待办集折叠区块（标题 + 容器）。"""
        container = QWidget()
        clay = QVBoxLayout(container)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.setSpacing(8)
        for td in items:
            clay.addWidget(_TodoCard(self, td, group_names))

        header = _GroupHeader(
            name, expanded,
            lambda: self._toggle_group(group_id, header, container))
        self.list_lay.addWidget(header)
        self.list_lay.addWidget(container)
        # 必须在 addWidget（reparent）之后再 setVisible，
        # 否则容器作为无父 widget 会以顶层窗口闪现
        container.setVisible(expanded)

    def _toggle_group(self, group_id, header, container):
        """折叠/展开某个待办集，并在开启记忆时持久化状态。"""
        new_state = not container.isVisible()
        container.setVisible(new_state)
        header.set_expanded(new_state)
        if self._get_setting("remember_list_expand", "true") == "true":
            self._save_expand_state(group_id, new_state)

    def _load_expand_state(self):
        """读取待办集展开记忆（group_id -> bool 的 JSON）。"""
        raw = self._get_setting("group_expand_state", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_expand_state(self, group_id, expanded):
        """持久化某个待办集的展开/折叠状态。"""
        state = self._load_expand_state()
        state[str(group_id)] = bool(expanded)
        try:
            self.state.settings_dao.set(
                "group_expand_state", json.dumps(state, ensure_ascii=False))
        except Exception:
            pass

    # ---------- 原有操作 ----------
    def _start_focus(self, td):
        """进入专注计时页面并加载指定待办（建立专注与待办的关联）。"""
        cb = getattr(self.state, "on_start_focus", None)
        if callable(cb):
            # on_start_focus 内部会切换到专注页并 load_todo(td)
            cb(td)
        else:
            # 回退：至少切换到专注页
            self.state.navigate("focus")

    def _toggle_done(self, td):
        if td["status"] == 1:
            self.todo_dao.update(td["id"], status=0, completed_at=None)
        else:
            self.todo_dao.complete(td["id"])
        self._refresh_list()

    def _delete_todo(self, td):
        ret = QMessageBox.question(
            self, "确认删除", f"确定要删除待办「{td['title']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.todo_dao.delete(td["id"])
            self._refresh_list()

    def _add_group(self):
        dlg = GroupDialog(self.state, self)
        dlg.on_saved = self._on_saved
        dlg.exec()

    def _add_todo(self):
        dlg = TodoDialog(self.state, None, self)
        dlg.on_saved = self._on_saved
        dlg.exec()

    def _edit_todo(self, td):
        dlg = TodoDialog(self.state, td, self)
        dlg.on_saved = self._on_saved
        dlg.exec()

    def _on_saved(self):
        self._refresh_list()

    # ---------- 更多设置 ----------
    def _open_more_settings(self, td):
        t = self._t
        init_values = {
            "hide_after_complete": td.get("hide_after_complete", 0),
            "is_amway_mode_exempted": td.get("is_amway_mode_exempted", 0),
            "loop_enabled": int(td.get("loop_count", 1) > 1),
            "custom_break_duration": td.get("custom_break_duration"),
        }
        dlg = MoreTodoSettingsDialog(t, init_values, self)
        if dlg.exec():
            values = dlg.values
            self.todo_dao.update(td["id"],
                                hide_after_complete=values["hide_after_complete"],
                                is_amway_mode_exempted=values["is_amway_mode_exempted"],
                                custom_break_duration=values["custom_break_duration"])
            if values.get("loop_enabled"):
                loop_count = td.get("loop_count", 1)
                if loop_count < 2:
                    loop_count = 2
                self.todo_dao.update(td["id"], loop_count=loop_count)
            self._refresh_list()

    # ---------- 更换背景 ----------
    def _change_background(self, td):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.todo_dao.update(td["id"], background_path=path)
            self._refresh_list()

    # ---------- 定时提醒 ----------
    def _set_remind(self, td):
        t = self._t
        dlg = _RemindDialog(t, td.get("remind_time"), self)
        if dlg.exec():
            self.todo_dao.update(td["id"], remind_time=dlg.time_value)
            self._refresh_list()

    # ---------- 习惯打卡 ----------
    def _habit_checkin(self, td):
        today = datetime.date.today()
        existing = self.habit_checkin_dao.get_today(td["id"], today)
        if existing:
            QMessageBox.information(
                self, "已打卡",
                f"「{td['title']}」今日已完成打卡。")
            return
        now = datetime.datetime.now()
        actual = td.get("habit_target")
        self.habit_checkin_dao.checkin(td["id"], today, now, actual)
        QMessageBox.information(
            self, "打卡成功",
            f"「{td['title']}」今日打卡成功！")
        self._refresh_list()

    # ---------- 专注历史记录 ----------
    def _show_focus_history(self, td):
        t = self._t
        records = self.focus_dao.list_recent(100)
        # 筛选该待办的记录
        todo_records = [r for r in records if r.get("todo_id") == td["id"]]
        dlg = _FocusHistoryDialog(t, td["title"], todo_records, self)
        dlg.exec()

    # ---------- 排序/移动 ----------
    def _sort_todo(self, td, direction):
        todos = self._get_current_todos()
        ids = [t["id"] for t in todos]
        idx = ids.index(td["id"])
        if direction == "top":
            new_idx = 0
        elif direction == "up" and idx > 0:
            new_idx = idx - 1
        elif direction == "down" and idx < len(ids) - 1:
            new_idx = idx + 1
        else:
            return
        # 移动元素
        ids.pop(idx)
        ids.insert(new_idx, td["id"])
        # 批量更新 sort_order
        for order, tid in enumerate(ids):
            self.todo_dao.update(tid, sort_order=order)
        self._refresh_list()

    def _move_to_group(self, td, group_id):
        self.todo_dao.update(td["id"], group_id=group_id)
        self._refresh_list()

    def _reorder_todo(self, source_id, target_id):
        """拖拽排序：将 source 移动到 target 之前。"""
        todos = self._get_current_todos()
        ids = [t["id"] for t in todos]
        if source_id not in ids or target_id not in ids:
            return
        ids.remove(source_id)
        target_idx = ids.index(target_id)
        ids.insert(target_idx, source_id)
        for order, tid in enumerate(ids):
            self.todo_dao.update(tid, sort_order=order)
        self._refresh_list()

    def _get_current_todos(self):
        """获取当前筛选后的待办列表。"""
        status = None if self.filter_status == 2 else self.filter_status
        gid = None if self.filter_group == "all" else int(self.filter_group)
        return self.todo_dao.list(status=status, group_id=gid)

    # ---------- 设置读取辅助 ----------
    def _get_setting(self, key: str, default: str = "") -> str:
        """从 settings 表读取配置，异常时返回默认值。"""
        try:
            return str(self.state.settings_dao.get(key, default) or default)
        except Exception:
            return default

    def _on_search(self, text: str):
        """搜索框文本变化：记录关键字并刷新列表。"""
        self._search_text = text
        self._refresh_list()


class _RemindDialog(QDialog):
    """定时提醒设置对话框。"""

    def __init__(self, theme, existing_time, parent=None):
        super().__init__(parent)
        self.t = theme
        self.setWindowTitle("设置定时提醒")
        self.setFixedSize(300, 220)
        self.time_value = None
        self._build(existing_time)

    def _build(self, existing_time):
        t = self.t
        # 对话框样式：包含自身外观 + 子控件按钮样式，确保 QSS 正确级联
        # 注意：QDialog 是顶层窗口，不设置 border/border-radius，否则会在
        # 矩形窗口内部绘制额外的圆角方框
        self.setStyleSheet(f"""
            QDialog {{
                background: {t.surface};
            }}
            QPushButton#primary {{
                background: {t.primary};
                color: {t.on_primary};
                border: none;
                border-radius: {t.radius_sm}px;
                padding: 6px 20px;
                font-weight: 500;
                font-size: 13px;
                min-height: 34px;
                min-width: 72px;
            }}
            QPushButton#primary:hover {{ opacity: 0.9; }}
            QPushButton#primary:pressed {{ background: {t.primary_pressed}; }}
            QPushButton#ghost {{
                background: transparent;
                color: {t.text};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                padding: 6px 20px;
                font-weight: 500;
                font-size: 13px;
                min-height: 34px;
                min-width: 72px;
            }}
            QPushButton#ghost:hover {{
                background: {t.surface_variant};
                border-color: {t.text_muted};
            }}
            QPushButton#ghost:pressed {{
                background: {t.surface_variant};
                color: {t.text_muted};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        self.time_edit = PlusMinusTimeEdit()
        self.time_edit.setFixedWidth(180)
        if existing_time:
            if isinstance(existing_time, datetime.datetime):
                from PyQt6.QtCore import QTime
                self.time_edit.setTime(QTime(existing_time.hour, existing_time.minute))
        else:
            from PyQt6.QtCore import QTime
            self.time_edit.setTime(QTime(20, 0))
        root.addWidget(self.time_edit, alignment=Qt.AlignmentFlag.AlignCenter)

        # 按钮行：右对齐，统一高度
        h = QHBoxLayout()
        h.setSpacing(12)
        h.addStretch(1)
        cancel = ghost_button("取消", on_click=self.reject, min_w=88)
        ok = primary_button("确定", on_click=self._on_ok, min_w=88)
        # 强制对齐：同一行垂直居中
        h.addWidget(cancel, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(ok, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(h)

    def _on_ok(self):
        time_val = self.time_edit.time()
        today = datetime.date.today()
        self.time_value = datetime.datetime.combine(today, time_val.toPyTime())
        self.accept()


class _FocusHistoryDialog(QDialog):
    """专注历史记录对话框。"""

    def __init__(self, theme, todo_title, records, parent=None):
        super().__init__(parent)
        self.t = theme
        self.setWindowTitle(f"专注历史记录 - {todo_title}")
        self.setMinimumSize(520, 360)
        self._build(todo_title, records)

    def _build(self, todo_title, records):
        t = self.t
        self.setStyleSheet(f"background:{t.surface};")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel(f"「{todo_title}」的专注历史")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{t.text};")
        root.addWidget(title)

        # 列表容器（内联样式，不使用 objectName="panel" 避免全局 QSS 覆盖）
        list_frame = QFrame()
        list_frame.setStyleSheet(
            f"background:transparent; border:none;")
        list_lay = QVBoxLayout(list_frame)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(8)

        if not records:
            empty = QLabel("暂无专注记录")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{t.text_muted}; font-size:14px; padding:40px 0;")
            list_lay.addWidget(empty)
        else:
            for r in records:
                # 卡片样式：QFrame 包裹，surface_variant 背景，圆角，内边距 12,8,12,8
                card = QFrame()
                card.setStyleSheet(
                    f"background:{t.surface_variant}; border:none; "
                    f"border-radius:{t.radius_md}px;")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(12, 8, 12, 8)
                card_lay.setSpacing(4)

                # 第一行：日期 + 状态徽章
                row1 = QHBoxLayout()
                row1.setSpacing(8)
                start = r.get("start_time")
                if start:
                    if isinstance(start, datetime.datetime):
                        date_str = start.strftime("%Y-%m-%d %H:%M")
                    else:
                        # 尝试解析字符串并格式化，确保不显示微秒
                        try:
                            parsed = datetime.datetime.fromisoformat(str(start))
                            date_str = parsed.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, TypeError):
                            # 无法解析，去掉微秒部分并截取到分钟
                            s = str(start).split(".")[0]
                            date_str = s[:16] if len(s) >= 16 else s
                else:
                    date_str = ""
                lab_date = QLabel(date_str)
                lab_date.setStyleSheet(
                    f"color:{t.text}; font-size:13px; font-weight:500;")
                row1.addWidget(lab_date)
                row1.addStretch(1)

                # 状态徽章
                is_completed = r.get("is_completed", 1)
                status_text = "已完成" if is_completed else "未完成"
                status_color = t.success if is_completed else t.warning
                lab_status = QLabel(status_text)
                lab_status.setStyleSheet(
                    f"background:{status_color}; color:#fff; border-radius:999px; "
                    f"padding:2px 10px; font-size:11px; font-weight:600;")
                row1.addWidget(lab_status)
                card_lay.addLayout(row1)

                # 第二行：时长
                actual = r.get("actual_duration", 0)
                mins = actual // 60
                secs = actual % 60
                lab_dur = QLabel(f"专注时长 {mins}分{secs}秒")
                lab_dur.setStyleSheet(
                    f"color:{t.primary}; font-weight:600; font-size:13px;")
                card_lay.addWidget(lab_dur)

                list_lay.addWidget(card)

        root.addWidget(list_frame, 1)

        # 关闭按钮（右下角 ghost 样式）
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(ghost_button("关闭", on_click=self.accept))
        root.addLayout(h)
