"""数据库连接配置对话框（Flet 版），支持测试连接。"""
from flet import (
    AlertDialog, Column, Row, Text, TextField, TextButton, icons,
    padding, FontWeight, MainAxisAlignment, ControlEvent,
)
from src.config import DBConfig
from src.database.connection import test_connection
from src.theme import Theme
from src.ui_flet.widgets import text_field, primary_button, ghost_button


class DBConfigDialog(AlertDialog):
    def __init__(self, t: Theme, db_config: DBConfig = None, on_result=None):
        cfg = db_config or DBConfig()
        self.t = t
        self.on_result = on_result
        self.ed_host = text_field(t, "主机地址", value=cfg.host, width=300)
        self.ed_port = text_field(t, "端口", value=str(cfg.port), width=120)
        self.ed_user = text_field(t, "用户名", value=cfg.user, width=300)
        self.ed_pwd = text_field(t, "密码", value=cfg.password, password=True, width=300)
        self.ed_db = text_field(t, "数据库名", value=cfg.database, width=300)
        self.lbl_status = Text("", size=13)
        self.result_config: DBConfig = None

        form = Column([
            Text("数据库连接设置", size=18, weight=FontWeight.BOLD, color=t.text),
            Text("请填写本地 MySQL 连接信息，首次连接将自动创建数据库与数据表。",
                 size=13, color=t.text_muted),
            self.ed_host, self.ed_port, self.ed_user, self.ed_pwd, self.ed_db,
            self.lbl_status,
            Row([
                ghost_button(t, "测试连接", on_click=self._on_test),
                Text("", expand=True),
                ghost_button(t, "取消", on_click=lambda e: self._close()),
                primary_button(t, "保存并连接", on_click=self._on_ok),
            ], spacing=8, alignment=MainAxisAlignment.END),
        ], spacing=10, width=360)

        super().__init__(title=None, content=form, modal=True)

    def current_config(self) -> DBConfig:
        return DBConfig(
            host=self.ed_host.value.strip() or "127.0.0.1",
            port=int(self.ed_port.value or 3306),
            user=self.ed_user.value.strip() or "root",
            password=self.ed_pwd.value,
            database=self.ed_db.value.strip() or "qingning_todo",
        )

    def _set_status(self, msg, ok=None):
        color = self.t.text_muted
        if ok is True:
            color = self.t.success
        elif ok is False:
            color = self.t.danger
        self.lbl_status.value = msg
        self.lbl_status.color = color
        self.lbl_status.update()

    def _on_test(self, e):
        cfg = self.current_config()
        self._set_status("正在测试连接...", None)
        ok, msg = test_connection(cfg, check_database=False)
        self._set_status(("✓ " if ok else "✗ ") + msg, ok)

    def _on_ok(self, e):
        cfg = self.current_config()
        ok, msg = test_connection(cfg, check_database=False)
        if not ok:
            self._set_status("✗ " + msg, False)
            return
        self.result_config = cfg
        self.page.pop_dialog()
        if self.on_result:
            self.on_result(cfg)

    def _close(self):
        self.page.pop_dialog()
