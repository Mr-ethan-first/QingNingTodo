"""配置读写测试。"""
import os

from src.config import AppConfig, DBConfig


def test_dbconfig_roundtrip():
    c = DBConfig(host="1.2.3.4", port=3307, user="u", password="p", database="d")
    d = c.to_dict()
    c2 = DBConfig.from_dict(d)
    assert c2.host == "1.2.3.4"
    assert c2.port == 3307
    assert c2.user == "u"
    assert c2.password == "p"
    assert c2.database == "d"


def test_appconfig_save_load(tmp_path):
    cfg = AppConfig(config_dir=str(tmp_path))
    assert cfg.load() is None
    assert not cfg.exists()

    db = DBConfig(host="127.0.0.1", port=3306, user="root", password="123456",
                  database="qingning_todo")
    cfg.save(db)
    assert cfg.exists()

    loaded = cfg.load()
    assert loaded is not None
    assert loaded.host == "127.0.0.1"
    assert loaded.database == "qingning_todo"
    assert loaded.password == "123456"


def test_appconfig_load_corrupt(tmp_path):
    cfg = AppConfig(config_dir=str(tmp_path))
    cfg.ensure_dir()
    with open(cfg.config_path, "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    assert cfg.load() is None


def test_dbconfig_defaults():
    c = DBConfig()
    assert c.host == "127.0.0.1"
    assert c.port == 3306
    assert c.charset == "utf8mb4"
