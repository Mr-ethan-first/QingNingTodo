"""Windows右下角滑出式通知窗口。

提供与应用主题一致的轻量级通知，从屏幕右下角滑入，
支持自动消失、手动关闭、点击交互。

P0 修复:
- 多 toast 堆叠: 模块级 _active_toasts 跟踪, 新 toast 在已有 toast 上方堆叠
- 多屏适配: 根据鼠标位置选定当前所在屏幕, 跨屏拖动也能正确显示
- 关闭时崩溃: 滑出动画改用 singleShot 控制生命周期, 避免动画叠加 RuntimeError
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, QStandardPaths
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame, QApplication

from src.theme import get_current_theme
from src.ui_qt.icons import icon


# P0 修复: 模块级 toast 跟踪列表, 用于堆叠定位
_active_toasts: list = []
# P0 修复: 队列中已经标记关闭但等待动画结束的 toast
_closing_toasts: set = set()


class ToastNotification(QWidget):
    """右下角滑出式通知窗口。"""

    def __init__(self, title: str, message: str, duration: int = 5000,
                 on_click=None, parent=None):
        """
        Args:
            title: 通知标题
            message: 通知内容
            duration: 自动关闭时间（毫秒），0表示不自动关闭
            on_click: 点击通知时的回调函数
        """
        super().__init__(parent)
        self._on_click = on_click
        self._duration = duration
        self._closing = False  # P0 修复: 防止动画叠加

        # 无边框 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        t = get_current_theme()
        self._theme = t

        # 主容器卡片
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-radius: {t.radius_md}px;
            }}
        """)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        # 标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("bell", t.primary, 18).pixmap(18, 18))
        title_row.addWidget(lbl_icon)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{t.text};")
        title_row.addWidget(lbl_title)
        title_row.addStretch(1)
        btn_close = QPushButton()
        btn_close.setIcon(icon("close", t.text_muted, 14))
        btn_close.setFixedSize(22, 22)
        btn_close.setFlat(True)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton{{border:none; border-radius:4px; background:transparent;}}"
            f"QPushButton:hover{{background:{t.surface_variant};}}")
        btn_close.clicked.connect(self._slide_out)
        title_row.addWidget(btn_close)
        lay.addLayout(title_row)

        # 消息内容
        lbl_msg = QLabel(message)
        lbl_msg.setStyleSheet(f"font-size:13px; color:{t.text_muted};")
        lbl_msg.setWordWrap(True)
        lbl_msg.setMaximumWidth(280)
        lay.addWidget(lbl_msg)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        self.setFixedWidth(320)
        self.adjustSize()

        # 点击事件
        self._card = card

        # P0 修复: 计算位置（多屏适配 + 堆叠）
        self._position_bottom_right()

        # 加入活动列表
        _active_toasts.append(self)

        # 滑入动画
        self._slide_in()

        # 自动关闭定时器
        if duration > 0:
            QTimer.singleShot(duration, self._slide_out)

    def _get_current_screen(self):
        """P0 修复: 多屏适配——取鼠标所在屏幕, 而非总是主屏。"""
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen

    def _position_bottom_right(self):
        """P0 修复: 定位到当前屏幕右下角, 并考虑已有 toast 堆叠。"""
        screen = self._get_current_screen().geometry()
        self._screen_geo = screen
        # 已有 toast 数 → 堆叠偏移
        existing = sum(
            1 for t in _active_toasts
            if t is not self and t._screen_geo == screen
        )
        margin = 20
        stack_offset = (self.height() + 8) * existing
        x = screen.x() + screen.width() - self.width() - margin
        y = screen.y() + screen.height() - self.height() - margin - stack_offset
        self._final_pos = QPoint(x, y)
        # 初始位置在屏幕下方（滑入起点）
        self.move(x, screen.y() + screen.height())

    def _slide_in(self):
        """从屏幕底部滑入。"""
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(300)
        self._anim.setStartValue(QPoint(self._final_pos.x(),
                                         self._final_pos.y() + self.height() + 20))
        self._anim.setEndValue(self._final_pos)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _slide_out(self):
        """向屏幕底部滑出后关闭。
        P0 修复: 用 _closing 标志防止多次动画叠加导致 RuntimeError
        """
        if self._closing:
            return
        self._closing = True
        # 从活动列表移除, 让后续 toast 重新堆叠
        if self in _active_toasts:
            _active_toasts.remove(self)
        # 触发后续 toast 重新定位
        for t in _active_toasts:
            t._reposition_after_close()
        # 启动滑出动画
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(300)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self._final_pos.x(),
                                       self._screen_geo.y() + self._screen_geo.height()))
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.close)
        self._anim.start()

    def _reposition_after_close(self):
        """当有更早的 toast 关闭后, 重新下移占位。"""
        if self._closing:
            return
        # 重新计算 final_pos(自身在堆叠中的位置)
        screen = self._screen_geo
        existing = sum(
            1 for t in _active_toasts
            if t is not self and getattr(t, "_screen_geo", None) == screen
        )
        margin = 20
        new_y = screen.y() + screen.height() - self.height() - margin - (self.height() + 8) * existing
        self._final_pos = QPoint(self._final_pos.x(), new_y)
        # 平滑移动到新位置
        if hasattr(self, "_anim") and self._anim is not None and self._anim.state() == QPropertyAnimation.State.Running:
            pass
        new_anim = QPropertyAnimation(self, b"pos")
        new_anim.setDuration(220)
        new_anim.setStartValue(self.pos())
        new_anim.setEndValue(self._final_pos)
        new_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        new_anim.start()

    def mousePressEvent(self, ev):
        """点击通知触发回调。"""
        if ev.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click()
            self._slide_out()


def show_toast(title: str, message: str, duration: int = 5000,
               on_click=None, parent=None):
    """显示一个右下角滑出式通知。

    Args:
        title: 通知标题
        message: 通知内容
        duration: 自动关闭时间（毫秒），0表示不自动关闭
        on_click: 点击通知时的回调函数
    """
    toast = ToastNotification(title, message, duration, on_click, parent)
    toast.show()
    return toast


def clear_all_toasts() -> None:
    """关闭所有当前显示的 toast（用于主题切换等场景）。"""
    for t in list(_active_toasts):
        t._slide_out()
