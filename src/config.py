"""应用配置管理。

负责数据库连接信息与应用设置的本地持久化（JSON 文件）。
由于数据库连接建立前无法使用 MySQL 存储，连接信息保存在用户主目录下。
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
    """数据库连接配置。"""
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
    """应用配置读写。"""

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = config_dir or _config_dir()
        self.config_path = os.path.join(self.config_dir, CONFIG_FILE_NAME)

    def ensure_dir(self) -> None:
        os.makedirs(self.config_dir, exist_ok=True)

    def exists(self) -> bool:
        return os.path.isfile(self.config_path)

    def load(self) -> Optional[DBConfig]:
        """读取数据库配置，不存在返回 None。"""
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

    def save(self, db_config: DBConfig) -> None:
        """保存数据库配置。"""
        self.ensure_dir()
        payload = {"database_config": db_config.to_dict()}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
