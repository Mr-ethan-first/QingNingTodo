"""应用配置管理。

负责数据库后端选择与连接信息的本地持久化（JSON 文件）。
支持两种数据库后端：
- sqlite（默认）：本地 SQLite 文件，无需安装，开箱即用
- mysql：需用户配置连接信息，适合多设备同步

配置文件结构：
{
  "db_backend": "sqlite",           // "sqlite" 或 "mysql"
  "database_config": { ... }        // MySQL 连接信息（仅 mysql 模式使用）
}
"""
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


# 配置文件存放目录：优先环境变量（便于测试隔离），否则用户主目录
def _config_dir() -> str:
    override = os.environ.get("QINGNING_TODO_HOME")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".qingning_todo")


CONFIG_FILE_NAME = "config.json"


@dataclass
class DBConfig:
    """MySQL 数据库连接配置（仅 mysql 模式使用）。"""
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "qingning_todo"
    charset: str = "utf8mb4"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "DBConfig":
        return DBConfig(
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 3306)),
            user=data.get("user", "root"),
            password=data.get("password", ""),
            database=data.get("database", "qingning_todo"),
            charset=data.get("charset", "utf8mb4"),
        )


class AppConfig:
    """应用配置读写。

    默认使用 SQLite 后端，无需用户配置即可启动。
    用户可在设置中切换为 MySQL 后端（需填写连接信息）。
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = config_dir or _config_dir()
        self.config_path = os.path.join(self.config_dir, CONFIG_FILE_NAME)

    def ensure_dir(self) -> None:
        os.makedirs(self.config_dir, exist_ok=True)

    def exists(self) -> bool:
        return os.path.isfile(self.config_path)

    @property
    def db_backend(self) -> str:
        """返回当前数据库后端：'sqlite' 或 'mysql'。默认 sqlite。"""
        if not self.exists():
            return "sqlite"
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("db_backend", "sqlite")
        except (json.JSONDecodeError, OSError):
            return "sqlite"

    def load(self) -> Optional[DBConfig]:
        """读取 MySQL 连接配置（仅 mysql 模式使用）。不存在返回 None。"""
        if not self.exists():
            return None
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db = data.get("database_config")
            if not db:
                return None
            return DBConfig.from_dict(db)
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, db_config: DBConfig, backend: str = "mysql") -> None:
        """保存数据库配置。

        Args:
            db_config: MySQL 连接配置
            backend: 数据库后端类型 ("sqlite" 或 "mysql")
        """
        self.ensure_dir()
        payload = {
            "db_backend": backend,
            "database_config": db_config.to_dict(),
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def save_backend(self, backend: str) -> None:
        """仅切换数据库后端，保留已有的 MySQL 配置。"""
        self.ensure_dir()
        existing = {}
        if self.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        existing["db_backend"] = backend
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
