"""应用入口（Flet 版）。

启动流程：
1. 单实例检测（避免重复运行）；
2. 读取本地配置中的数据库连接信息，若无或连接失败则弹出配置对话框；
3. 连接成功后自动创建数据库与表结构；
4. 读取已保存的主题偏好，进入主界面。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft

from src.config import AppConfig, DBConfig
from src.database.connection import Database
from src.database import dao
from src.theme import DEFAULT_THEME, get_theme
from src.ui_flet.state import AppState
from src.ui_flet.main_view import MainView
from src.ui_flet.db_config_view import DBConfigDialog


def main():
    # 单实例检测（跨平台临时文件锁）
    lock_path = os.path.join(app_home(), ".running.lock")
    if os.path.exists(lock_path):
        # 简单判断：存在锁文件视为已在运行（仅桌面端提示）
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "番茄 ToDo 已经在运行中。\n请查看桌面右下角的系统托盘图标。",
                "番茄 ToDo", 0)
        except Exception:
            pass
        return 0
    try:
        with open(lock_path, "w") as f:
            f.write("1")
    except Exception:
        pass

    def run(page: ft.Page):
        page.title = "番茄ToDo 本地版"
        try:
            page.window.width = 1080
            page.window.height = 720
            page.window.min_width = 920
            page.window.min_height = 620
        except Exception:
            pass
        page.padding = 0
        page.spacing = 0
        page.bgcolor = ft.Colors.WHITE

        app_config = AppConfig()
        cfg = app_config.load()
        if not cfg:
            def on_result(new_cfg):
                app_config.save(new_cfg)
                _boot(page, app_config, new_cfg)
            dlg = DBConfigDialog(get_theme(DEFAULT_THEME), on_result=on_result)
            page.show_dialog(dlg)
            return

        _boot(page, app_config, cfg)

    ft.run(run, assets_dir=None)


def _boot(page: ft.Page, app_config: AppConfig, cfg: DBConfig):
    try:
        db = Database(cfg)
        db.init_database()
    except Exception as e:
        page.show_dialog(ft.SnackBar(ft.Text(f"数据库初始化失败：{e}")))
        return

    # 读取主题偏好
    theme_name = DEFAULT_THEME
    try:
        theme_name = dao.SettingsDAO(db).get("theme", DEFAULT_THEME)
    except Exception:
        pass

    state = AppState(db, app_config, theme_name)
    view = MainView(state)
    page.bgcolor = state.theme.bg
    page.add(view)
    page.update()


def app_home() -> str:
    import os
    override = os.environ.get("QINGNING_TODO_HOME")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".qingning_todo")


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        lp = os.path.join(app_home(), ".running.lock")
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except Exception:
                pass
