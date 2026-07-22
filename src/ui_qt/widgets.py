"""通用 PyQt6 组件库（主题感知）。

设计语言「青柠晨露」——纯净冷白底 · 通透青柠绿 · 冷色点缀 · 专业炫酷。
所有组件读取全局当前主题令牌（src.theme.get_current_theme()），换肤时由
页面统一重建外观，无需逐控件重设样式（QSS 已通过 app.setStyleSheet 注入）。

v2 升级：
- 卡片：悬浮抬升投影（enter/leave 动态切换 shadow 强度）
- 主按钮：彩色发光投影（QGraphicsDropShadowEffect + 主色）
- 玻璃卡片：更精致的半透明 + 高光描边
- 徽章：渐变底色
- 分区标题：圆角图标块 + 渐变底
"""
from PyQt6.QtCore import Qt, QSize, QObject, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal, QEvent, QDate, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap, QIcon, QPainterPath
from PyQt6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDateEdit, QFrame,
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QListView,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QStyle, QVBoxLayout,
    QWidget,
)
from PyQt6 import sip

from src.theme import get_current_theme, hex_rgba
from src.tokens import shadow as shadow_tok, motion
from src.ui_qt.icons import icon


def _soft_shadow(widget: QWidget, blur=20, offset_y=4, alpha=28,
                 color: str = None) -> QGraphicsDropShadowEffect:
    """柔性投影：低对比度、大模糊半径，营造纸页叠放感。

    Args:
        color: 可选阴影颜色（十六进制）。不传则用半透明黑。
               传主色可产生「发光」效果。
    Returns:
        QGraphicsDropShadowEffect 实例（已绑定到 widget）。
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, offset_y)
    if color:
        rgb = _hex_to_rgb(color)
        if rgb:
            effect.setColor(QColor(rgb[0], rgb[1], rgb[2], alpha))
        else:
            effect.setColor(QColor(0, 0, 0, alpha))
    else:
        effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def _hex_to_rgb(hex_color: str):
    """'#RRGGBB' -> (r, g, b)。"""
    c = hex_color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return None
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return None


def on_color(hex_color: str, dark_text: str = "#1A1D23",
             light_text: str = "#FFFFFF") -> str:
    """P2 工厂: 根据背景色亮度自动选择黑/白前景色 (WCAG 风格).

    用于 badge、状态点、彩色按钮等「背景色动态」场景。
    使用 ITU-R BT.601 亮度公式 (0.299R + 0.587G + 0.114B), 阈值 0.55。
    """
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return light_text
    luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0
    return dark_text if luminance > 0.55 else light_text


class _CardHoverFilter(QObject):
    """卡片悬浮抬升效果：enter 时加深投影，leave 时恢复。

    通过事件过滤器动态调整 QGraphicsDropShadowEffect 的模糊半径和透明度，
    营造「卡片悬浮」的物理感。QSS 的 :hover 只能改边框，投影需在代码侧控制。

    修复: 继承 QObject 并实现 eventFilter, 避免内部类闭包造成的潜在 GC 风险。
    """

    def __init__(self, card_widget: QFrame, shadow_effect: QGraphicsDropShadowEffect):
        super().__init__(card_widget)  # parent=card, 由 Qt 自动保活
        self._card = card_widget
        self._effect = shadow_effect
        # 静态态参数（sm 级）
        self._rest_blur, self._rest_offset, self._rest_alpha = shadow_tok.sm
        # 悬浮态参数（md 级）
        self._hover_blur, self._hover_offset, self._hover_alpha = shadow_tok.md
        # 直接由 QObject parent 持有，无需额外引用
        self._card.installEventFilter(self)

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.Enter:
            self._apply(self._hover_blur, self._hover_offset, self._hover_alpha)
        elif et == QEvent.Type.Leave:
            self._apply(self._rest_blur, self._rest_offset, self._rest_alpha)
        return False  # 不吞掉事件

    def _apply(self, blur: int, offset: int, alpha: int) -> None:
        if not self._effect:
            return
        self._effect.setBlurRadius(blur)
        self._effect.setOffset(0, offset)
        c = self._effect.color()
        c.setAlpha(alpha)
        self._effect.setColor(c)


def card(parent: QWidget = None, shadow: bool = True) -> QFrame:
    """主题感知卡片：大圆角 + 柔和投影（纸页叠放感）+ 悬浮抬升。

    v2: 默认使用 sm 级投影（轻柔），鼠标悬浮时自动切换到 md 级（明显抬升），
    营造「卡片浮起」的物理反馈。

    修复: _CardHoverFilter 改为 QObject 子类, parent=card,
         由 Qt 对象树保活, 不再依赖额外属性引用。
    """
    f = QFrame(parent)
    f.setObjectName("card")
    if shadow:
        # 使用 sm 级投影作为静态态
        b, o, a = shadow_tok.sm
        effect = _soft_shadow(f, blur=b, offset_y=o, alpha=a)
        # _CardHoverFilter 的 QObject parent=f, Qt 自动保活
        f._hover_handler = _CardHoverFilter(f, effect)
    return f


class RoundedCard(QFrame):
    """圆角卡片：完全接管 paintEvent 绘制圆角背景和边框。

    不使用 QSS 的 background/border（通过不设置 objectName 避免），
    完全由 paintEvent 绘制，确保圆角外区域显示父窗口背景色而非直角阴影。
    """

    def __init__(self, radius: int = 24, parent: QWidget = None):
        super().__init__(parent)
        self._radius = radius
        # 关键：禁止 QFrame 自动填充背景，避免 Qt 在 paintEvent 之前
        # 绘制直角背景导致四角阴影
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def setRadius(self, radius: int):
        self._radius = radius
        self.update()

    def paintEvent(self, ev):
        t = get_current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 先用父窗口背景色填充整个矩形，覆盖 Qt 可能绘制的直角背景
        p.fillRect(self.rect(), QColor(t.bg))
        # 然后只在圆角路径内绘制卡片背景色
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.surface))
        p.drawPath(path)
        # 绘制边框
        pen = QPen(QColor(t.border), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                          self._radius, self._radius)


def glass_card(parent: QWidget = None, alpha: float = 0.92, blur: int = 32,
               offset_y: int = 8, alpha_shadow: int = 36) -> QFrame:
    """玻璃拟态卡片：半透明表面 + 高光描边 + 柔光投影。

    v2: 更高的模糊半径和更低的透明度，增强「轻盈悬浮」质感。
    用于对话框等需呈现「轻盈悬浮」质感的容器。
    """
    t = get_current_theme()
    f = QFrame(parent)
    f.setObjectName("glassCard")
    # 高光描边：浅色主题用白，深色主题用浅灰
    border_highlight = "rgba(255,255,255,0.6)" if t.name == "light" else "rgba(255,255,255,0.12)"
    f.setStyleSheet(
        f"#glassCard{{background:{hex_rgba(t.surface, alpha)};"
        f" border:1px solid {border_highlight};"
        f" border-radius:{t.radius_lg}px;}}")
    _soft_shadow(f, blur=blur, offset_y=offset_y, alpha=alpha_shadow)
    return f


def fade_in(widget: QWidget, duration: int = motion.base) -> None:
    """克制的入场动效：窗口透明度 0→1（ease-out）。

    仅作用于透明度，避免几何动画干扰布局；时长由 motion 令牌统一约束。
    """
    try:
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
    except Exception:
        return
    widget.setWindowOpacity(0.0)
    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    widget._fade_anim = anim  # 保活，避免被 GC


def primary_button(text: str, on_click=None, parent: QWidget = None,
                   icon_name: str = None, min_w: int = None) -> QPushButton:
    """主按钮：渐变底（与 ghost_button 宽高布局完全一致，仅颜色不同）。"""
    b = QPushButton(text, parent)
    b.setObjectName("primary")
    b.setFixedHeight(36)
    if icon_name:
        t_ = get_current_theme()
        b.setIcon(icon(icon_name, t_.on_primary))
        b.setIconSize(QSize(18, 18))
    if on_click:
        b.clicked.connect(on_click)
    if min_w:
        b.setMinimumWidth(min_w)
    return b


def ghost_button(text: str, on_click=None, parent: QWidget = None,
                 icon_name: str = None, min_w: int = None) -> QPushButton:
    b = QPushButton(text, parent)
    b.setObjectName("ghost")
    b.setFixedHeight(36)
    if icon_name:
        t_ = get_current_theme()
        b.setIcon(icon(icon_name, t_.primary_ghost))
        b.setIconSize(QSize(18, 18))
    if on_click:
        b.clicked.connect(on_click)
    if min_w:
        b.setMinimumWidth(min_w)
    return b


def icon_button(icon_name: str, on_click=None, parent: QWidget = None,
                size: int = 32, icon_size: int = 16, tooltip: str = None) -> QPushButton:
    """P1 工厂: 主题感知图标按钮 (objectName=iconBtn, 主色图标, 悬浮底色).

    用于侧栏操作、卡片内操作、对话框关闭等场景。统一全应用图标按钮外观。
    """
    t_ = get_current_theme()
    b = QPushButton(parent)
    b.setObjectName("iconBtn")
    b.setIcon(icon(icon_name, t_.text_muted, icon_size))
    b.setIconSize(QSize(icon_size, icon_size))
    b.setFixedSize(size, size)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFlat(True)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click:
        b.clicked.connect(on_click)
    return b


def status_badge(text: str, color: str = None, bg: str = None,
                 parent: QWidget = None) -> QLabel:
    """P1 工厂: 状态徽章 (胶囊形, 主色或自定义背景).

    统一 stats_page / todo_page 中重复的 badge 样式。
    """
    from PyQt6.QtWidgets import QLabel
    t_ = get_current_theme()
    bg = bg or t_.primary
    fg = color or t_.on_primary
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(
        f"background:{bg}; color:{fg}; border:none; "
        f"border-radius:999px; padding:2px 10px; "
        f"font-size:11px; font-weight:600;")
    return lbl


def more_button(text: str = "更多设置", on_click=None, parent: QWidget = None) -> QPushButton:
    """P1 工厂: 「更多设置」链接按钮 (透明底, 主色文字, 右侧箭头).

    统一 dialogs.py 中重复的更多设置按钮实现。
    """
    t_ = get_current_theme()
    b = QPushButton(text, parent)
    b.setObjectName("moreLink")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton#moreLink{{background:transparent; color:{t_.primary};"
        f" border:none; padding:6px 0; font-size:12px; font-weight:500;"
        f" text-align:left;}}"
        f"QPushButton#moreLink:hover{{color:{t_.primary_hover};}}"
    )
    if on_click:
        b.clicked.connect(on_click)
    return b


def line_edit(label: str = None, value: str = "", placeholder: str = "",
              password: bool = False, parent: QWidget = None) -> QLineEdit:
    le = QLineEdit(value, parent)
    if placeholder:
        le.setPlaceholderText(placeholder)
    elif label:
        le.setPlaceholderText(label)
    if password:
        le.setEchoMode(QLineEdit.EchoMode.Password)
    return le


class _DropdownPanel(QFrame):
    """自建下拉弹出面板：完全替代 QComboBoxPrivateContainer。

    使用 Qt.WindowType.Popup 窗口类型，自带外部点击自动关闭。
    内含 QListWidget 渲染选项，通过 QSS 直接控制全部视觉，
    从根源上消除白框闪烁（不再依赖 Qt 内部容器的 Palette 修补）。
    """

    item_selected = pyqtSignal(int)

    def __init__(self, combo: QComboBox) -> None:
        super().__init__(
            combo,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._combo = combo
        self._explicit_confirm: bool = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._list = QListWidget(self)
        self._list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection)
        self._list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._list.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self._list)

        self._apply_theme()
        self._populate()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- 样式 -------------------------------------------------
    def _apply_theme(self) -> None:
        t = get_current_theme()
        item_h = max(28, getattr(t, 'combo_item_height', 28))
        self.setStyleSheet(
            f"_DropdownPanel {{"
            f"  background: {t.surface};"
            f"  border: 1px solid {t.border};"
            f"  border-radius: {t.radius_sm}px;"
            f"}}"
            f"QListWidget {{"
            f"  background: {t.surface};"
            f"  color: {t.text};"
            f"  border: none;"
            f"  outline: none;"
            f"  padding: 2px;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 6px 10px;"
            f"  border-radius: {t.radius_sm}px;"
            f"  min-height: {item_h}px;"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {t.primary_soft};"
            f"  color: {t.primary};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background: {hex_rgba(t.primary, 0.12)};"
            f"}}"
        )

    # -- 数据同步 ---------------------------------------------
    def _populate(self) -> None:
        self._list.clear()
        for i in range(self._combo.count()):
            item = QListWidgetItem(self._combo.itemText(i))
            ic = self._combo.itemIcon(i)
            if not ic.isNull():
                item.setIcon(ic)
            self._list.addItem(item)
        idx = self._combo.currentIndex()
        if 0 <= idx < self._list.count():
            self._list.setCurrentRow(idx)

    def update_items(self) -> None:
        """外部调用：刷新选项列表并重新应用主题。"""
        self._apply_theme()
        self._populate()

    # -- 定位 -------------------------------------------------
    def position_and_show(self) -> None:
        """计算弹出位置（优先下方，空间不足则上方）并显示。"""
        combo = self._combo
        pw = combo.width()
        item_h = self._list.sizeHintForRow(0)
        if item_h < 0:
            item_h = 32
        vis = min(self._list.count(), 8)
        ph = vis * item_h + 8

        screen = QApplication.screenAt(
            combo.mapToGlobal(combo.rect().center()))
        if screen is None:
            screen = QApplication.primaryScreen()
        sg = screen.availableGeometry()

        below = combo.mapToGlobal(combo.rect().bottomLeft())
        above = combo.mapToGlobal(combo.rect().topLeft())
        space_below = sg.bottom() - below.y()
        space_above = above.y() - sg.top()

        if space_below >= ph or space_below >= space_above:
            pos = below
        else:
            pos = above
            pos.setY(pos.y() - ph)
        pos.setX(max(sg.left(), min(pos.x(), sg.right() - pw)))

        self.setGeometry(pos.x(), pos.y(), pw, ph)
        self.show()
        self._list.setFocus(Qt.FocusReason.PopupFocusReason)
        idx = self._combo.currentIndex()
        if 0 <= idx < self._list.count():
            self._list.scrollToItem(
                self._list.item(idx),
                QListWidget.ScrollHint.PositionAtCenter,
            )

    # -- 关闭 / 确认 ------------------------------------------
    def closeEvent(self, event) -> None:
        if self._explicit_confirm:
            row = self._list.currentRow()
            if row >= 0:
                self.item_selected.emit(row)
        self._explicit_confirm = False
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._explicit_confirm = False
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._explicit_confirm = True
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        local = self.mapFromGlobal(event.globalPosition().toPoint())
        if self.rect().contains(local):
            super().mousePressEvent(event)
        else:
            self._explicit_confirm = False
            self.close()

    def _on_item_clicked(self, _item: QListWidgetItem) -> None:
        self._explicit_confirm = True
        self.close()


class SmoothComboBox(QComboBox):
    """自定义下拉框：完全自建弹出面板，消除白框闪烁。

    彻底绕过 Qt 内部的 QComboBoxPrivateContainer（其默认白底 Palette
    是导致闪烁的根因），改用 _DropdownPanel 自建弹出窗口。
    面板使用 QSS 直接控制全部视觉，亮色 / 暗色主题自动跟随。

    无动画、无弹性——展开即到位，静态平滑。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel: _DropdownPanel | None = None
        self._panel_visible: bool = False

    # -- 弹出 / 收起 ------------------------------------------
    def showPopup(self) -> None:
        """显示自建弹出面板（不调用 super，完全绕过 Qt 内置 popup）。"""
        if self.count() == 0:
            return
        if self._panel is None:
            self._panel = _DropdownPanel(self)
            self._panel.item_selected.connect(self._on_panel_selected)
        self._panel.update_items()
        self._panel.position_and_show()
        self._panel_visible = True
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def hidePopup(self) -> None:
        """隐藏弹出面板并清理事件过滤器。"""
        if self._panel is not None and self._panel.isVisible():
            self._panel.hide()
        self._panel_visible = False
        app = QApplication.instance()
        if app is not None and not sip.isdeleted(self):
            app.removeEventFilter(self)

    # -- 事件过滤器：兜底处理外部点击与快捷键 -----------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not self._panel_visible:
            return False
        et = event.type()

        # 外部鼠标点击 -> 关闭面板
        if et == QEvent.Type.MouseButtonPress and self._panel is not None:
            if isinstance(obj, QWidget) and not self._panel.isAncestorOf(obj):
                self.hidePopup()
                return False

        # 键盘：Escape 关闭，Enter/Return 确认
        if et == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hidePopup()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._panel is not None:
                    row = self._panel._list.currentRow()
                    if row >= 0:
                        self.setCurrentIndex(row)
                self.hidePopup()
                return True

        return False

    # -- 回调 -------------------------------------------------
    def _on_panel_selected(self, index: int) -> None:
        """面板确认选择后更新 combobox 索引。"""
        if 0 <= index < self.count():
            self.setCurrentIndex(index)
        self.hidePopup()

    # -- 覆盖尺寸提示 -----------------------------------------
    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        if self._panel is not None and self._panel.isVisible():
            hint.setWidth(max(hint.width(), self._panel.width()))
        return hint

    # -- 焦点管理：失焦时关闭面板 -----------------------------
    def focusOutEvent(self, event) -> None:
        if self._panel_visible and self._panel is not None:
            focus = QApplication.focusWidget()
            if focus is None or not self._panel.isAncestorOf(focus):
                self.hidePopup()
        super().focusOutEvent(event)



def combo_box(items, value=None, on_change=None, parent: QWidget = None,
              min_w: int = None) -> QComboBox:
    """items: [(data, text), ...]。"""
    cb = SmoothComboBox(parent)
    for data, text in items:
        cb.addItem(text, data)
    if value is not None:
        idx = cb.findData(value)
        if idx >= 0:
            cb.setCurrentIndex(idx)
    if on_change:
        cb.currentIndexChanged.connect(lambda _=0: on_change())
    if min_w:
        cb.setMinimumWidth(min_w)
    return cb


def badge(text: str, parent: QWidget = None, style: str = "default") -> QLabel:
    """药丸徽章：青柠渐变底 + 主色文字，紧凑精致（v2: 渐变底色）。

    Args:
        style: 样式类型
            - "default": 默认青柠渐变底（无背景图时使用）
            - "overlay": 白色半透明底+白色文字（有背景图时使用，确保可读性）
    """
    t = get_current_theme()
    lab = QLabel(text, parent)
    if style == "overlay":
        # 有背景图时：半透明白色背景 + 白色文字 + 细描边
        lab.setStyleSheet(
            f"background:rgba(255,255,255,0.22); color:#FFFFFF;"
            f" border-radius:999px; padding:3px 12px;"
            f" font-weight:600; font-size:12px;"
            f" border:1px solid rgba(255,255,255,0.35);"
        )
    else:
        # 默认：青柠渐变底色
        grad = (f"qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                f" stop:0 {t.primary_soft}, stop:1 {hex_rgba(t.primary, 0.2)})")
        lab.setStyleSheet(
            f"background:{grad}; color:{t.primary_ghost};"
            f" border-radius:999px; padding:3px 12px;"
            f" font-weight:600; font-size:12px;"
            f" border:1px solid {hex_rgba(t.primary, 0.2)};"
        )
    return lab


def section_title(text: str, icon_name: str = None, parent: QWidget = None) -> QWidget:
    """分区标题：可选青柠图标块（圆角方块渐变底）+ 粗体标题。

    v2: 图标块使用渐变底色，更精致。
    """
    t = get_current_theme()
    w = QWidget(parent)
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    if icon_name:
        ico = QLabel()
        ico.setPixmap(icon(icon_name, t.primary, 18).pixmap(34, 34))
        ico.setFixedSize(34, 34)
        # v2: 渐变底色
        grad = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                f" stop:0 {t.primary_soft}, stop:1 {hex_rgba(t.primary, 0.15)})")
        ico.setStyleSheet(
            f"background:{grad}; border-radius:{t.radius_sm}px;"
            f" border:1px solid {hex_rgba(t.primary, 0.15)};"
        )
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(ico)
    lab = QLabel(text)
    lab.setStyleSheet(f"font-size:20px; font-weight:700; color:{t.text};")
    h.addWidget(lab)
    h.addStretch(1)
    return w


def hero_banner(title: str, subtitle: str, parent: QWidget = None) -> QFrame:
    """页面顶部品牌横幅：青柠多段渐变 + 标题 / 副标题。

    v2: 多段渐变（primary → hover → accent2），更丰富。
    v3: 暗色主题标题强制白色，添加微妙边框增强可见性。
    """
    t = get_current_theme()
    f = QFrame(parent)
    f.setObjectName("heroBanner")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(24, 18, 24, 18)
    col = QVBoxLayout()
    col.setSpacing(4)
    ti = QLabel(title)
    ti.setObjectName("heroTitle")
    # 标题颜色：暗色主题强制白色 #FFFFFF，亮色主题使用 on_primary
    title_color = "#FFFFFF" if t.name == "dark" else t.on_primary
    ti.setStyleSheet(
        f"color: {title_color}; font-size: 22px; font-weight: 700;"
    )
    su = QLabel(subtitle)
    su.setObjectName("heroSubtitle")
    # 副标题颜色：暗色主题使用高透明度白色，亮色主题使用 on_primary
    sub_color = "#FFFFFF" if t.name == "dark" else t.on_primary
    su.setStyleSheet(
        f"color: {sub_color}; font-size: 13px;"
    )
    col.addWidget(ti)
    col.addWidget(su)
    lay.addLayout(col)
    lay.addStretch(1)
    return f


class CircularTimer(QLabel):
    """倒计时环形显示（青柠光环 + 大字号）。"""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._text = "25:00"
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(220, 220)

    def set_text(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, ev):
        from PyQt6.QtGui import QBrush
        t = get_current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 14
        # 外环光晕
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.primary))
        p.setOpacity(0.10 if t.name == "light" else 0.16)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setOpacity(1.0)
        # 主环
        pen = QPen(QColor(t.primary), 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        # 文字
        f = QFont()
        f.setPointSize(48)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(t.primary))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class TweenSlider(QSlider):
    """带补间动画的滑块：数值由外部（如数字框）驱动时平滑过渡。

    设计取舍（审计项「滑块补间动画」）：
    - 构造期 / 用户拖动滑块期间走**同步** `setValue`，保证初始位置正确、
      跟手无延迟，且不干扰测试中对「程序化取值」的断言；
    - 仅当窗口可见且滑块未被按下（即数字框联动改值）时，用 motion.base
      (240ms) ease-out 补间，营造「滑块滑过去」的细腻手感。
    """

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._anim = QPropertyAnimation(self, b"animValue")
        self._anim.setDuration(motion.base)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_anim_value(self) -> int:
        return self.value()

    def _set_anim_value(self, v: int) -> None:
        # 由动画逐步驱动真实值；super 避免递归进入本类 setValue。
        # 屏蔽 valueChanged，避免「滑块→数字框→滑块」反馈环在补间期间
        # 反复重启动画（数字框已是最终值，无需回灌）。
        self.blockSignals(True)
        super().setValue(int(round(v)))
        self.blockSignals(False)

    # 注册的 Qt 属性，供 QPropertyAnimation 插值
    animValue = pyqtProperty(int, _get_anim_value, _set_anim_value)

    def setValue(self, value: int) -> None:
        if value == self.value():
            super().setValue(value)
            return
        # 构造期（不可见）或用户正在拖动时不补间，保持同步
        if not self.isVisible() or self.isSliderDown():
            super().setValue(value)
            return
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(value)
        self._anim.start()


class ToggleSwitch(QWidget):
    """丝滑滑块开关 —— 自绘 + QPropertyAnimation 动画。

    替代 QCheckBox 的 QSS 胶囊样式，实现真正的「拇指滑动」效果：
    - 200ms OutCubic 缓动，拇指从左滑到右（或反向）；
    - 轨道颜色渐变（关闭→开启）；
    - 主题感知（主色 / 轨道色 / 阴影取当前主题令牌）；
    - 兼容 QCheckBox API：toggled 信号、isChecked / setChecked。
    """

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._thumb_ratio = 1.0 if checked else 0.0  # 0=left, 1=right
        self._track_w = 46
        self._track_h = 26
        self._thumb_r = 10  # thumb radius
        self.setFixedSize(self._track_w, self._track_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 焦点策略: 支持键盘 Tab 切换
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # P0 修复: 拖出/拖回检测, 仅在按下位置在控件内才允许切换
        self._pressed_inside = False
        # 动画
        self._anim = QPropertyAnimation(self, b"thumbRatio")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── Qt 属性（供动画插值） ──
    def _get_thumb_ratio(self) -> float:
        return self._thumb_ratio

    def _set_thumb_ratio(self, v: float) -> None:
        self._thumb_ratio = v
        self.update()

    thumbRatio = pyqtProperty(float, _get_thumb_ratio, _set_thumb_ratio)

    # ── 兼容 QCheckBox API ──
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self._animate(1.0 if checked else 0.0)
        self.toggled.emit(checked)

    def toggle(self) -> None:
        self.setChecked(not self._checked)

    # ── 动画 ──
    def _animate(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._thumb_ratio)
        self._anim.setEndValue(target)
        self._anim.start()

    # ── 交互 ──
    def mousePressEvent(self, ev):
        """P0 修复: 记录按压位置, mouseReleaseEvent 中判断是否仍在控件内。"""
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed_inside = True
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        """P0 修复: 仅当按压和松开都在控件内时切换, 防止拖出误触。"""
        if (
            ev.button() == Qt.MouseButton.LeftButton
            and self._pressed_inside
            and self.rect().contains(ev.pos())
        ):
            self.toggle()
        self._pressed_inside = False
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.toggle()
        else:
            super().keyPressEvent(ev)

    def focusInEvent(self, ev):
        """P0 修复: 焦点环（无障碍）。"""
        super().focusInEvent(ev)
        self.update()

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        self.update()

    # ── 绘制 ──
    def paintEvent(self, ev):
        t = get_current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # 焦点环(P0 修复: 无障碍)—— 用半透明主色描边
        if self.hasFocus():
            p.setPen(Qt.PenStyle.NoPen)
            focus_color = QColor(t.primary)
            focus_color.setAlphaF(0.35)
            p.setBrush(focus_color)
            p.drawRoundedRect(-2, -2, w + 4, h + 4, (h + 4) / 2, (h + 4) / 2)
        # 轨道圆角
        track_radius = h / 2
        # 轨道颜色：关闭→开启
        if self._checked:
            track_color = QColor(t.primary)
        else:
            track_color = QColor(t.switch_track)
        # 绘制轨道
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 0, w, h, track_radius, track_radius)
        # 拇指位置
        thumb_d = self._thumb_r * 2
        margin = (h - thumb_d) / 2
        x_left = margin
        x_right = w - thumb_d - margin
        thumb_x = x_left + (x_right - x_left) * self._thumb_ratio
        thumb_y = margin
        # 拇指阴影（按主题调整, 暗色加深, 亮色减淡）
        p.setPen(Qt.PenStyle.NoPen)
        shadow_alpha = 50 if t.name == "dark" else 30
        shadow_color = QColor(0, 0, 0, shadow_alpha)
        p.setBrush(shadow_color)
        p.drawEllipse(int(thumb_x + 1), int(thumb_y + 2), thumb_d, thumb_d)
        # 拇指主体（白色）
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(int(thumb_x), int(thumb_y), thumb_d, thumb_d)
        p.end()


# ═════════════════════════════════════════════════════════════════════════════
# CalendarDateEdit：可爱日历图标 + 点击弹出日历
# ═════════════════════════════════════════════════════════════════════════════

def _make_calendar_icon(size: int = 20, color: str = "#2A3A1F",
                         fill_color: str = "#E0EFD0") -> QIcon:
    """绘制一个可爱的小日历图标（圆角卡片 + 装订线 + 日期格子）。

    设计要点：
    - 圆角矩形外框（像一张小卡片）
    - 顶部两个装订线（像台历）
    - 中间一条横线分隔
    - 下方 2x3 小格子（像日期）
    - 柔和的填充色 + 描边色
    """
    s = size
    pix = QPixmap(s, s)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, s // 10)
    w = s - margin * 2
    h = s - margin * 2

    # 圆角矩形外框（填充）
    fill = QColor(fill_color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(margin, margin, w, h, 3, 3)

    # 描边
    stroke = QColor(color)
    pen = QPen(stroke, max(1.2, s / 14))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(margin, margin, w, h, 3, 3)

    # 顶部横线（分隔标题和日期区）
    line_y = margin + h * 0.38
    p.drawLine(margin + 2, int(line_y), margin + w - 2, int(line_y))

    # 两个装订线（顶部小突起）
    hook_w = max(1.5, s / 12)
    hook_h = max(2, s / 8)
    hook1_x = margin + w * 0.30
    hook2_x = margin + w * 0.70
    hook_top = margin - hook_h * 0.5
    # 装订线 1
    p.drawLine(int(hook1_x), int(hook_top), int(hook1_x), int(margin + 2))
    # 装订线 2
    p.drawLine(int(hook2_x), int(hook_top), int(hook2_x), int(margin + 2))

    # 下方 2x2 小日期格子（可爱感来源）
    cell_margin = max(1, s // 8)
    cell_area_top = int(line_y + 2)
    cell_area_bottom = margin + h - 2
    cell_area_h = cell_area_bottom - cell_area_top
    cell_area_left = margin + cell_margin
    cell_area_right = margin + w - cell_margin
    cell_area_w = cell_area_right - cell_area_left
    # 2 列 2 行
    cell_w = (cell_area_w - 2) / 2
    cell_h = (cell_area_h - 2) / 2
    cell_radius = max(1, s / 16)
    p.setPen(Qt.PenStyle.NoPen)
    # 格子填充（比外框填充稍深一点）
    cell_fill = QColor(color)
    cell_fill.setAlpha(35)
    p.setBrush(cell_fill)
    for row in range(2):
        for col in range(2):
            cx = cell_area_left + col * (cell_w + 2)
            cy = cell_area_top + row * (cell_h + 2)
            p.drawRoundedRect(int(cx), int(cy), int(cell_w), int(cell_h),
                              cell_radius, cell_radius)

    p.end()
    return QIcon(pix)


class CalendarDateEdit(QWidget):
    """可爱日历日期选择器：输入框 + 小日历图标按钮。

    完全绕过 QDateEdit 原生上下箭头按钮，使用自定义图标按钮触发日历弹出。
    API 与 QDateEdit 兼容：date() / setDate() / setDisplayFormat() 等。

    用法：
        cal = CalendarDateEdit()
        cal.setDate(QDate.currentDate())
        cal.dateChanged.connect(lambda d: print(d))
    """

    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date = QDate.currentDate()
        self._format = "yyyy-MM-dd"
        self._cal_popup: QCalendarWidget | None = None
        self._setup_ui()
        self._update_icon()

    def _setup_ui(self):
        t = get_current_theme()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 日期显示（只读输入框样式）
        self._line = QLineEdit()
        self._line.setReadOnly(True)
        self._line.setCursor(Qt.CursorShape.PointingHandCursor)
        self._line.setText(self._date.toString(self._format))
        self._line.setFixedHeight(32)
        self._line.setStyleSheet(f"""
            QLineEdit {{
                background: {t.surface};
                color: {t.text};
                border: 1px solid {t.border};
                border-right: none;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top-left-radius: {t.radius_sm}px;
                border-bottom-left-radius: {t.radius_sm}px;
                padding: 0 10px;
                font-size: 12px;
                font-family: {t.font_b};
            }}
        """)
        self._line.mousePressEvent = lambda ev: self._toggle_calendar()
        lay.addWidget(self._line, 1)

        # 可爱日历图标按钮（与输入框等高）
        self._btn = QPushButton()
        self._btn.setFixedSize(32, 32)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setToolTip("选择日期")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-left: none;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                border: 1px solid {t.primary};
                border-left: none;
                background: {hex_rgba(t.primary, 0.06)};
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.12)};
            }}
        """)
        self._btn.clicked.connect(self._toggle_calendar)
        lay.addWidget(self._btn, 0)

    def _update_icon(self):
        """根据当前主题更新日历图标颜色。"""
        t = get_current_theme()
        if t.name == "dark":
            color = "#E0E7FF"
            fill = "#1E2A5C"
        else:
            color = "#5B8A3A"
            fill = "#E0EFD0"
        self._btn.setIcon(_make_calendar_icon(size=16, color=color, fill_color=fill))
        self._btn.setIconSize(QSize(16, 16))

    # ── 日历弹出 ──
    def _toggle_calendar(self):
        if self._cal_popup is not None and self._cal_popup.isVisible():
            self._cal_popup.hide()
            return
        self._show_calendar()

    def _show_calendar(self):
        t = get_current_theme()
        self._cal_popup = QCalendarWidget()
        # 关键：去除窗口标题栏和关闭按钮，只保留日历面板
        self._cal_popup.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._cal_popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._cal_popup.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        self._cal_popup.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self._cal_popup.setGridVisible(False)
        self._cal_popup.setSelectedDate(self._date)
        self._cal_popup.setMinimumSize(300, 260)
        # 主题色 QSS
        self._cal_popup.setStyleSheet(self._calendar_qss(t))
        self._cal_popup.selectionChanged.connect(self._on_cal_selected)
        # 定位到输入框下方
        pos = self.mapToGlobal(self._line.rect().bottomLeft())
        self._cal_popup.move(pos.x() - 20, pos.y() + 4)
        self._cal_popup.show()
        self._cal_popup.raise_()
        self._cal_popup.activateWindow()

    def _on_cal_selected(self):
        new_date = self._cal_popup.selectedDate()
        self.setDate(new_date)
        self._cal_popup.hide()

    @staticmethod
    def _calendar_qss(t) -> str:
        is_dark = t.name == "dark"
        if is_dark:
            sel_bg = hex_rgba(t.primary, 0.30)
            sel_fg = t.text
            nav_bg = hex_rgba(t.surface, 0.40)
        else:
            sel_bg = t.primary
            sel_fg = t.on_primary
            nav_bg = t.primary_soft
        return f"""
        QCalendarWidget {{
            background: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: {t.radius_md}px;
            font-family: {t.font_b};
            font-size: 13px;
        }}
        QCalendarWidget QToolButton {{
            background: transparent; color: {t.text}; border: none;
            border-radius: {t.radius_sm}px; padding: 6px 12px;
            font-size: 14px; font-weight: 600;
        }}
        QCalendarWidget QToolButton:hover {{
            background: {nav_bg}; color: {t.primary};
        }}
        QCalendarWidget QToolButton#qt_calendar_prevmonth,
        QCalendarWidget QToolButton#qt_calendar_nextmonth {{
            min-width: 36px; max-width: 36px;
            min-height: 36px; max-height: 36px;
            border-radius: 18px; font-size: 18px;
        }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background: {t.surface_variant};
            border-bottom: 1px solid {t.border};
            border-top-left-radius: {t.radius_md}px;
            border-top-right-radius: {t.radius_md}px;
            min-height: 44px;
        }}
        QCalendarWidget QTableView {{
            background: transparent;
            alternate-background-color: transparent;
            border: none; gridline-color: transparent; outline: 0;
            selection-background-color: {sel_bg};
            selection-color: {sel_fg};
        }}
        QCalendarWidget QTableView::item {{
            background: transparent; color: {t.text};
            border: none; border-radius: {t.radius_sm}px;
            padding: 0; margin: 2px;
        }}
        QCalendarWidget QTableView::item:hover {{
            background: {hex_rgba(t.primary, 0.12)};
            border-radius: {t.radius_sm}px;
        }}
        QCalendarWidget QTableView::item:selected {{
            background: {sel_bg}; color: {sel_fg};
            font-weight: 700; border-radius: {t.radius_sm}px;
        }}
        QCalendarWidget QHeaderView::section {{
            background: transparent; color: {t.text_muted};
            border: none; padding: 8px 0;
            font-size: 11px; font-weight: 700;
        }}
        """

    # ── QDateEdit 兼容 API ──
    def date(self) -> QDate:
        return self._date

    def setDate(self, date):
        """设置日期，支持 QDate 和 datetime.date。"""
        import datetime as _dt
        if isinstance(date, _dt.date) and not isinstance(date, QDate):
            date = QDate(date.year, date.month, date.day)
        if date != self._date:
            self._date = date
            self._line.setText(date.toString(self._format))
            self.dateChanged.emit(date)

    def setDisplayFormat(self, fmt: str):
        self._format = fmt
        self._line.setText(self._date.toString(fmt))

    def displayFormat(self) -> str:
        return self._format

    def setMinimumWidth(self, w: int):
        self._line.setMinimumWidth(max(0, w - 34))

    def setFixedHeight(self, h: int):
        self._line.setFixedHeight(h)
        self._btn.setFixedHeight(h)

    def setEnabled(self, enabled: bool):
        self._line.setEnabled(enabled)
        self._btn.setEnabled(enabled)

    def refresh_theme(self):
        """主题切换时调用，更新图标颜色和 QSS。"""
        self._update_icon()
        t = get_current_theme()
        self._line.setStyleSheet(f"""
            QLineEdit {{
                background: {t.surface};
                color: {t.text};
                border: 1px solid {t.border};
                border-right: none;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top-left-radius: {t.radius_sm}px;
                border-bottom-left-radius: {t.radius_sm}px;
                padding: 7px 10px;
                font-size: 12px;
                font-family: {t.font_b};
                min-height: 34px;
            }}
        """)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-left: none;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                padding: 0; margin: 0;
            }}
            QPushButton:hover {{
                border: 1px solid {t.primary};
                border-left: none;
                background: {hex_rgba(t.primary, 0.06)};
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.12)};
            }}
        """)


class PlusMinusSpinBox(QWidget):
    """数字输入控件：左侧显示值 + 右侧 +/- 按钮。

    替代 QSpinBox，用直观的 + / - 符号替代原生小三角箭头。
    API 与 QSpinBox 兼容：value() / setValue() / setRange() / setSuffix() 等。
    """

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._min = 0
        self._max = 99
        self._suffix = ""
        self._step = 1
        self._setup_ui()

    def _setup_ui(self):
        t = get_current_theme()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 减号按钮（左侧）
        self._btn_minus = QPushButton("\u2212")
        self._btn_minus.setFixedSize(32, 32)
        self._btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_minus.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                color: {t.primary};
                border: 1px solid {t.border};
                border-right: none;
                border-top-left-radius: {t.radius_sm}px;
                border-bottom-left-radius: {t.radius_sm}px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background: {hex_rgba(t.primary, 0.10)};
                border: 1px solid {t.primary};
                border-right: none;
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.18)};
            }}
        """)
        self._btn_minus.clicked.connect(self._on_minus)

        # 数值显示（中间）
        self._line = QLineEdit()
        self._line.setReadOnly(True)
        self._line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._line.setFixedHeight(32)
        self._line.setStyleSheet(f"""
            QLineEdit {{
                background: {t.surface};
                color: {t.text};
                border: 1px solid {t.border};
                border-left: none;
                border-right: none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 0 8px;
                font-size: 13px;
                font-weight: 600;
                font-family: {t.font_b};
            }}
        """)

        # 加号按钮（右侧）
        self._btn_plus = QPushButton("+")
        self._btn_plus.setFixedSize(32, 32)
        self._btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_plus.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                color: {t.primary};
                border: 1px solid {t.border};
                border-left: none;
                border-top-right-radius: {t.radius_sm}px;
                border-bottom-right-radius: {t.radius_sm}px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background: {hex_rgba(t.primary, 0.10)};
                border: 1px solid {t.primary};
                border-left: none;
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.18)};
            }}
        """)
        self._btn_plus.clicked.connect(self._on_plus)

        lay.addWidget(self._btn_minus)
        lay.addWidget(self._line, 1)
        lay.addWidget(self._btn_plus)

        # 可选的单位标签（放在+按钮右侧，框外）
        self._unit_label = None

        self._update_display()

    def _clamp(self, v):
        return max(self._min, min(self._max, v))

    def _update_display(self):
        self._line.setText(f"{self._value}{self._suffix}")

    def _on_plus(self):
        new_val = self._clamp(self._value + self._step)
        if new_val != self._value:
            self._value = new_val
            self._update_display()
            self.valueChanged.emit(self._value)

    def _on_minus(self):
        new_val = self._clamp(self._value - self._step)
        if new_val != self._value:
            self._value = new_val
            self._update_display()
            self.valueChanged.emit(self._value)

    def value(self):
        return self._value

    def setValue(self, v):
        v = self._clamp(int(v))
        if v != self._value:
            self._value = v
            self._update_display()
            self.valueChanged.emit(self._value)

    def setRange(self, lo, hi):
        self._min = lo
        self._max = hi
        self._value = self._clamp(self._value)
        self._update_display()

    def setMinimum(self, lo):
        self._min = lo
        self._value = self._clamp(self._value)
        self._update_display()

    def setMaximum(self, hi):
        self._max = hi
        self._value = self._clamp(self._value)
        self._update_display()

    def setSingleStep(self, step):
        self._step = step

    def setSuffix(self, suffix):
        self._suffix = suffix
        self._update_display()

    def setUnitOutside(self, unit):
        """将单位标签放在+按钮右侧（框外），与新建待办对话框的 _slider_row 一致。

        调用后 setSuffix 不再生效（单位不再显示在框内）。
        """
        t = get_current_theme()
        if self._unit_label is None:
            self._unit_label = QLabel(unit)
            self._unit_label.setStyleSheet(
                f"color:{t.text_muted}; font-size:13px; padding-left:8px;")
            self._unit_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.layout().addWidget(self._unit_label)
        else:
            self._unit_label.setText(unit)
        # 清空框内 suffix，避免重复显示
        self._suffix = ""
        self._update_display()

    def setSpecialValueText(self, text):
        pass

    def setFixedWidth(self, w):
        self._line.setFixedWidth(max(0, w - 72))

    def setFixedHeight(self, h):
        self._line.setFixedHeight(h)
        self._btn_plus.setFixedHeight(h)
        self._btn_minus.setFixedHeight(h)

    def setEnabled(self, enabled):
        self._line.setEnabled(enabled)
        self._btn_plus.setEnabled(enabled)
        self._btn_minus.setEnabled(enabled)

    def refresh_theme(self):
        self._setup_ui()
        self._update_display()



class PlusMinusTimeEdit(QWidget):
    """时间选择控件：显示 HH:mm + 右侧 +/- 按钮。

    布局与 PlusMinusSpinBox 完全一致：[显示框] [+] [-]
    + 每次增加 15 分钟，- 每次减少 15 分钟（循环）。
    """

    timeChanged = pyqtSignal(object)  # QTime

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import QTime
        self._time = QTime(20, 0)
        self._step = 15  # 分钟步长
        self._setup_ui()

    def _setup_ui(self):
        t = get_current_theme()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 减号按钮（左侧）
        self._btn_minus = QPushButton("−")
        self._btn_minus.setFixedSize(32, 32)
        self._btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_minus.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                color: {t.primary};
                border: 1px solid {t.border};
                border-right: none;
                border-top-left-radius: {t.radius_sm}px;
                border-bottom-left-radius: {t.radius_sm}px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background: {hex_rgba(t.primary, 0.10)};
                border: 1px solid {t.primary};
                border-right: none;
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.18)};
            }}
        """)
        self._btn_minus.clicked.connect(self._on_minus)

        # 时间显示（中间）
        self._line = QLineEdit()
        self._line.setReadOnly(True)
        self._line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._line.setFixedHeight(32)
        self._line.setStyleSheet(f"""
            QLineEdit {{
                background: {t.surface};
                color: {t.text};
                border: 1px solid {t.border};
                border-left: none;
                border-right: none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 0 8px;
                font-size: 13px;
                font-weight: 600;
                font-family: {t.font_b};
            }}
        """)

        # 加号按钮（右侧）
        self._btn_plus = QPushButton("+")
        self._btn_plus.setFixedSize(32, 32)
        self._btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_plus.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                color: {t.primary};
                border: 1px solid {t.border};
                border-left: none;
                border-top-right-radius: {t.radius_sm}px;
                border-bottom-right-radius: {t.radius_sm}px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background: {hex_rgba(t.primary, 0.10)};
                border: 1px solid {t.primary};
                border-left: none;
            }}
            QPushButton:pressed {{
                background: {hex_rgba(t.primary, 0.18)};
            }}
        """)
        self._btn_plus.clicked.connect(self._on_plus)

        lay.addWidget(self._btn_minus)
        lay.addWidget(self._line, 1)
        lay.addWidget(self._btn_plus)

        self._update_display()

    def _update_display(self):
        self._line.setText(f"{self._time.hour():02d}:{self._time.minute():02d}")

    def _on_plus(self):
        from PyQt6.QtCore import QTime
        total_min = self._time.hour() * 60 + self._time.minute()
        total_min = (total_min + self._step) % (24 * 60)
        self._time = QTime(total_min // 60, total_min % 60)
        self._update_display()
        self.timeChanged.emit(self._time)

    def _on_minus(self):
        from PyQt6.QtCore import QTime
        total_min = self._time.hour() * 60 + self._time.minute()
        total_min = (total_min - self._step) % (24 * 60)
        self._time = QTime(total_min // 60, total_min % 60)
        self._update_display()
        self.timeChanged.emit(self._time)

    def time(self):
        return self._time

    def setTime(self, t):
        self._time = t
        self._update_display()

    def setFixedHeight(self, h):
        self._line.setFixedHeight(h)
        self._btn_plus.setFixedHeight(h)
        self._btn_minus.setFixedHeight(h)

    def setFixedWidth(self, w):
        self._line.setFixedWidth(max(0, w - 72))

    def setDisplayFormat(self, fmt):
        pass  # 兼容 QTimeEdit API

    def setEnabled(self, enabled):
        self._line.setEnabled(enabled)
        self._btn_plus.setEnabled(enabled)
        self._btn_minus.setEnabled(enabled)

    def refresh_theme(self):
        self._setup_ui()
