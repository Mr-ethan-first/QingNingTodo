"""数据库连接与初始化测试。"""
from src.config import DBConfig
from src.database.connection import test_connection as check_conn


def test_connection_success(db_config, _mysql_available):
    if not _mysql_available:
        import pytest
        pytest.skip("MySQL 不可用")
    ok, msg = check_conn(db_config, check_database=False)
    assert ok
    assert "连接成功" in msg


def test_connection_bad_password(db_config, _mysql_available):
    if not _mysql_available:
        import pytest
        pytest.skip("MySQL 不可用")
    bad = DBConfig(host=db_config.host, port=db_config.port, user=db_config.user,
                   password="___definitely_wrong_pwd___", database=db_config.database)
    ok, msg = check_conn(bad, check_database=False)
    assert not ok
    assert "认证失败" in msg or "失败" in msg


def test_connection_bad_host():
    bad = DBConfig(host="10.255.255.1", port=3306, user="root", password="x")
    ok, msg = check_conn(bad, check_database=False)
    assert not ok


def test_init_database_creates_tables(db):
    """验证 init_database 创建了所有预期表。"""
    # 兼容 MySQL (SHOW TABLES) 和 SQLite (sqlite_master)
    # 注意：两个 Database 类都有 _conn 属性，必须用类名区分。
    from src.database.sqlite_backend import SQLiteDatabase
    if isinstance(db, SQLiteDatabase):
        tables = db.query_all(
            "SELECT name FROM sqlite_master WHERE type='table'")
        names = {row["name"] for row in tables}
    else:  # MySQL Database
        tables = db.query_all("SHOW TABLES")
        names = {list(row.values())[0] for row in tables}
    expected = {
        "user", "todo_group", "todo", "focus_record", "goal", "future_plan",
        "checkin_record", "achievement", "focus_whitelist", "lock_schedule",
        "white_noise", "settings", "interrupt_details", "habit_checkins",
    }
    assert expected.issubset(names)


def test_seed_data(db):
    # 默认用户存在
    user = db.query_one("SELECT * FROM `user` LIMIT 1")
    assert user is not None
    # 白噪音已写入
    cnt = db.scalar("SELECT COUNT(*) FROM `white_noise`")
    assert cnt >= 1
    # 成就徽章已写入
    cnt2 = db.scalar("SELECT COUNT(*) FROM `achievement`")
    assert cnt2 >= 1


def test_init_idempotent(db):
    """重复初始化不应报错，也不应重复插入种子数据。"""
    before = db.scalar("SELECT COUNT(*) FROM `white_noise`")
    db.init_database()
    after = db.scalar("SELECT COUNT(*) FROM `white_noise`")
    assert before == after
