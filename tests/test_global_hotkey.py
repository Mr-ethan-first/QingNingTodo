"""全局快捷键（系统热键）单元测试：组合键解析、真实注册可用性、失败反馈。

覆盖本次修复点：
- 无效组合键（无有效按键）应同步返回 False 并通过 `_last_error` 暴露原因；
- 有效组合键在 Windows 上应真实注册成功（证明全局热键可用）。
"""
import pytest

from src.ui_qt.global_hotkey import GlobalHotkey, _AVAILABLE


def test_parse_combo_mods_and_vk():
    mods, vk = GlobalHotkey.parse_combo("Ctrl+Shift+A")
    assert mods & 0x0002 and mods & 0x0004  # CONTROL + SHIFT
    assert vk == 0x41                       # 'A'


def test_parse_combo_function_key():
    mods, vk = GlobalHotkey.parse_combo("F5")
    assert mods == 0
    assert vk == 0x74


def test_parse_combo_win_mod():
    mods, vk = GlobalHotkey.parse_combo("Win+D")
    assert mods & 0x0008
    assert vk == 0x44


def test_parse_combo_no_key_returns_zero_vk():
    # 无有效按键 -> vk==0，start() 应据此返回 False
    _, vk = GlobalHotkey.parse_combo("Ctrl+Ctrl")
    assert vk == 0


def test_start_invalid_combo_returns_false_with_reason():
    hk = GlobalHotkey("Ctrl+Ctrl")
    ok = hk.start()
    assert ok is False
    assert hk._last_error, "无效组合键应给出失败原因"
    assert hk._running is False


def test_start_unavailable_platform_returns_false():
    # 非 Windows 平台 _AVAILABLE 为 False，start() 应返回 False 且不残留线程
    if _AVAILABLE:
        pytest.skip("当前为 Windows 平台，跳过不可用分支")
    hk = GlobalHotkey("Ctrl+Shift+A")
    assert hk.start() is False
    assert hk._last_error
    assert hk._running is False


@pytest.mark.skipif(not _AVAILABLE, reason="非 Windows 平台无系统热键")
def test_start_valid_combo_registers_and_stops():
    hk = GlobalHotkey("Ctrl+Shift+A")
    ok = hk.start()
    assert ok is True
    assert hk._hwnd is not None
    hk.stop()
    # stop() 异步投递 WM_QUIT，需等待工作线程完成注销与销毁窗口
    if hk._thread is not None:
        hk._thread.join(timeout=3)
    assert hk._hwnd is None
