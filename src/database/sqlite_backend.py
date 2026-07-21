"""SQLite 数据库后端。

提供与 MySQLDatabase (connection.Database) 相同的接口，
内部自动将 MySQL 风格 SQL 转换为 SQLite 兼容语法。

转换规则：
- %s → ?                      （参数占位符）
- %% → %                      （转义百分号）
- NOW() → datetime('now','localtime')
- DATE_FORMAT(col,'fmt') → strftime('fmt',col)
- HOUR(col) → CAST(strftime('%H',col) AS INTEGER)
- DAY(col)  → CAST(strftime('%d',col) AS INTEGER)
- MONTH(col)→ CAST(strftime('%m',col) AS INTEGER)
- YEAR(col) → CAST(strftime('%Y',col) AS INTEGER)
- INSERT ... ON DUPLICATE KEY UPDATE ... → INSERT OR REPLACE ...

SQLite 文件存储在用户主目录 ~/.qingning_todo/qingning_todo.db，
无需用户安装任何额外软件。
"""
import datetime
import os
import re
import sqlite3
from typing import Any, List, Optional

from src.config import AppConfig
from src.database import schema


# Python 3.12+ 弃用了 sqlite3 默认的 datetime/date adapter。
# 这里显式注册等价的 adapter/converter，保持原有行为不变，
# 同时消除 DeprecationWarning，避免未来 Python 版本移除默认实现后崩溃。
def _adapt_datetime(d: datetime.datetime) -> str:
    """与 Python 3.12 之前的默认 adapter 行为一致：
    使用空格分隔日期与时间。"""
    return d.strftime("%Y-%m-%d %H:%M:%S.%f")


def _adapt_date(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def _convert_timestamp(b: bytes) -> datetime.datetime:
    """与默认 TIMESTAMP converter 行为兼容：
    解析 'YYYY-MM-DD HH:MM:SS.ffffff' 或 'YYYY-MM-DD HH:MM:SS'。"""
    s = b.decode("ascii")
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def _convert_date(b: bytes) -> datetime.date:
    """与默认 DATE converter 行为兼容：解析 'YYYY-MM-DD'。"""
    s = b.decode("ascii")
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


sqlite3.register_adapter(datetime.datetime, _adapt_datetime)
sqlite3.register_adapter(datetime.date, _adapt_date)
sqlite3.register_converter("TIMESTAMP", _convert_timestamp)
sqlite3.register_converter("DATE", _convert_date)


def _convert_sql(sql: str) -> str:
    """将 MySQL 风格 SQL 转换为 SQLite 兼容 SQL。"""
    # 1. ON DUPLICATE KEY UPDATE → INSERT OR REPLACE
    #    先处理这个，避免后续 %s 替换干扰
    if re.search(r'\bON\s+DUPLICATE\s+KEY\s+UPDATE\b', sql, re.IGNORECASE):
        sql = re.sub(
            r'INSERT\s+INTO\b',
            'INSERT OR REPLACE INTO',
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r'\s+ON\s+DUPLICATE\s+KEY\s+UPDATE\s+.*$',
            '',
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # 2. %% → %  （pymysql 中 %% 转义为 %，SQLite 不需要）
    #    必须在 %s → ? 之前执行，避免 %%s 被错误转换
    sql = sql.replace('%%', '%')

    # 3. %s → ?
    sql = sql.replace('%s', '?')

    # 4. NOW() → datetime('now','localtime')
    sql = re.sub(
        r'\bNOW\s*\(\s*\)',
        "datetime('now','localtime')",
        sql,
        flags=re.IGNORECASE,
    )

    # 5. DATE_FORMAT(col, 'fmt') → strftime('fmt', col)
    #    注意参数顺序交换
    sql = re.sub(
        r"DATE_FORMAT\s*\(\s*([^,]+?)\s*,\s*'([^']+)'\s*\)",
        r"strftime('\2', \1)",
        sql,
        flags=re.IGNORECASE,
    )

    # 6. HOUR(col) → CAST(strftime('%H', col) AS INTEGER)
    sql = re.sub(
        r'\bHOUR\s*\(\s*([^)]+?)\s*\)',
        r"CAST(strftime('%H', \1) AS INTEGER)",
        sql,
        flags=re.IGNORECASE,
    )

    # 7. DAY(col) → CAST(strftime('%d', col) AS INTEGER)
    sql = re.sub(
        r'\bDAY\s*\(\s*([^)]+?)\s*\)',
        r"CAST(strftime('%d', \1) AS INTEGER)",
        sql,
        flags=re.IGNORECASE,
    )

    # 8. MONTH(col) → CAST(strftime('%m', col) AS INTEGER)
    sql = re.sub(
        r'\bMONTH\s*\(\s*([^)]+?)\s*\)',
        r"CAST(strftime('%m', \1) AS INTEGER)",
        sql,
        flags=re.IGNORECASE,
    )

    # 9. YEAR(col) → CAST(strftime('%Y', col) AS INTEGER)
    sql = re.sub(
        r'\bYEAR\s*\(\s*([^)]+?)\s*\)',
        r"CAST(strftime('%Y', \1) AS INTEGER)",
        sql,
        flags=re.IGNORECASE,
    )

    # 10. INSERT IGNORE → INSERT OR IGNORE
    sql = re.sub(
        r'\bINSERT\s+IGNORE\s+INTO\b',
        'INSERT OR IGNORE INTO',
        sql, flags=re.IGNORECASE)

    # 11. CURDATE() → date('now','localtime')
    sql = re.sub(
        r'\bCURDATE\s*\(\s*\)',
        "date('now','localtime')",
        sql, flags=re.IGNORECASE)

    # 12. CURTIME() → time('now','localtime')
    sql = re.sub(
        r'\bCURTIME\s*\(\s*\)',
        "time('now','localtime')",
        sql, flags=re.IGNORECASE)

    # 13. DATEDIFF(a, b) → (julianday(a) - julianday(b))
    sql = re.sub(
        r'\bDATEDIFF\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)',
        r"(julianday(\1) - julianday(\2))",
        sql, flags=re.IGNORECASE)

    # 14. LIMIT offset, count → LIMIT count OFFSET offset
    sql = re.sub(
        r'\bLIMIT\s+(\d+)\s*,\s*(\d+)',
        r'LIMIT \2 OFFSET \1',
        sql, flags=re.IGNORECASE)

    return sql


def _convert_schema_stmt(stmt: str) -> str:
    """将 MySQL DDL 语句转换为 SQLite 兼容 DDL。"""
    # 移除 ENGINE=... DEFAULT CHARSET=... COLLATE=...
    stmt = re.sub(
        r'\s*ENGINE\s*=\s*\w+', '', stmt, flags=re.IGNORECASE)
    stmt = re.sub(
        r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '', stmt, flags=re.IGNORECASE)
    stmt = re.sub(
        r'\s*COLLATE\s*=\s*\w+', '', stmt, flags=re.IGNORECASE)

    # AUTO_INCREMENT → AUTOINCREMENT
    stmt = re.sub(
        r'AUTO_INCREMENT', 'AUTOINCREMENT', stmt, flags=re.IGNORECASE)

    # UNIQUE KEY `name` (cols) → UNIQUE (cols)
    # SQLite 不支持给 UNIQUE 约束命名
    stmt = re.sub(
        r',\s*UNIQUE\s+KEY\s+`?\w*`?\s*\(([^)]+)\)',
        r', UNIQUE (\1)',
        stmt, flags=re.IGNORECASE)

    # 移除行内 KEY 定义（SQLite 用 CREATE INDEX 代替）
    # 匹配 `, KEY xxx (col)` 或 `, KEY (col)`（但不匹配 UNIQUE KEY 和 FOREIGN KEY，已上面处理）
    stmt = re.sub(
        r',\s*KEY\s+`?\w*`?\s*\([^)]+\)', '', stmt, flags=re.IGNORECASE)

    # FOREIGN KEY 保留（SQLite 支持，需 PRAGMA foreign_keys=ON）
    # 但需要确保格式正确：FOREIGN KEY (`col`) REFERENCES `table`(`id`) ON DELETE CASCADE
    # SQLite 支持这个语法，无需修改

    # 移除 COMMENT '...'
    stmt = re.sub(
        r"\s*COMMENT\s+'[^']*'", '', stmt, flags=re.IGNORECASE)

    # TINYINT → INTEGER (SQLite type affinity)
    stmt = re.sub(r'\bTINYINT\b', 'INTEGER', stmt, flags=re.IGNORECASE)
    # BIGINT → INTEGER
    stmt = re.sub(r'\bBIGINT\b', 'INTEGER', stmt, flags=re.IGNORECASE)
    # TIME → TEXT (SQLite 推荐用 TEXT 存储时间)
    stmt = re.sub(r'\bTIME\b', 'TEXT', stmt, flags=re.IGNORECASE)

    return stmt


def _extract_indexes(stmt: str) -> List[str]:
    """从 CREATE TABLE 语句中提取非唯一 KEY 定义，生成 CREATE INDEX 语句。

    排除 UNIQUE KEY（已由表定义中的 UNIQUE 约束覆盖）。
    """
    indexes = []
    # 先移除 UNIQUE KEY 定义，避免被下面的正则匹配到
    temp = re.sub(
        r'UNIQUE\s+KEY\s+`?\w*`?\s*\([^)]+\)', '', stmt, flags=re.IGNORECASE)
    # 匹配 KEY `idx_name` (`col`)
    for m in re.finditer(
        r'KEY\s+`?(\w+)`?\s*\(([^)]+)\)', temp, re.IGNORECASE
    ):
        idx_name = m.group(1)
        cols = m.group(2)
        # 提取表名
        table_match = re.search(
            r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?(\w+)`?', stmt,
            re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1)
            indexes.append(
                f'CREATE INDEX IF NOT EXISTS `{idx_name}` ON `{table_name}` ({cols})'
            )
    return indexes


class SQLiteDatabase:
    """SQLite 数据库后端，接口与 connection.Database 兼容。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ---- 连接管理 ----
    def connect(self, with_database: bool = True) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        # 启用外键约束
        self._conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def _ensure(self) -> None:
        if self._conn is None:
            self.connect()

    # ---- 初始化数据库与表 ----
    def init_database(self) -> None:
        """创建表结构并写入初始数据（事务保护）。"""
        self.connect()
        try:
            # 先执行所有 DDL（建表）
            for stmt in schema.SCHEMA_STATEMENTS:
                converted = _convert_schema_stmt(stmt)
                try:
                    self._conn.execute(converted)
                except Exception as ex:
                    print(f"[sqlite] DDL 执行失败: {ex}\n  SQL: {converted[:200]}")
            # 表创建成功后再创建索引
            for stmt in schema.SCHEMA_STATEMENTS:
                for idx_sql in _extract_indexes(stmt):
                    try:
                        self._conn.execute(idx_sql)
                    except Exception:
                        pass
            self._conn.commit()
            self._seed_data()
        except Exception:
            self._conn.rollback()
            raise

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

        # 白噪音（仅插入不存在的内置条目，保持ID稳定）
        for name, file_path, category, is_builtin in schema.DEFAULT_WHITE_NOISE:
            existing = self.query_one(
                "SELECT id FROM `white_noise` WHERE file_path=%s", (file_path,))
            if not existing:
                self.execute(
                    "INSERT INTO `white_noise`(name, file_path, category, is_builtin) "
                    "VALUES(%s,%s,%s,%s)",
                    (name, file_path, category, is_builtin))
            else:
                # 更新名称（schema 可能变更了名称）
                self.execute(
                    "UPDATE `white_noise` SET name=%s, category=%s WHERE file_path=%s",
                    (name, category, file_path))

        # 成就徽章
        cnt = self.query_one(
            "SELECT COUNT(*) AS c FROM `achievement` WHERE user_id=%s", (user_id,)
        )["c"]
        if cnt == 0:
            self.execute_many(
                "INSERT INTO `achievement`(user_id, badge_code, badge_name, unlocked) "
                "VALUES(%s,%s,%s,0)",
                [(user_id, code, title) for code, title in schema.DEFAULT_ACHIEVEMENTS],
            )

        # 默认设置
        existing = self.query_one("SELECT COUNT(*) AS cnt FROM settings")
        if existing and existing["cnt"] == 0:
            for key, value, desc in schema.DEFAULT_SETTINGS:
                self.execute(
                    "INSERT INTO `settings`(user_id, setting_key, setting_value, updated_at) "
                    "VALUES(%s,%s,%s,%s)",
                    (user_id, key, value, now))

    # ---- 通用执行 ----
    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """执行写操作，返回受影响行数或最后插入 id。"""
        self._ensure()
        converted = _convert_sql(sql)
        cur = self._conn.execute(converted, params or ())
        self._conn.commit()
        # INSERT 返回 lastrowid（新行 id），UPDATE/DELETE 返回 rowcount。
        # 注意：sqlite3 的 lastrowid 在 UPDATE 后不会清零，会保留上次 INSERT 的值，
        # 所以不能用 lastrowid or rowcount 的方式判断。
        stripped = converted.lstrip().upper()
        if stripped.startswith('INSERT'):
            return cur.lastrowid or cur.rowcount
        return cur.rowcount

    def execute_many(self, sql: str, seq_params: List[tuple]) -> int:
        """批量执行写操作，返回受影响行数。"""
        if not seq_params:
            return 0
        self._ensure()
        converted = _convert_sql(sql)
        cur = self._conn.executemany(converted, seq_params)
        self._conn.commit()
        return cur.rowcount

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[dict]:
        self._ensure()
        converted = _convert_sql(sql)
        cur = self._conn.execute(converted, params or ())
        return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
        self._ensure()
        converted = _convert_sql(sql)
        cur = self._conn.execute(converted, params or ())
        row = cur.fetchone()
        return dict(row) if row else None

    def scalar(self, sql: str, params: Optional[tuple] = None) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return None
        return next(iter(row.values()))


def create_sqlite_database(app_config: AppConfig) -> SQLiteDatabase:
    """创建 SQLite 数据库实例，路径基于 AppConfig 的配置目录。"""
    db_path = os.path.join(app_config.config_dir, "qingning_todo.db")
    return SQLiteDatabase(db_path)
