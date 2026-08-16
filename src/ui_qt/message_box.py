"""主题化消息框：替代原生 QMessageBox，统一全应用弹窗视觉。

设计要点：
- 无边框玻璃卡片，继承当前主题 QSS
- 图标/标题/正文/按钮全主题色
- 支持 question / warning / information / critical（danger）四种场景
- 按钮支持主色确认、幽灵取消、危险红色确认
- 返回 QMessageBox.StandardButton，便于 1:1 替换旧调用
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from src.theme import get_current_theme, hex_rgba
from src.ui_qt.icons import icon
from src.ui_qt.widgets import fade_in, glass_card


class ThemedMessageBox(QDialog):
    """主题化消息对话框（QDialog 实现，非原生 QMessageBox）。"""

    _ICON_MAP = {
        "question": "question",
        "info": "info",
        "warning": "warning",
        "danger": "danger",
        "success": "success",
    }

    _ICON_COLOR = {
        "question": "primary",
        "info": "primary",
        "warning": "warning",
        "danger": "danger",
        "success": "success",
    }

    def __init__(
        self,
        parent: QWidget,
        title: str,
        text: str,
        msg_type: str = "info",
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        destructive: bool = False,
        custom_buttons: list[tuple[str, str]] | None = None,
        default_id: str | None = None,
        destructive_ids: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowTitle(title)
        self._result = QMessageBox.StandardButton.NoButton
        self._custom_result: str | None = None
        self._custom_buttons = custom_buttons or []
        self._default_id = default_id
        self._destructive_ids = set(destructive_ids or [])

        t = get_current_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = glass_card(self)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # 标题行：图标 + 标题 + 关闭按钮
        header = QHBoxLayout()
        header.setSpacing(12)
        icon_name = self._ICON_MAP.get(msg_type, "info")
        icon_color = getattr(t, self._ICON_COLOR.get(msg_type, "primary"), t.primary)
        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon(icon_name, icon_color, 28).pixmap(28, 28))
        ico_lbl.setFixedSize(32, 32)
        ico_lbl.setStyleSheet("background:transparent;")
        header.addWidget(ico_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"background:transparent; font-size:18px; font-weight:700; color:{t.text};"
        )
        header.addWidget(title_lbl, 1)

        close_btn = QPushButton()
        close_btn.setObjectName("iconBtn")
        close_btn.setIcon(icon("close", t.text_muted, 16))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFlat(True)
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)

        lay.addLayout(header)

        # 正文
        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setMinimumWidth(280)
        msg_lbl.setStyleSheet(
            f"background:transparent; font-size:13px; color:{t.text_muted}; "
            f"line-height:150%; padding:2px 0 6px 0;"
        )
        lay.addWidget(msg_lbl)

        # 按钮区
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        self._btn_map: dict[QMessageBox.StandardButton, QPushButton] = {}
        self._custom_btn_map: dict[str, QPushButton] = {}
        self._default_button = default_button
        self._destructive = destructive
        if self._custom_buttons:
            self._build_custom_buttons(btn_row, t)
        else:
            self._build_buttons(btn_row, buttons, t)
        lay.addLayout(btn_row)

        root.addWidget(card)

        # 快捷键：Esc 触发取消/No，Enter 触发默认按钮
        self._sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._sc_esc.activated.connect(self._on_escape)
        self._sc_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self._sc_enter.activated.connect(self._on_enter)
        self._sc_enter2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        self._sc_enter2.activated.connect(self._on_enter)

        fade_in(self)

    def _build_buttons(
        self, row: QHBoxLayout,
        buttons: QMessageBox.StandardButton,
        t,
    ):
        # 按位解析标准按钮
        btn_list = []
        if buttons & QMessageBox.StandardButton.Yes:
            btn_list.append(("确定", QMessageBox.StandardButton.Yes))
        if buttons & QMessageBox.StandardButton.No:
            btn_list.append(("取消", QMessageBox.StandardButton.No))
        if buttons & QMessageBox.StandardButton.Ok:
            btn_list.append(("确定", QMessageBox.StandardButton.Ok))
        if buttons & QMessageBox.StandardButton.Cancel:
            btn_list.append(("取消", QMessageBox.StandardButton.Cancel))
        if buttons & QMessageBox.StandardButton.Save:
            btn_list.append(("保存", QMessageBox.StandardButton.Save))
        if buttons & QMessageBox.StandardButton.Discard:
            btn_list.append(("不保存", QMessageBox.StandardButton.Discard))
        if buttons & QMessageBox.StandardButton.Close:
            btn_list.append(("关闭", QMessageBox.StandardButton.Close))
        if buttons & QMessageBox.StandardButton.Apply:
            btn_list.append(("应用", QMessageBox.StandardButton.Apply))
        if buttons & QMessageBox.StandardButton.Reset:
            btn_list.append(("重置", QMessageBox.StandardButton.Reset))

        # 默认按 Cancel/No 在左，Yes/Ok 在右（与 QMessageBox 一致）
        ordered = []
        for label, std in btn_list:
            if std in (
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Close,
            ):
                ordered.insert(0, (label, std))
            else:
                ordered.append((label, std))

        for label, std in ordered:
            is_primary = (std == self._default_button)
            is_yes = std == QMessageBox.StandardButton.Yes
            is_ok = std == QMessageBox.StandardButton.Ok
            is_danger = self._destructive and (is_yes or is_ok)
            btn = self._make_button(label, is_primary, is_danger, t)
            btn.clicked.connect(lambda checked, s=std: self._done(s))
            row.addWidget(btn)
            self._btn_map[std] = btn
            if std == self._default_button:
                btn.setDefault(True)
                btn.setFocus()

    def _build_custom_buttons(self, row: QHBoxLayout, t):
        """构建自定义标签按钮；返回值为自定义 id（str）。"""
        for bid, label in self._custom_buttons:
            is_primary = (bid == self._default_id)
            is_danger = bid in self._destructive_ids
            btn = self._make_button(label, is_primary, is_danger, t)
            btn.clicked.connect(lambda checked, b=bid: self._done_custom(b))
            row.addWidget(btn)
            self._custom_btn_map[bid] = btn
            if bid == self._default_id:
                btn.setDefault(True)
                btn.setFocus()

    def _done_custom(self, bid: str):
        self._custom_result = bid
        self.accept()

    def _make_button(
        self, label: str, primary: bool, danger: bool, t
    ) -> QPushButton:
        b = QPushButton(label)
        b.setFixedHeight(36)
        b.setMinimumWidth(88)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(self._button_stylesheet(primary, danger, t))
        return b

    def _button_stylesheet(self, primary: bool, danger: bool, t) -> str:
        radius = t.radius_sm
        if danger:
            return f"""
            QPushButton {{
                background: {t.danger};
                color: {t.on_danger};
                border: none;
                border-radius: {radius}px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {t.danger_hover}; }}
            QPushButton:pressed {{ background: {hex_rgba(t.danger, 0.85)}; }}
            """
        if primary:
            return f"""
            QPushButton {{
                background: {t.primary};
                color: {t.on_primary};
                border: none;
                border-radius: {radius}px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {t.primary_hover}; }}
            QPushButton:pressed {{ background: {t.primary_pressed}; }}
            """
        return f"""
        QPushButton {{
            background: transparent;
            color: {t.text_muted};
            border: 1px solid {t.border};
            border-radius: {radius}px;
            padding: 0 18px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {t.surface_variant};
            color: {t.text};
            border: 1px solid {t.primary};
        }}
        QPushButton:pressed {{ background: {t.surface_variant}; }}
        """

    def _done(self, std_btn: QMessageBox.StandardButton):
        self._result = std_btn
        self.accept()

    def _default_custom_id(self) -> str | None:
        """自定义按钮模式下，Esc/关闭的默认回退 id。"""
        if not self._custom_buttons:
            return None
        # 优先 default_id；否则取第一个非 destructive 按钮
        if self._default_id:
            return self._default_id
        for bid, _ in self._custom_buttons:
            if bid not in self._destructive_ids:
                return bid
        return self._custom_buttons[0][0]

    def _on_close(self):
        if self._custom_buttons:
            self._done_custom(self._default_custom_id())
            return
        if QMessageBox.StandardButton.Cancel in self._btn_map:
            self._done(QMessageBox.StandardButton.Cancel)
        elif QMessageBox.StandardButton.No in self._btn_map:
            self._done(QMessageBox.StandardButton.No)
        else:
            self._done(self._default_button)

    def _on_escape(self):
        if self._custom_buttons:
            self._done_custom(self._default_custom_id())
            return
        if QMessageBox.StandardButton.Cancel in self._btn_map:
            self._done(QMessageBox.StandardButton.Cancel)
        elif QMessageBox.StandardButton.No in self._btn_map:
            self._done(QMessageBox.StandardButton.No)
        else:
            self._done(self._default_button)

    def _on_enter(self):
        if self._custom_buttons:
            target = self._default_id or self._custom_buttons[0][0]
            self._done_custom(target)
            return
        if self._default_button in self._btn_map:
            self._done(self._default_button)
        elif self._btn_map:
            self._done(list(self._btn_map.keys())[-1])

    @classmethod
    def question(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
    ) -> QMessageBox.StandardButton:
        dlg = cls(parent, title, text, "question", buttons, defaultButton, destructive=False)
        return dlg.exec()

    @classmethod
    def warning(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    ) -> QMessageBox.StandardButton:
        dlg = cls(parent, title, text, "warning", buttons, defaultButton, destructive=False)
        return dlg.exec()

    @classmethod
    def information(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    ) -> QMessageBox.StandardButton:
        dlg = cls(parent, title, text, "info", buttons, defaultButton, destructive=False)
        return dlg.exec()

    @classmethod
    def critical(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    ) -> QMessageBox.StandardButton:
        dlg = cls(parent, title, text, "danger", buttons, defaultButton, destructive=True)
        return dlg.exec()

    @classmethod
    def confirm(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
        destructive: bool = False,
    ) -> QMessageBox.StandardButton:
        """通用确认框；destructive=True 时「确定/是」按钮使用危险红色。"""
        dlg = cls(parent, title, text, "question", buttons, defaultButton, destructive=destructive)
        return dlg.exec()

    @classmethod
    def custom(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        buttons: list[tuple[str, str]],
        default_id: str | None = None,
        destructive_ids: list[str] | None = None,
        msg_type: str = "question",
    ) -> str | None:
        """自定义按钮弹窗。buttons=[(id, label), ...]，返回被点击按钮的 id。

        用于「休息确认」等不适合标准 Yes/No/Ok 的场景。
        """
        dlg = cls(
            parent, title, text, msg_type,
            custom_buttons=buttons, default_id=default_id,
            destructive_ids=destructive_ids,
        )
        return dlg.exec()

    def exec(self):
        super().exec()
        if self._custom_buttons:
            return self._custom_result
        return self._result
