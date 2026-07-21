"""全局快捷键（Windows 真实系统热键）。

通过 ctypes 调用 user32 的 RegisterHotKey，在独立工作线程中泵取消息，
捕获 WM_HOTKEY 后以 Qt 信号 `activated` 跨线程通知主线程，用于"快速唤起青柠待办"。

仅 Windows 平台可用；其它平台 `GlobalHotkey.start()` 返回 False，调用方应静默降级。
"""
import ctypes
import threading
from typing import Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import ctypes.wintypes as wintypes
    user32 = ctypes.windll.user32  # type: ignore
    HWND_MESSAGE = wintypes.HWND(-3)
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    # 常用非字符按键的虚拟键码
    _VK_MAP = {
        "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
        "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
        "enter": 0x0D, "return": 0x0D, "space": 0x20, "tab": 0x09,
        "esc": 0x1B, "escape": 0x1B, "delete": 0x2E, "del": 0x2E,
        "backspace": 0x08, "back": 0x08,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "home": 0x24, "end": 0x23, "pgup": 0x21, "pageup": 0x21,
        "pgdn": 0x22, "pagedown": 0x22, "insert": 0x2D, "ins": 0x2D,
    }

    # 设置精确参数类型，避免 64 位平台指针截断
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    user32.RegisterHotKey.restype = ctypes.c_int
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = ctypes.c_int
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = ctypes.c_int
    user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = ctypes.c_int
    LPMSG = ctypes.POINTER(wintypes.MSG)
    user32.GetMessageW.argtypes = [LPMSG, wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
    user32.GetMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = [LPMSG]
    user32.TranslateMessage.restype = ctypes.c_int
    user32.DispatchMessageW.argtypes = [LPMSG]
    user32.DispatchMessageW.restype = ctypes.c_int
    user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
    user32.VkKeyScanW.restype = ctypes.c_short

    _AVAILABLE = True
except Exception:  # pragma: no cover - 非 Windows 平台
    _AVAILABLE = False
    user32 = None
    HWND_MESSAGE = None
    MOD_ALT = MOD_CONTROL = MOD_SHIFT = MOD_WIN = 0
    WM_HOTKEY = WM_QUIT = 0
    _VK_MAP = {}


class GlobalHotkey(QObject):
    """注册一个全局快捷键，触发时发出 `activated` 信号。"""

    activated = pyqtSignal()

    def __init__(self, combo: str = "Ctrl+Shift+A", parent: Optional[QObject] = None):
        super().__init__(parent)
        self._combo = combo
        self._id = 0xA1  # 模块内固定热键 ID
        self._hwnd = None
        self._mods = 0
        self._vk = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def combo(self) -> str:
        return self._combo

    @staticmethod
    def parse_combo(combo: str) -> Tuple[int, int]:
        """解析 "Ctrl+Shift+A" 形式为 (modifiers, virtual_key)。

        无法识别的按键返回 virtual_key=0，调用方据此跳过注册。
        """
        mods = 0
        key = ""
        for part in combo.replace(" ", "").split("+"):
            p = part.lower()
            if p in ("ctrl", "control"):
                mods |= MOD_CONTROL
            elif p == "shift":
                mods |= MOD_SHIFT
            elif p in ("alt", "menu"):
                mods |= MOD_ALT
            elif p == "win":
                mods |= MOD_WIN
            else:
                key = part
        vk = 0
        if key:
            k = key.lower()
            if k in _VK_MAP:
                vk = _VK_MAP[k]
            elif len(key) == 1:
                try:
                    vk = user32.VkKeyScanW(key[0]) & 0xFF  # type: ignore
                except Exception:
                    vk = 0
        return mods, vk

    def _parse(self):
        self._mods, self._vk = self.parse_combo(self._combo)

    def start(self) -> bool:
        """启动热键监听；成功返回 True，不可用或已运行返回 False。"""
        if not _AVAILABLE or self._running:
            return _AVAILABLE and self._running
        self._parse()
        if self._vk == 0:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """停止监听并注销热键。"""
        self._running = False
        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)  # type: ignore
            except Exception:
                pass

    def _run(self):
        try:
            hwnd = user32.CreateWindowExW(  # type: ignore
                0, "STATIC", "QingNingHotkey", 0,
                0, 0, 0, 0, HWND_MESSAGE, None, None, None)
        except Exception:
            self._running = False
            return
        if not hwnd:
            self._running = False
            return
        self._hwnd = hwnd
        if not user32.RegisterHotKey(hwnd, self._id, self._mods, self._vk):  # type: ignore
            self._running = False
            try:
                user32.DestroyWindow(hwnd)  # type: ignore
            except Exception:
                pass
            self._hwnd = None
            return

        msg = wintypes.MSG()  # type: ignore
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)  # type: ignore
            if ret == 0 or ret == -1:  # WM_QUIT 或错误
                break
            if msg.message == WM_HOTKEY:
                self.activated.emit()
            user32.TranslateMessage(ctypes.byref(msg))  # type: ignore
            user32.DispatchMessageW(ctypes.byref(msg))  # type: ignore

        try:
            user32.UnregisterHotKey(hwnd, self._id)  # type: ignore
            user32.DestroyWindow(hwnd)  # type: ignore
        except Exception:
            pass
        self._hwnd = None
