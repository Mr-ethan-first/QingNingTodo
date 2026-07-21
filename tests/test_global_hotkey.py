"""全局快捷键（GlobalHotkey）测试。

仅在 Windows 平台验证快捷键组合解析逻辑；真实注册依赖系统消息循环，
在测试环境中 skip。
"""
import pytest

from src.ui_qt.global_hotkey import GlobalHotkey, _AVAILABLE

pytestmark = pytest.mark.skipif(
    not _AVAILABLE, reason="非 Windows 平台，无全局热键 API")


def test_parse_ctrl_shift_a():
    mods, vk = GlobalHotkey.parse_combo("Ctrl+Shift+A")
    assert mods & 0x0002          # MOD_CONTROL
    assert mods & 0x0004          # MOD_SHIFT
    assert vk == 0x41             # 'A'


def test_parse_alt_and_win():
    mods, vk = GlobalHotkey.parse_combo("Win+Alt+F5")
    assert mods & 0x0008          # MOD_WIN
    assert mods & 0x0001          # MOD_ALT
    assert vk == 0x74             # F5


def test_parse_lowercase_normalized():
    mods, vk = GlobalHotkey.parse_combo("ctrl+shift+b")
    assert mods & 0x0002
    assert mods & 0x0004
    assert vk == 0x42             # 'B'


def test_parse_invalid_key_returns_zero_vk():
    mods, vk = GlobalHotkey.parse_combo("Ctrl+Shift+???")
    assert vk == 0


def test_parse_digits():
    mods, vk = GlobalHotkey.parse_combo("Ctrl+1")
    assert mods & 0x0002
    assert vk == 0x31             # '1'


def test_start_returns_false_on_unknown_key():
    hk = GlobalHotkey("Ctrl+Shift+???")
    # 未真正注册（vk=0），start 应返回 False 且不抛异常
    assert hk.start() is False
