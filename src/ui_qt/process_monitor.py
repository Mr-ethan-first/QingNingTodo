"""前台进程监控（学霸模式底层能力）。

仅在 Windows 上通过 ctypes 读取前台窗口所属进程名；其它平台或读取失败
时返回空串（上层据此"不判定违规"，避免误杀）。纯函数 `normalize` /
`is_allowed` 可脱离 GUI 单独测试。
"""
import os
import sys

try:
    import ctypes
    from ctypes import wintypes
except Exception:  # pragma: no cover - 非 Windows 环境
    ctypes = None


def normalize(name: str) -> str:
    """将进程名规格化：转小写、去空白、去掉 .exe 后缀。"""
    if not name:
        return ""
    name = name.strip().lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def is_allowed(foreground: str, allowed_set) -> bool:
    """判断前台进程是否在被允许的进程集合中。"""
    if not foreground:
        # 取不到前台进程时不判定违规（避免误杀）。
        return True
    fg = normalize(foreground)
    if not fg:
        return True
    return fg in allowed_set


def get_current_process_name() -> str:
    """返回本应用进程名（小写 basename），失败时返回空串。"""
    try:
        return os.path.basename(sys.executable).lower()
    except Exception:
        return ""


def get_foreground_process_name() -> str:
    """返回当前前台窗口所属进程的 basename（小写），失败/非 Windows 返回空串。"""
    if ctypes is None:
        return ""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        hproc = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
        if not hproc:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(2048)
            size = wintypes.DWORD(2048)
            if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        return ""
