# -*- coding: utf-8 -*-
"""框架验证测试。"""
import pytest


def test_framework_works():
    """验证 pytest 基本功能正常。"""
    assert 1 + 1 == 2


def test_db_fixture(db):
    """验证数据库 fixture 正常工作。"""
    from src.database.dao import SettingsDAO
    dao = SettingsDAO(db)
    val = dao.get("theme", "light")
    assert val is not None


def test_db_with_data_fixture(db_with_data):
    """验证带数据的数据库 fixture 正常工作。"""
    from src.database.dao import TodoDAO
    dao = TodoDAO(db_with_data)
    todos = dao.list()
    assert len(todos) == 3
