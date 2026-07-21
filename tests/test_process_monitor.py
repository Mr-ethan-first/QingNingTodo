"""进程监控纯函数测试（不依赖 GUI / 平台）。"""
import sys

from src.ui_qt.process_monitor import normalize, is_allowed, get_current_process_name


def test_normalize_strips_exe_and_spaces():
    assert normalize("Chrome.EXE") == "chrome"
    assert normalize("  FireFox ") == "firefox"
    assert normalize("notepad") == "notepad"
    assert normalize("") == ""


def test_is_allowed_matches_whitelist():
    allowed = {"chrome", "code"}
    # 前台进程名带 .exe，应与白名单（去后缀）匹配
    assert is_allowed("chrome.exe", allowed) is True
    assert is_allowed("CODE.EXE", allowed) is True
    # 不在白名单
    assert is_allowed("notepad.exe", allowed) is False


def test_is_allowed_treats_unreadable_as_safe():
    # 取不到前台进程时不判定违规（避免误杀）
    assert is_allowed("", {"chrome"}) is True
    assert is_allowed(None, {"chrome"}) is True


def test_get_current_process_name_returns_basename():
    import os
    name = get_current_process_name()
    assert name  # 非空（测试进程自身）
    assert name == os.path.basename(sys.executable).lower()
