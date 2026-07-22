"""主窗口（PyQt6）：侧边导航 + 堆叠页面 + 系统托盘。"""
import sys

from PyQt6.QtCore import (
    QAbstractNativeEventFilter, QPropertyAnimation, QEasingCurve,
    QEvent, QPoint, QRect, QSize, QTimer, Qt,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QPushButton, QSizePolicy, QStackedWidget, QSystemTrayIcon, QVBoxLayout,
    QWidget,
)

from src.theme import Theme, apply_theme, hex_rgba
from src.ui_qt.global_hotkey import GlobalHotkey
from src.ui_qt.icons import app_icon, icon
from src.ui_qt.pages.focus_page import FocusPage
from src.ui_qt.pages.plan_page import PlanPage
from src.ui_qt.pages.settings_page import SettingsPage
from src.ui_qt.pages.stats_page import StatsPage
from src.ui_qt.pages.todo_page import TodoPage
from src.ui_qt.reminder import ReminderService

_IS_WINDOWS = sys.platform == "win32"


class _TaskbarMinimizeFilter(QAbstractNativeEventFilter):
    """拦截 Windows WM_SYSCOMMAND，在 OS 最小化窗口前播放收起动画。

    通过 QAbstractNativeEventFilter（而非重写 QWidget.nativeEvent）实现，
    避免 PyQt6 中 nativeEvent override 导致的栈损坏崩溃。
    """

    def __init__(self, main_window: "MainWindow"):
        super().__init__()
        self._window = main_window
        self._hwnd: int | None = None

    def set_hwnd(self):
        """窗口 show 后调用，获取 HWND 用于过滤。"""
        try:
            self._hwnd = int(self._window.winId())
        except Exception:
            self._hwnd = None

    def nativeEventFilter(self, eventType, message):
        if not _IS_WINDOWS or eventType != "windows_generic_MSG":
            return False, 0
        if self._hwnd is None:
            return False, 0
        try:
            import ctypes.wintypes as wintypes
            msg = wintypes.MSG.from_address(int(message))
            WM_SYSCOMMAND = 0x0112
            if msg.message == WM_SYSCOMMAND:
                cmd = msg.wParam & 0xFFF0
                SC_MINIMIZE = 0xF020
                SC_RESTORE = 0xF120
                w = self._window
                # 动画/切换过程中不重复拦截，避免状态错乱
                if w._collapsing or w._expanding:
                    return False, 0
                if cmd == SC_MINIMIZE:
                    # 任务栏点击「活动窗口」→ 收起
                    if w.isVisible() and not w.isMinimized():
                        w.collapse_to_taskbar()
                        return True, 0  # 阻止原生最小化
                elif cmd == SC_RESTORE:
                    # 任务栏点击已最小化/隐藏窗口 → 展开；
                    # 点击「可见但非前台」窗口 → 同样收起（实现点击切换）。
                    if w.isMinimized() or not w.isVisible():
                        w.expand_from_taskbar()
                    else:
                        w.collapse_to_taskbar()
                    return True, 0  # 由我们自行处理展开/收起
        except Exception:
            pass
        return False, 0


class _TitleBar(QWidget):
    """无边框窗口的自定义标题栏：拖拽移动 + 最小化/最大化/关闭。"""

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(6)

        # 透明拖拽区：事件穿透到标题栏，按住即可移动窗口
        drag = QWidget()
        drag.setObjectName("titleDrag")
        drag.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        drag.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(drag, 1)

        for icon_name, slot in (
            ("minimize", window.collapse_to_taskbar),
            ("maximize", self._toggle_max),
            ("close", window.close),
        ):
            b = QPushButton()
            b.setObjectName("iconBtn")
            b.setIcon(icon(icon_name, window._t.text_muted, 16))
            b.setFixedSize(30, 30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            lay.addWidget(b)

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self._window.pos()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if getattr(self, "_drag_pos", None) is not None and \
                (ev.buttons() & Qt.MouseButton.LeftButton):
            self._window.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None


class MainWindow(QMainWindow):
    ROUTES = ["todo", "focus", "stats", "plan", "settings"]
    NAV = [
        ("待办清单", "checklist"),
        ("专注计时", "timer"),
        ("数据统计", "chart"),
        ("未来计划", "map"),
        ("设置", "settings"),
    ]

    def __init__(self, state):
        # 关键：在创建 native 窗口之前就带上 Window + FramelessWindowHint。
        # 必须显式包含 Qt.WindowType.Window 基础标志——只传 FramelessWindowHint
        # 会替换 QMainWindow 默认的 Window 标志，导致 Qt 在某些路径下以默认
        # 有边框样式渲染。
        super().__init__(flags=Qt.WindowType.Window
                              | Qt.WindowType.FramelessWindowHint
                              | Qt.WindowType.WindowMinimizeButtonHint
                              | Qt.WindowType.WindowSystemMenuHint)
        self.state = state
        self._t = state.theme
        self.setWindowTitle("青柠待办")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(960, 640)
        self.resize(1180, 760)
        # 无边框窗口：自定义标题栏 + 边缘可缩放（Frameless 已在 __init__ 传入）。
        #
        # ⚠️ 重要：此处【绝不能】调用 setWindowOpacity() 或设置
        # WA_ShowWithoutActivating。在 Windows 上 setWindowOpacity() 会切换
        # WS_EX_LAYERED 并触发 native 窗口重建，重建瞬间会丢失 FramelessWindowHint，
        # 导致窗口以「默认有系统标题栏、标题 fallback 为 applicationName、默认小尺寸」
        # 的状态闪现一帧（即用户曾看到的「标题为青柠待办的小窗口」）。
        # 同理，opacity 0→1 淡入动画也会触发同样的重建，已一并移除。
        self._setup_frameless()

        # ---- 窗口展开/收起动画状态 ----
        self._collapsing = False
        self._expanding = False
        self._first_show = True
        self._saved_geometry: QRect | None = None
        self._collapse_anim: QPropertyAnimation | None = None
        self._expand_anim: QPropertyAnimation | None = None
        # 收起动画后即将 minimize 的标记（防止 changeEvent 重复拦截）
        self._minimize_pending = False
        # 上一次窗口状态（用于检测 restore）
        self._prev_state = Qt.WindowState.WindowNoState
        # Windows 原生消息过滤器：拦截 SC_MINIMIZE 播放收起动画
        self._native_filter: _TaskbarMinimizeFilter | None = None
        # Aurora UI 极光背景动画状态
        self._aurora_angle = 0
        self._aurora_timer = None
        self._aurora_layer = None

        # 中央区域：标题栏 +（侧栏 + 内容）
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 自定义标题栏（可拖拽 + 窗口控制）
        self._title_bar = self._build_title_bar()
        root.addWidget(self._title_bar)

        # 内容行：侧栏 + 分隔 + 页面
        content = QWidget()
        content.setObjectName("appContent")
        hrow = QHBoxLayout(content)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(0)

        # 侧栏容器
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("sidebar")
        self.sidebar_lay = QVBoxLayout(self.sidebar_widget)
        self.sidebar_lay.setContentsMargins(0, 0, 0, 0)
        self.sidebar_lay.setSpacing(0)
        hrow.addWidget(self.sidebar_widget, 0)

        # 分隔线：使用主题边框色, 跟随主题变化
        self._sidebar_sep = QFrame()
        self._sidebar_sep.setFixedWidth(1)
        self._sidebar_sep.setObjectName("sidebarSeparator")
        self._sidebar_sep.setStyleSheet(f"background:{self._t.border};")
        hrow.addWidget(self._sidebar_sep, 0)

        # 页面容器
        self.stack = QStackedWidget()
        hrow.addWidget(self.stack, 1)

        root.addWidget(content, 1)

        self.pages = {}
        self._create_pages()
        self._build_sidebar()
        # 延迟创建系统托盘图标：给 explorer 一点就绪时间；
        # 真正的防护在 _setup_tray 内部——托盘不可用时不创建 QSystemTrayIcon，
        # 从而避免 Qt 弹出"标题=toolTip、带系统标题栏"的 fallback 小窗口。
        QTimer.singleShot(800, self._setup_tray)
        self._init_shortcut()
        self._init_reminder()

        state.subscribe(self._on_theme)
        state.nav_callback = self.navigate
        state.on_start_focus = self._on_start_focus
        state.on_focus_finished = self._on_focus_finished

        # 子进程/子窗口管理：主程序退出时联动关闭所有子窗口与子进程，
        # 避免残留窗口（对话框/Toast）或子进程导致主进程无法退出。
        self._child_processes = []
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cleanup_on_quit)

        self.navigate("todo")

    # ---- 页面 ----
    def _create_pages(self):
        self.pages = {
            "todo": TodoPage(self.state),
            "focus": FocusPage(self.state),
            "stats": StatsPage(self.state),
            "plan": PlanPage(self.state),
            "settings": SettingsPage(self.state),
        }
        for r in self.ROUTES:
            self.stack.addWidget(self.pages[r])

    # ---- 侧栏 ----
    def _build_sidebar(self):
        t = self._t

        # 清空旧控件（全部 takeAt，含子 Layout / Spacer）
        while self.sidebar_lay.count():
            item = self.sidebar_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_child_layout(item.layout())

        # 侧栏渐变背景已由全局 QSS #sidebar 提供（build_qss），
        # 此处不再覆盖 setStyleSheet，使主题切换时自动跟随。

        # 品牌
        brand = QHBoxLayout()
        brand.setContentsMargins(18, 18, 18, 18)
        brand.setSpacing(10)
        ico = QLabel()
        ico.setPixmap(icon("leaf", t.primary, 28).pixmap(38, 38))
        ico.setFixedSize(38, 38)
        ico.setStyleSheet(f"background:{t.primary_soft}; border-radius:{t.radius_md}px;")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(ico)
        v = QVBoxLayout()
        v.setSpacing(2)
        name = QLabel("青柠待办")
        name.setStyleSheet(f"font-size:16px; font-weight:700; color:{t.sidebar_text};")
        sub = QLabel("专注 · 致远")
        sub.setStyleSheet(f"font-size:11px; color:{t.sidebar_muted};")
        v.addWidget(name); v.addWidget(sub)
        brand.addLayout(v, 1)
        self.sidebar_lay.addLayout(brand)

        # 分隔
        self.sidebar_lay.addSpacing(4)

        # 导航按钮
        self.nav_btns = []
        route_actions = {r: action for r, action in
                         zip(self.ROUTES, [lambda: self.navigate("todo"),
                                           lambda: self.navigate("focus"),
                                           lambda: self.navigate("stats"),
                                           lambda: self.navigate("plan"),
                                           lambda: self.navigate("settings")])}
        for i, (name, icon_name) in enumerate(self.NAV):
            btn = self._nav_button(name, icon_name, i, route_actions[self.ROUTES[i]])
            self.nav_btns.append(btn)
            self.sidebar_lay.addWidget(btn)

        self.sidebar_lay.addStretch(1)

        # 当前主题 + 版本
        theme_name = QLabel(f"当前：{t.label}")
        theme_name.setStyleSheet(f"font-size:12px; color:{t.sidebar_muted};"
                                 f" padding:0 18px 4px;")
        self.sidebar_lay.addWidget(theme_name)

        ver = QLabel("v1.0.0")
        ver.setStyleSheet(f"font-size:11px; color:{t.sidebar_muted};"
                          f" padding:0 18px 14px;")
        self.sidebar_lay.addWidget(ver)

        self._style_nav()

    def _clear_child_layout(self, layout):
        """递归清理子 layout 中的控件，避免内存泄漏。"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_child_layout(item.layout())

    def _nav_button(self, name, icon_name, idx, on_click):
        t = self._t
        btn = QPushButton(self.sidebar_widget)
        btn.setCheckable(True)
        btn.setObjectName("navBtn")
        btn.clicked.connect(on_click)
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 样式由全局 QSS #navBtn 提供，此处仅设置图标与文字
        btn.setIcon(icon(icon_name, t.sidebar_muted, 20))
        btn.setIconSize(QSize(20, 20))
        btn.setText(f"  {name}")
        return btn

    def _style_nav(self):
        t = self._t
        for i, btn in enumerate(self.nav_btns):
            sel = btn.isChecked()
            btn.setIcon(icon(self.NAV[i][1],
                             t.primary if sel else t.sidebar_muted, 20))

    # ---- 导航 ----
    def navigate(self, route: str):
        if route not in self.pages:
            return
        idx = self.ROUTES.index(route)
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == idx)
        self._style_nav()
        self.stack.setCurrentIndex(idx)
        self.pages[route].refresh()

    def _on_start_focus(self, todo):
        self.navigate("focus")
        self.pages["focus"].load_todo(todo)

    def _on_focus_finished(self):
        try:
            self.pages["stats"].refresh()
        except Exception:
            pass

    # ---- 全局快捷键 ----
    def _init_shortcut(self):
        combo = "Ctrl+Shift+A"
        try:
            combo = self.state.settings_dao.get("shortcut_key", combo) or combo
        except Exception:
            pass
        self._hotkey = GlobalHotkey(combo, parent=self)
        self._hotkey.activated.connect(self._on_hotkey)
        self._hotkey.start()
        # 供设置页在修改快捷键后重新注册
        self.state.on_shortcut_change = self._on_shortcut_change

    def _on_shortcut_change(self, combo: str):
        try:
            self._hotkey.stop()
        except Exception:
            pass
        self._hotkey = GlobalHotkey(combo, parent=self)
        self._hotkey.activated.connect(self._on_hotkey)
        self._hotkey.start()

    def _on_hotkey(self):
        """全局快捷键触发：将主窗口唤到前台。"""
        if self.isVisible() and not self.isMinimized():
            self.collapse_to_taskbar()
        else:
            self.expand_from_taskbar()

    # ---- 习惯每日提醒 ----
    def _init_reminder(self):
        self._reminder = ReminderService(self.state, parent=self)
        self._reminder.reminder.connect(self._on_reminder)
        self._reminder.start()

    def _on_reminder(self, title: str, message: str):
        tray = getattr(self, "_tray", None)
        if tray is None:
            return
        try:
            tray.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, 8000)
        except Exception:
            pass

    # ---- 主题 ----
    def _on_theme(self, theme: Theme):
        self._t = theme
        app = QApplication.instance()
        if app:
            apply_theme(app, theme)
        # 侧栏分隔线跟随主题
        if hasattr(self, "_sidebar_sep") and self._sidebar_sep is not None:
            self._sidebar_sep.setStyleSheet(f"background:{theme.border};")
        # 极光背景 (仅 dark 主题启用, 1:1 还原 Aurora UI 旋转效果)
        if theme.name == "dark":
            self._ensure_aurora_layer()
        else:
            self._remove_aurora_layer()
        self._build_sidebar()
        self.setWindowIcon(app_icon())
        self._build_tray()

    def _ensure_aurora_layer(self) -> None:
        """在 central 顶部添加一个全屏 QLabel, 用 conic-gradient 模拟极光, 25s 旋转一周.
        1:1 还原 Aurora UI body::before (conic-gradient + filter:blur(90px) + animation:auroraSpin 25s).
        """
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QColor
        if self._aurora_layer is not None:
            return  # 已存在, 仅需重启动画
        central = self.centralWidget()
        if central is None:
            return
        # 极光底层
        self._aurora_layer = QLabel(central)
        self._aurora_layer.setObjectName("auroraLayer")
        # 极光不接收鼠标事件
        self._aurora_layer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._aurora_layer.lower()  # 放在最底层
        # 启动 25s 周期的旋转动画
        if self._aurora_timer is None:
            self._aurora_timer = QTimer(self)
            self._aurora_timer.setInterval(80)  # ~12.5fps 足够流畅
            self._aurora_timer.timeout.connect(self._tick_aurora)
            self._aurora_timer.start()

    def _remove_aurora_layer(self) -> None:
        if self._aurora_timer is not None:
            self._aurora_timer.stop()
            self._aurora_timer = None
        if self._aurora_layer is not None:
            self._aurora_layer.deleteLater()
            self._aurora_layer = None

    def _tick_aurora(self) -> None:
        """极光旋转: 25s 一周 => 360° / (25000/80) = 1.152°/tick.
        1:1 还原 Aurora UI body::before conic-gradient (filter:blur(90px), opacity:.4).
        Qt 无 blur 滤镜, 用低 alpha 模拟 + 大尺寸实现柔光效果.
        """
        if self._aurora_layer is None or self._t is None or self._t.name != "dark":
            return
        self._aurora_angle = (self._aurora_angle + 1.152) % 360.0
        t = self._t
        a = self._aurora_angle
        # 原型: conic-gradient(from 0deg at 70% 30%, primary, secondary, accent, primary);
        #       filter: blur(90px); opacity: 0.4
        # Qt 模拟: 用低 alpha (~22%) 的 conic-gradient 模拟半透明模糊效果
        css = (
            f"background-color: transparent;"
            f"background-image: qconicalgradient("
            f"cx:0.7, cy:0.3, angle:{a:.2f}, "
            f"stop:0 {hex_rgba(t.primary, 0.25)}, "
            f"stop:0.33 {hex_rgba(t.secondary, 0.18)}, "
            f"stop:0.66 {hex_rgba(t.accent, 0.22)}, "
            f"stop:1 {hex_rgba(t.primary, 0.25)});"
        )
        self._aurora_layer.setStyleSheet(css)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # 极光层始终覆盖整个 central
        if self._aurora_layer is not None:
            central = self.centralWidget()
            if central is not None:
                self._aurora_layer.setGeometry(central.rect())
                self._aurora_layer.lower()

    def showEvent(self, ev):
        super().showEvent(ev)
        if self._aurora_layer is not None:
            central = self.centralWidget()
            if central is not None:
                self._aurora_layer.setGeometry(central.rect())

    # ---- 系统托盘 ----
    def _setup_tray(self):
        """创建系统托盘图标。

        关键修复：仅当系统托盘可用时才创建 QSystemTrayIcon。
        若不可用（某些虚拟桌面 / 远程会话 / 通知区域被禁用 / explorer 尚未就绪），
        Qt 会弹出一个【带系统标题栏、标题为 toolTip（"青柠待办"）的小窗口】作为
        fallback——这正是用户曾看到的"小弹窗"。因此不可用时【绝不创建】
        QSystemTrayIcon（保持 self._tray=None），也就不会触发该 fallback 窗口。

        首次检测可能因 explorer 尚未就绪而误报不可用，故最多重试数次。
        """
        self._tray = None
        self._tray_available = False
        self._try_setup_tray(0)

    def _try_setup_tray(self, attempt: int):
        try:
            avail = QSystemTrayIcon.isSystemTrayAvailable()
        except Exception:
            avail = False

        if avail:
            self._tray_available = True
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(app_icon())
            self._tray.setToolTip("青柠待办")
            self._tray.activated.connect(self._on_tray_activated)
            self._build_tray()
            self._tray.show()
            return

        # 托盘暂不可用：稍后重试，但【绝不】创建 QSystemTrayIcon，避免 fallback 小窗。
        if attempt < 6:
            QTimer.singleShot(1000, lambda: self._try_setup_tray(attempt + 1))
        else:
            # 确认不可用：保持无托盘，关闭即退出程序（见 closeEvent）。
            self._tray_available = False

    def _build_tray(self):
        if not hasattr(self, '_tray') or self._tray is None:
            return
        if hasattr(self, '_tray_menu') and self._tray_menu:
            self._tray_menu.deleteLater()
        menu = QMenu()
        self._tray_menu = menu
        show_action = menu.addAction("显示主窗口")
        show_action.triggered.connect(self.expand_from_taskbar)
        quit_action = menu.addAction("退出")
        # 走统一退出逻辑：先联动关闭子窗口/子进程，再退出
        quit_action.triggered.connect(self._quit_from_tray)
        self._tray.setContextMenu(menu)

    def _quit_from_tray(self):
        """托盘菜单「退出」：联动关闭所有子窗口与子进程后退出。

        托盘退出不经过主窗口 closeEvent（无需二次确认），直接强制退出。
        """
        self._cleanup_on_quit()
        try:
            if hasattr(self, "_tray") and self._tray is not None:
                self._tray.hide()
        except Exception:
            pass
        QApplication.instance().quit()

    # ---- 无边框窗口：拖拽 / 边缘缩放 ----
    _RESIZE_MARGIN = 6

    def _setup_frameless(self):
        """去掉原生标题栏，启用自定义标题栏与边缘缩放。

        FramelessWindowHint 已在 __init__ 的 super() 中设置，
        此处不再调用 setWindowFlags，避免对已创建的 native 窗口触发重建。
        """
        self._resizing = False
        self._resize_edge = None
        self._resize_start: QPoint | None = None
        self._resize_geo: QRect | None = None

    def _build_title_bar(self) -> QWidget:
        return _TitleBar(self)

    def _edge_at(self, pos: QPoint) -> str | None:
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self._RESIZE_MARGIN
        left, right = x <= m, x >= w - m
        top, bottom = y <= m, y >= h - m
        if left and top:
            return "tl"
        if right and top:
            return "tr"
        if left and bottom:
            return "bl"
        if right and bottom:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return None

    def _set_cursor(self, edge: str | None) -> None:
        cur = Qt.CursorShape.ArrowCursor
        if edge in ("l", "r"):
            cur = Qt.CursorShape.SizeHorCursor
        elif edge in ("t", "b"):
            cur = Qt.CursorShape.SizeVerCursor
        elif edge in ("tl", "br"):
            cur = Qt.CursorShape.SizeFDiagCursor
        elif edge in ("tr", "bl"):
            cur = Qt.CursorShape.SizeBDiagCursor
        self.setCursor(cur)

    def _apply_resize(self, gpos: QPoint) -> None:
        if self._resize_geo is None or self._resize_start is None:
            return
        dx = gpos.x() - self._resize_start.x()
        dy = gpos.y() - self._resize_start.y()
        geo = QRect(self._resize_geo)
        edge = self._resize_edge
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        if "l" in edge:
            geo.setLeft(min(geo.left() + dx, geo.right() - min_w))
        if "r" in edge:
            geo.setRight(geo.right() + dx)
        if "t" in edge:
            geo.setTop(min(geo.top() + dy, geo.bottom() - min_h))
        if "b" in edge:
            geo.setBottom(geo.bottom() + dy)
        self.setGeometry(geo)

    def mouseMoveEvent(self, ev):
        if self._resizing and self._resize_edge and self._resize_start is not None:
            self._apply_resize(ev.globalPosition().toPoint())
            ev.accept()
            return
        self._set_cursor(self._edge_at(ev.pos()))
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(ev.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start = ev.globalPosition().toPoint()
                self._resize_geo = self.geometry()
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._resizing = False
        self._resize_edge = None
        self._resize_start = None
        self._resize_geo = None
        super().mouseReleaseEvent(ev)

    def showEvent(self, ev):
        """首次显示事件：在 OS 显示窗口前设置分层样式，避免闪现。

        TRAE/Electron 的实现：BrowserWindow 在创建时即带 WS_EX_LAYERED，
        因此 setOpacity 不会触发样式变更与窗口重建，淡入动画全程平滑。

        Qt 的 show_helper 流程：
        1. create() — 创建 native 窗口（HWND 已就绪）
        2. sendEvent(QShowEvent) — 调用本 showEvent
        3. show_sys() — 调用 ShowWindow(hwnd, SW_SHOW) 让窗口可见

        因此在 showEvent 内（super 调用前）HWND 已存在但 ShowWindow 尚未
        调用，此时手动 SetWindowLongPtr 添加 WS_EX_LAYERED 并通过
        SetLayeredWindowAttributes 将 alpha 设为 0，ShowWindow 即以透明
        状态显示，无任何闪现。后续 setWindowOpacity 仅更新 alpha，
        不再触发窗口样式变更。
        """
        if self._first_show:
            self._first_show = False
            # 关键：在 super().showEvent() 之前完成 layered 样式设置
            if _IS_WINDOWS:
                self._setup_layered_zero_alpha()
            super().showEvent(ev)
            if _IS_WINDOWS and self._native_filter is None:
                self._native_filter = _TaskbarMinimizeFilter(self)
                QApplication.instance().installNativeEventFilter(
                    self._native_filter)
                self._native_filter.set_hwnd()
            # 延迟一帧启动淡入动画（此时窗口已透明显示，无闪现）
            QTimer.singleShot(0, lambda: self._fade_in(start=0.0, duration=300))
        else:
            super().showEvent(ev)

    def _setup_layered_zero_alpha(self):
        """在 showEvent 内、ShowWindow 之前调用：
        手动为 HWND 添加 WS_EX_LAYERED 并将 alpha 设为 0。

        模仿 Electron BrowserWindow 的行为——它在创建 native 窗口时即
        带 WS_EX_LAYERED，setOpacity 仅调用 SetLayeredWindowAttributes
        更新 alpha，不触发 SetWindowLongPtr 样式变更与窗口重建。

        本函数在 native 窗口已 create、ShowWindow 未调用的时机手动添加
        分层样式并设为透明，让 ShowWindow 直接以透明状态显示。
        """
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if not (ex_style & WS_EX_LAYERED):
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
            # 通过 Qt 的 setWindowOpacity 同步 Qt 内部状态与 native alpha。
            # WS_EX_LAYERED 已手动添加，setWindowOpacity 仅会调用
            # SetLayeredWindowAttributes 更新 alpha，不会再次触发样式变更。
            self.setWindowOpacity(0.0)
            self._layered_initialized = True
        except Exception:
            self._layered_initialized = False

    def _fade_in(self, start: float, duration: int, on_finished=None):
        """播放淡入动画：窗口透明度从 start → 1.0。

        前置条件：WS_EX_LAYERED 已在 _setup_layered_zero_alpha 中添加，
        因此 setWindowOpacity 仅调用 SetLayeredWindowAttributes 更新 alpha，
        不再触发窗口样式变更，与 Electron/TRAE 的 setOpacity 完全一致。
        """
        if self._collapsing or self._expanding:
            return
        # 显式设为 start（动画启动前同步状态，避免动画首帧跳变）
        self.setWindowOpacity(start)
        self._expanding = True
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        if on_finished is not None:
            anim.finished.connect(on_finished)
        else:
            anim.finished.connect(self._on_fade_in_finished)
        self._expand_anim = anim
        anim.start()

    def _on_fade_in_finished(self):
        """淡入结束。"""
        self._expanding = False
        self.setWindowOpacity(1.0)

    # ---- 窗口收起动画（淡出） ----
    def collapse_to_taskbar(self):
        """收起窗口：淡出后最小化，保持任务栏图标可见。"""
        if self._collapsing or self._expanding:
            return
        if not self.isVisible():
            return

        self._collapsing = True
        self._saved_geometry = self.geometry()

        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(180)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        anim.finished.connect(self._on_collapse_finished)
        self._collapse_anim = anim
        anim.start()

    def _on_collapse_finished(self):
        """淡出结束：最小化窗口并恢复透明度。"""
        self._collapsing = False
        self._minimize_pending = True
        self.showMinimized()
        # 恢复透明度为 1，下次显示时不会残留
        self.setWindowOpacity(1.0)

    def expand_from_taskbar(self):
        """展开窗口：恢复显示后淡入。"""
        if self._collapsing or self._expanding:
            return
        if self.isMinimized() or not self.isVisible():
            # 先设为透明，防止 showNormal 后闪现
            # （WS_EX_LAYERED 已在首次 showEvent 中设置，此处无样式变更）
            self.setWindowOpacity(0.0)
            self.showNormal()
            self.raise_()
            self.activateWindow()
            # 延迟一帧后播放淡入动画
            QTimer.singleShot(0, lambda: self._fade_in(start=0.0, duration=200))
        else:
            self._fade_in(start=self.windowOpacity(), duration=200)

    def _on_expand_finished(self):
        """展开动画结束。"""
        self._expanding = False
        self.setWindowOpacity(1.0)

    def changeEvent(self, event):
        """拦截窗口状态变化，处理从最小化恢复时的淡入。"""
        if event.type() == QEvent.Type.WindowStateChange:
            new_state = self.windowState()
            old_state = self._prev_state
            self._prev_state = new_state

            is_min = bool(new_state & Qt.WindowState.WindowMinimized)
            was_min = bool(old_state & Qt.WindowState.WindowMinimized)

            # 收起动画后的主动 minimize → 放行
            if is_min and not was_min:
                if self._minimize_pending:
                    self._minimize_pending = False

            # 从最小化恢复 → 播放淡入
            if (was_min and not is_min and not self._expanding
                    and not self._collapsing):
                # 先设为透明防止闪现
                self.setWindowOpacity(0.0)
                QTimer.singleShot(0, lambda: self._fade_in(start=0.0, duration=200))

        super().changeEvent(event)

    def _on_tray_activated(self, reason):
        """托盘图标激活：单击/双击切换展开与收起。"""
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self._collapsing or self._expanding:
                return
            # 最小化或不可见 → 展开
            if self.isMinimized() or not self.isVisible():
                self.expand_from_taskbar()
            else:
                # 可见且非最小化 → 收起
                self.collapse_to_taskbar()

    def closeEvent(self, ev):
        """点击叉号关闭窗口：默认退出程序。

        行为由设置项 `confirm_on_close` 控制（默认 "true"）：
        - 为 "true"：弹出退出确认对话框（提醒窗口），用户可选择
          「退出程序」（默认）/「最小化到托盘」，并可勾选「不再提醒」；
          勾选「不再提醒」后写入 `confirm_on_close`="false"，下次直接退出。
        - 为 "false"：不再提醒，点击叉号直接退出程序。
        """
        # 系统托盘不可用：无"最小化到托盘"能力，关闭即直接退出程序
        if not getattr(self, "_tray_available", False):
            self._quit_app(ev)
            return

        confirm = "true"
        try:
            confirm = (self.state.settings_dao.get(
                "confirm_on_close", "true") or "true").lower()
        except Exception:
            confirm = "true"

        # 不再提醒 → 直接退出
        if confirm != "true":
            self._quit_app(ev)
            return

        from src.ui_qt.dialogs import CloseConfirmDialog
        dlg = CloseConfirmDialog(parent=self)
        dlg.exec()

        # 勾选「不再提醒」：持久化配置，后续可在设置页重新开启
        if dlg.dont_remind:
            try:
                self.state.settings_dao.set("confirm_on_close", "false")
            except Exception:
                pass

        if dlg.action == CloseConfirmDialog.ACTION_EXIT:
            self._quit_app(ev)
        elif dlg.action == CloseConfirmDialog.ACTION_TRAY:
            ev.ignore()
            self.collapse_to_taskbar()
        else:
            # 取消：什么也不做，窗口保持打开
            ev.ignore()

    def _quit_app(self, ev):
        """真正退出应用：联动关闭所有子窗口与子进程、隐藏托盘图标并退出事件循环。"""
        ev.accept()
        self._cleanup_on_quit()
        try:
            if hasattr(self, "_tray") and self._tray is not None:
                self._tray.hide()
        except Exception:
            pass
        QApplication.instance().quit()

    # ---- 退出联动：关闭所有子窗口与子进程 ----
    def register_child_process(self, proc):
        """登记一个子进程（如 subprocess.Popen 实例）。

        应用退出时会自动终止这些子进程，避免残留导致主进程无法退出。
        """
        if not hasattr(self, "_child_processes"):
            self._child_processes = []
        if proc is not None:
            self._child_processes.append(proc)

    def _cleanup_on_quit(self):
        """应用退出前的联动清理：关闭所有仍打开的子窗口、终止所有子进程。

        覆盖两条退出路径：
        - 任务栏/标题栏关闭主窗口 → closeEvent → _quit_app → quit()
        - 托盘菜单「退出」→ 直接 QApplication.quit()（由 aboutToQuit 触发本方法）
        """
        self._terminate_child_processes()
        self._close_all_child_windows()

    def _close_all_child_windows(self):
        """关闭所有非主窗口的顶层窗口（子对话框 / Toast / 弹层等）。

        子窗口默认 WA_QuitOnClose=True，若残留会导致 QApplication 事件循环
        不退出、主进程无法关闭。此处显式关闭，确保进程完全退出。
        """
        app = QApplication.instance()
        if app is None:
            return
        # 使用 list() 快照，避免遍历过程中窗口列表变化
        for w in list(app.topLevelWidgets()):
            if w is self:
                continue
            try:
                if w.isVisible():
                    w.close()
            except Exception:
                pass

    def _terminate_child_processes(self):
        """终止所有已登记的子进程（含进程树），超时则强制杀掉。"""
        procs = getattr(self, "_child_processes", None)
        if not procs:
            return
        import subprocess as _sp
        for proc in list(procs):
            try:
                if hasattr(proc, "poll") and proc.poll() is None:
                    # 优先终止整个进程树（Windows 用 taskkill /T，其它用 os.killpg）
                    pid = getattr(proc, "pid", None)
                    if _IS_WINDOWS and pid is not None:
                        try:
                            _sp.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                    capture_output=True, timeout=5)
                            continue
                        except Exception:
                            pass
                    if hasattr(proc, "terminate"):
                        proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except Exception:
                        if hasattr(proc, "kill"):
                            proc.kill()
            except Exception:
                pass
        self._child_processes = []
