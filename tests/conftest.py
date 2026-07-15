"""pytest 公共夹具。

使用独立的测试数据库，避免污染业务数据。
数据库连接信息可通过环境变量覆盖：
    TEST_DB_HOST / TEST_DB_PORT / TEST_DB_USER / TEST_DB_PASSWORD / TEST_DB_NAME
默认：127.0.0.1:3306 root/123456 qingning_todo_pytest
若数据库不可用，相关测试将被跳过。

为提升速度：数据库与表结构在整个测试会话中只创建一次；
每个测试前清空业务数据并重新写入种子数据（DELETE 远快于 DROP/CREATE DATABASE）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DBConfig  # noqa: E402
from src.database.connection import Database, test_connection  # noqa: E402

# 需要在每个测试前清空的业务表（按可安全删除顺序）
_BUSINESS_TABLES = [
    "focus_record", "todo", "todo_group", "goal", "future_plan",
    "checkin_record", "achievement", "focus_whitelist", "lock_schedule",
    "settings", "white_noise", "user",
]


def _test_config() -> DBConfig:
    return DBConfig(
        host=os.environ.get("TEST_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("TEST_DB_PORT", "3306")),
        user=os.environ.get("TEST_DB_USER", "root"),
        password=os.environ.get("TEST_DB_PASSWORD", "123456"),
        database=os.environ.get("TEST_DB_NAME", "qingning_todo_pytest"),
    )


@pytest.fixture(scope="session")
def db_config() -> DBConfig:
    return _test_config()


@pytest.fixture(scope="session")
def _mysql_available(db_config) -> bool:
    ok, _ = test_connection(db_config, check_database=False)
    return ok


@pytest.fixture(scope="session")
def _database(db_config, _mysql_available):
    """会话级：创建测试库与表结构一次。"""
    if not _mysql_available:
        pytest.skip("MySQL 服务不可用，跳过数据库测试")

    import pymysql
    conn = pymysql.connect(
        host=db_config.host, port=int(db_config.port),
        user=db_config.user, password=db_config.password, autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{db_config.database}`")
    conn.close()

    database = Database(db_config)
    database.init_database()
    yield database

    try:
        database.execute(f"DROP DATABASE IF EXISTS `{db_config.database}`")
    except Exception:  # noqa: BLE001
        pass
    database.close()


@pytest.fixture()
def db(_database):
    """函数级：清空业务数据并重新播种，保证测试隔离。

    使用 DELETE 而非 TRUNCATE：TRUNCATE 属 DDL，在开启 fsync 的
    环境下每次数百毫秒~秒级，DELETE 则为毫秒级。
    """
    for table in _BUSINESS_TABLES:
        _database.execute(f"DELETE FROM `{table}`")
    # 重新写入种子数据（默认用户、白噪音、成就徽章）
    _database._seed_data()
    return _database
