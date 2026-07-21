"""测试配置：设置 offscreen 平台确保 GUI 测试在无显示器环境下运行。

支持通过环境变量 ``QINGNING_TEST_DB_BACKEND`` 强制指定数据库后端：
- ``mysql``：强制使用 MySQL 后端（若不可用则 skip）
- ``sqlite``：强制使用 SQLite 后端
- 未设置时：优先 MySQL（如可用），否则回退 SQLite

这样既保证 MySQL 集成测试在 CI/有 MySQL 的环境下运行，
又保证无 MySQL 环境下测试不全部 skip，同时支持分别对两个后端跑全量测试。
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QINGNING_TODO_HOME", os.path.join(
    os.path.dirname(__file__), "..", ".test_data"))

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.config import DBConfig, AppConfig
from src.database.connection import test_connection, Database
from src.database.sqlite_backend import SQLiteDatabase


def _forced_backend() -> str | None:
    """读取 QINGNING_TEST_DB_BACKEND 环境变量。"""
    val = os.environ.get("QINGNING_TEST_DB_BACKEND", "").strip().lower()
    return val or None


@pytest.fixture(scope="session")
def db_config():
    return DBConfig(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="123456",
        database="qingning_todo_test",
        charset="utf8mb4",
    )


@pytest.fixture(scope="session")
def _mysql_available(db_config):
    """检测 MySQL 是否可用。"""
    ok, _ = test_connection(db_config, check_database=False)
    return ok


@pytest.fixture(scope="session")
def _sqlite_db():
    """创建 SQLite 测试数据库。"""
    app_cfg = AppConfig()
    app_cfg.ensure_dir()
    db_path = os.path.join(app_cfg.config_dir, "test.db")
    # 删除旧测试文件及遗留的 journal/wal 文件，避免上次测试中断导致锁死
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    db = SQLiteDatabase(db_path)
    db.init_database()
    return db


@pytest.fixture(scope="session")
def db(_mysql_available, db_config, _sqlite_db):
    """返回测试数据库实例。

    优先使用 MySQL（如果可用），否则回退到 SQLite。
    通过 QINGNING_TEST_DB_BACKEND 可强制指定后端以便分别跑全量测试。

    MySQL 模式下，在 init_database 前后会各清理一次表，
    确保即使上次测试会话异常中断留下脏数据，本次也能从干净状态开始。
    """
    backend = _forced_backend()

    if backend == "mysql":
        if not _mysql_available:
            pytest.skip("QINGNING_TEST_DB_BACKEND=mysql 但 MySQL 不可用")
        conn = Database(db_config)
        # 先清理一次，避免上次会话异常中断留下的脏数据影响本次 init
        _cleanup_mysql_tables(conn)
        conn.init_database()
        yield conn
        # 会话结束后再次清理
        _cleanup_mysql_tables(conn)
        conn.close()
    elif backend == "sqlite":
        yield _sqlite_db
    elif _mysql_available:
        conn = Database(db_config)
        _cleanup_mysql_tables(conn)
        conn.init_database()
        yield conn
        _cleanup_mysql_tables(conn)
        conn.close()
    else:
        yield _sqlite_db


def _cleanup_mysql_tables(conn):
    """清理 MySQL 测试数据库中的表。

    使用 SET FOREIGN_KEY_CHECKS=0 避免外键约束阻止 DROP，
    确保即使上次测试会话异常中断也能彻底清理。
    """
    try:
        # 关闭外键约束检查
        try:
            conn.execute("SET FOREIGN_KEY_CHECKS=0")
        except Exception:
            pass
        tables = ["interrupt_details", "habit_checkins", "checkin_record",
                 "focus_record", "todo", "todo_group",
                 "future_plan", "goal", "focus_whitelist",
                 "lock_schedule", "settings", "white_noise",
                 "achievement", "user"]
        for tb in tables:
            try:
                conn.execute(f"DROP TABLE IF EXISTS `{tb}`")
            except Exception:
                pass
        # 重新启用外键约束检查
        try:
            conn.execute("SET FOREIGN_KEY_CHECKS=1")
        except Exception:
            pass
    except Exception:
        pass
