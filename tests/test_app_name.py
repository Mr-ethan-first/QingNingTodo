"""应用命名回归测试：已改为青柠待办。"""
from src import __app_name__, __version__


def test_app_name_is_qingning():
    assert __app_name__ == "青柠待办", f"应用名应为「青柠待办」，实际为「{__app_name__}」"


def test_version_exists():
    assert isinstance(__version__, str)
    assert __version__
