"""应用入口（PyQt6 版）。

启动流程：
1. 单实例检测（Windows 命名互斥锁）；
   - 若已有实例运行：将已有窗口恢复并置前，然后退出；
2. 读取本地配置中的数据库后端选择：
   - sqlite（默认）：本地 SQLite 文件，无需配置，开箱即用；
   - mysql：需用户配置连接信息，适合多设备同步。
3. 初始化数据库与表结构；
4. 读取已保存的主题偏好，应用 QSS 并启动主窗口。
"""
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from src.config import AppConfig
from src.database import dao
from src.theme import DEFAULT_THEME, get_theme, apply_theme
from src.ui_qt.state import AppState
from src.ui_qt.main_window import MainWindow

# 窗口标题（与 MainWindow.setWindowTitle 保持一致）
_WINDOW_TITLE = "青柠待办"

# 单实例互斥锁名称
_MUTEX_NAME = "QingNingTodo_SingleInstance_Mutex"

# 保存互斥锁句柄（模块级，防止 GC 回收后释放锁）
_single_instance_mutex = None


def _log_debug(msg: str):
    """写入调试日志到用户配置目录（用于排查启动问题）。"""
    try:
        log_dir = os.environ.get("QINGNING_TODO_HOME",
                                  os.path.join(os.path.expanduser("~"), ".qingning_todo"))
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "startup_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def _check_single_instance() -> bool:
    """检测是否已有实例运行。

    使用 Windows 命名互斥锁（Named Mutex）实现跨进程单实例检测。
    比 QSharedMemory 更可靠：互斥锁是内核对象，生命周期与进程绑定，
    进程退出后自动释放。

    Returns:
        True 表示这是第一个实例（已创建互斥锁）；
        False 表示已有实例运行。
    """
    if os.name != "nt":
        return True  # 非 Windows 平台跳过检测

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183

        # 使用 ctypes 基础类型，避免 wintypes 导入问题
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]

        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        last_error = kernel32.GetLastError()

        _log_debug(f"CreateMutexW: handle={handle}, last_error={last_error}, "
                   f"name={_MUTEX_NAME}")

        if last_error == ERROR_ALREADY_EXISTS:
            # 互斥锁已存在 = 已有实例运行
            _log_debug("Mutex already exists - another instance is running")
            return False

        # 保存句柄引用，防止 GC 回收后关闭句柄
        global _single_instance_mutex
        _single_instance_mutex = handle
        _log_debug(f"Mutex created successfully, first instance")
        return True
    except Exception as e:
        _log_debug(f"Mutex check failed: {type(e).__name__}: {e}")
        # 出错时不阻止启动
        return True


def _bring_existing_window_to_front() -> bool:
    """尝试将已运行实例的主窗口恢复并置前。

    使用 Win32 API 通过窗口标题查找已运行实例的 HWND，
    若窗口处于最小化状态则恢复，然后置前。

    Returns:
        True 表示成功找到并激活窗口；False 表示未找到或失败。
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32

        # 按标题查找窗口
        hwnd = user32.FindWindowW(None, _WINDOW_TITLE)
        if not hwnd:
            return False

        SW_RESTORE = 9
        SW_SHOW = 5

        # 若窗口最小化，先恢复
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        # 置前
        # AttachThreadInput 技巧：SetForegroundWindow 在 Windows 上有权限限制，
        # 通过附加到目标窗口的输入线程可以绕过限制。
        foreground_hwnd = user32.GetForegroundWindow()
        foreground_tid = user32.GetWindowThreadProcessId(foreground_hwnd, None)
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        if foreground_tid != target_tid:
            user32.AttachThreadInput(foreground_tid, target_tid, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(foreground_tid, target_tid, False)
        else:
            user32.SetForegroundWindow(hwnd)

        return True
    except Exception:
        return False


def _init_database(app_cfg: AppConfig):
    """根据配置选择数据库后端，初始化并返回 Database 实例。"""
    backend = app_cfg.db_backend

    if backend == "mysql":
        from src.database.connection import Database
        cfg = app_cfg.load()
        if not cfg:
            # 没有保存的 MySQL 配置，回退到 SQLite
            app_cfg.save_backend("sqlite")
            backend = "sqlite"
        else:
            try:
                db = Database(cfg)
                db.init_database()
                return db
            except Exception as ex:
                # MySQL 连接失败，回退到 SQLite
                print(f"[main] MySQL 连接失败，回退到 SQLite：{ex}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    None, "数据库连接",
                    f"MySQL 连接失败，已自动切换到本地 SQLite 模式。\n\n错误：{ex}")
                app_cfg.save_backend("sqlite")
                backend = "sqlite"

    if backend == "sqlite":
        from src.database.sqlite_backend import create_sqlite_database
        db = create_sqlite_database(app_cfg)
        db.init_database()
        return db

    # 未知后端，默认 SQLite
    from src.database.sqlite_backend import create_sqlite_database
    db = create_sqlite_database(app_cfg)
    db.init_database()
    return db


def main():
    # Windows 任务栏图标：设置 AppUserModelID，使任务栏显示独立图标而非 Python 默认图标
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QingNing.Todo.1.0")
    except Exception:
        pass

    # 单实例检测（命名互斥锁）
    if not _check_single_instance():
        # 已有实例运行：将已有窗口恢复并置前，然后立即退出
        _bring_existing_window_to_front()
        _log_debug("Second instance: brought window to front, exiting now")
        # 直接退出，不创建 QApplication / 不显示 toast
        # （创建 QApplication 在 onefile 模式下很慢，且 toast 会阻止进程退出）
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("青柠待办")

    # 初始化数据库（SQLite 默认免配置启动，MySQL 需配置）
    app_cfg = AppConfig()

    # 如果是 MySQL 模式但还没有配置，弹出配置对话框
    if app_cfg.db_backend == "mysql" and not app_cfg.load():
        from src.ui_qt.dialogs import DBConfigDialog
        dlg = DBConfigDialog(on_result=lambda c: setattr(dlg, "result_cfg", c))
        dlg.result_cfg = None  # type: ignore
        if dlg.exec():
            cfg = dlg.result_cfg
            if cfg:
                app_cfg.save(cfg, backend="mysql")
            else:
                app_cfg.save_backend("sqlite")
        else:
            app_cfg.save_backend("sqlite")

    try:
        db = _init_database(app_cfg)
    except Exception as e:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "数据库错误", f"数据库初始化失败：{e}")
        return 0

    # 读取主题偏好
    theme_name = DEFAULT_THEME
    try:
        theme_name = dao.SettingsDAO(db).get("theme", DEFAULT_THEME)
    except Exception:
        pass

    theme = get_theme(theme_name)
    apply_theme(app, theme)

    state = AppState(db, app_cfg, theme_name)

    # 应用启动时即叠加自定义主色（若已配置），保证整体配色生效
    effective = state.theme
    if effective is not theme:
        apply_theme(app, effective)
    window = MainWindow(state)
    window.resize(1180, 760)

    # 直接在正确位置显示主窗口。
    # 不调用 processEvents()——否则 MainWindow.__init__ 中设置的 800ms
    # 托盘定时器会在 show() 之前触发，QSystemTrayIcon.show() 创建的
    # 原生窗口会以 tooltip（"青柠待办"）为标题闪现一个小窗口。
    screen = app.primaryScreen().availableGeometry()
    cx = (screen.width() - 1180) // 2
    cy = (screen.height() - 760) // 2
    window.move(cx, cy)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
