"""打包脚本：使用 `flet pack`（基于 PyInstaller）生成单文件 exe。

用法：
    python build.py

生成结果：dist/番茄ToDo.exe

说明：
Flet 应用通过 Flutter 引擎渲染，使用官方 `flet pack` 命令打包。
该命令会启动一个本地服务（默认 http），桌面端以独立窗口运行。
"""
import os
import shutil
import subprocess
import sys

APP_NAME = "番茄ToDo"
ENTRY = os.path.join("src", "main.py")


def _find_flet() -> str:
    """定位 flet 可执行文件（新版 flet 无 `python -m flet` 入口）。"""
    exe = shutil.which("flet")
    if exe:
        return exe
    scripts = os.path.join(os.path.dirname(sys.executable), "Scripts")
    for name in ("flet.exe", "flet"):
        cand = os.path.join(scripts, name)
        if os.path.exists(cand):
            return cand
    # 兜底：尝试 flet_cli 模块
    return None


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    flet_exe = _find_flet()
    if flet_exe:
        base = [flet_exe, "pack"]
    else:
        base = [sys.executable, "-m", "flet_cli", "pack"]

    args = base + [
        ENTRY,
        f"-n={APP_NAME}",
        # 非交互，跳过覆盖确认
        "-y",
        # 确保收集数据层与数据库驱动
        "--hidden-import=pymysql",
        # 单目录（Flet 桌面应用推荐，避免单文件解压缓慢）
        "--onedir",
        f"--distpath={os.path.join(root, 'dist_new')}",  # 规范输出目录（dist被Defender锁定时用dist_new）
        # 以下透传给底层 PyInstaller（flet pack 不直接支持）
        # 收集 src 下全部子模块，确保各页面被打包
        "--pyinstaller-build-args=--collect-submodules=src",
        # 应用不使用 Qt/tk，环境中多套 Qt 绑定会导致打包冲突，全部排除
        "--pyinstaller-build-args=--exclude-module=PyQt5",
        "--pyinstaller-build-args=--exclude-module=PyQt6",
        "--pyinstaller-build-args=--exclude-module=PySide2",
        "--pyinstaller-build-args=--exclude-module=PySide6",
        "--pyinstaller-build-args=--exclude-module=qtpy",
        "--pyinstaller-build-args=--exclude-module=tkinter",
        "--pyinstaller-build-args=--exclude-module=matplotlib",
        # 关闭 UPX：UPX 压缩的 exe 易被 Windows Defender 实时扫描锁定，
        # 导致最终 update_exe_pe_checksum 因 Permission denied 失败。
        "--pyinstaller-build-args=--noupx",
    ]
    print("执行:", " ".join(args))
    ret = subprocess.call(args)
    if ret == 0:
        exe = os.path.join(root, "dist_new", f"{APP_NAME}", f"{APP_NAME}.exe")
        print(f"\n打包完成：{exe}")
    else:
        print("\n打包失败，返回码:", ret)
    return ret


if __name__ == "__main__":
    sys.exit(main())
