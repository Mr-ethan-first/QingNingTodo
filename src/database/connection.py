"""数据库连接管理与连接测试。"""
import datetime
from typing import Optional, Tuple, List, Any

import pymysql
from pymysql.cursors import DictCursor

from src.config import DBConfig
from src.database import schema


def test_connection(db_config: DBConfig, check_database: bool = False) -> Tuple[bool, str]:
    """测试数据库连接。

    :param db_config: 连接配置
    :param check_database: 是否要求目标数据库已存在；False 时仅测试服务器连通性
    :return: (是否成功, 提示信息)
    """
    conn = None
    try:
        kwargs = dict(
            host=db_config.host,
            port=int(db_config.port),
            user=db_config.user,
            password=db_config.password,
            charset=db_config.charset,
            connect_timeout=5,
        )
        if check_database:
            kwargs["database"] = db_config.database
        conn = pymysql.connect(**kwargs)
        server_info = conn.get_server_info()
        return True, f"连接成功！MySQL 服务器版本：{server_info}"
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else "?"
        msg = e.args[1] if len(e.args) > 1 else str(e)
        if code == 1045:
            return False, f"认证失败：用户名或密码错误 ({msg})"
        if code == 2003:
            return False, f"无法连接到服务器：请检查主机与端口 ({msg})"
        if code == 1049:
            return False, f"数据库不存在：{db_config.database} ({msg})"
        return False, f"连接失败[{code}]：{msg}"
    except Exception as e:  # noqa: BLE001
        return False, f"连接失败：{e}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


class Database:
    """封装 MySQL 连接，提供查询/执行与自动重连。"""

    def __init__(self, db_config: DBConfig):
        self.config = db_config
        self._conn: Optional[pymysql.connections.Connection] = None

    # ---- 连接管理 ----
    def connect(self, with_database: bool = True) -> None:
        kwargs = dict(
            host=self.config.host,
            port=int(self.config.port),
            user=self.config.user,
            password=self.config.password,
            charset=self.config.charset,
            connect_timeout=5,
            autocommit=True,
            cursorclass=DictCursor,
        )
        if with_database:
            kwargs["database"] = self.config.database
        self._conn = pymysql.connect(**kwargs)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def _ensure(self) -> None:
        if self._conn is None:
            self.connect()
        else:
            try:
                self._conn.ping(reconnect=False)
            except Exception:  # noqa: BLE001
                self.connect()

    # ---- 初始化数据库与表 ----
    def init_database(self) -> None:
        """创建数据库（若不存在），建表并写入初始数据。"""
        # 先不指定 database 连接，创建库
        tmp = pymysql.connect(
            host=self.config.host,
            port=int(self.config.port),
            user=self.config.user,
            password=self.config.password,
            charset=self.config.charset,
            connect_timeout=5,
            autocommit=True,
        )
        try:
            with tmp.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.config.database}` "
                    f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
                )
        finally:
            tmp.close()

        # 连接到目标库建表
        self.connect(with_database=True)
        for stmt in schema.SCHEMA_STATEMENTS:
            self.execute(stmt)
        self._seed_data()

    def _seed_data(self) -> None:
        """写入默认用户、白噪音与成就徽章（幂等）。"""
        now = datetime.datetime.now()
        # 默认本地用户
        user = self.query_one("SELECT id FROM `user` LIMIT 1")
        if not user:
            self.execute(
                "INSERT INTO `user`(nickname, created_at, updated_at) VALUES(%s,%s,%s)",
                ("我", now, now),
            )
        user_id = self.query_one("SELECT id FROM `user` LIMIT 1")["id"]

        # 白噪音（批量插入，减少提交次数）
        cnt = self.query_one("SELECT COUNT(*) AS c FROM `white_noise`")["c"]
        if cnt == 0:
            self.execute_many(
                "INSERT INTO `white_noise`(name, file_path, category, is_builtin) "
                "VALUES(%s,%s,%s,%s)",
                list(schema.DEFAULT_WHITE_NOISE),
            )

        # 成就徽章（批量插入）
        cnt = self.query_one(
            "SELECT COUNT(*) AS c FROM `achievement` WHERE user_id=%s", (user_id,)
        )["c"]
        if cnt == 0:
            self.execute_many(
                "INSERT INTO `achievement`(user_id, badge_code, badge_name, unlocked) "
                "VALUES(%s,%s,%s,0)",
                [(user_id, code, title) for code, title in schema.DEFAULT_ACHIEVEMENTS],
            )

    # ---- 通用执行 ----
    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """执行写操作，返回受影响行数或最后插入 id。"""
        self._ensure()
        with self._conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid or cur.rowcount

    def execute_many(self, sql: str, seq_params: List[tuple]) -> int:
        """批量执行写操作，返回受影响行数。"""
        if not seq_params:
            return 0
        self._ensure()
        with self._conn.cursor() as cur:
            return cur.executemany(sql, seq_params)

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[dict]:
        self._ensure()
        with self._conn.cursor() as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
        self._ensure()
        with self._conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return row

    def scalar(self, sql: str, params: Optional[tuple] = None) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return None
        return next(iter(row.values()))
