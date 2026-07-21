"""打包脚本：使用 PyInstaller 生成单文件 exe（最小化体积）。

用法：
    python build.py

生成结果：dist/青柠待办.exe

最小化原则：
- 应用基于 PyQt6（仅用到 QtCore / QtGui / QtWidgets / QtSvg），
  PyInstaller 的 PyQt6 hook 会自动按需收集 Qt DLL，
  无需手动排除 PyQt6 子模块（手动排除反而会阻止 hook 收集依赖 DLL）；
- 同时支持 SQLite（默认）与 MySQL 两种后端：pymysql 必须打包进 exe，
  以便用户在设置中切换为 MySQL 模式；
- 开发/测试/科学计算库（pytest、numpy、PIL、scipy、pandas 等）一律排除；
- 单文件（onefile）模式，便于分发与清理旧版本。
- 音频资源（assets/sounds/）与帮助文档自动打包。

关键修复：
  系统 PATH 中若存在 Anaconda3 的 Qt6 DLL（与 PyQt6 自带版本不一致），
  PyInstaller 会错误收集冲突版本的 Qt6Core.dll，导致运行时
  "ImportError: DLL load failed while importing QtCore: 找不到指定的程序"。
  本脚本在调用 PyInstaller 前清理 PATH，仅保留 Python 与系统目录。
"""
import os
import subprocess
import sys

APP_NAME = "青柠待办"
ENTRY = os.path.join("src", "main.py")
DIST_DIR = "dist"

# 未使用 / 开发依赖，打包时一律排除以减小体积。
# 注意：
# - pymysql 必须保留（MySQL 后端需要），不可排除。
# - 不再排除 PyQt6 子模块：PyInstaller 的 hook 会按需收集，
#   手动排除会阻止对应 hook 运行，可能导致 Qt6 依赖 DLL 缺失。
EXCLUDES = [
    # 开发 / 测试
    "pytest", "pytest_timeout", "unittest", "doctest",
    "setuptools", "pip", "wheel", "pkg_resources",
    "pydoc_data",
    # 交互式 / Notebook
    "IPython", "jupyter", "nbconvert", "nbformat",
    "ipykernel", "traitlets",
    # 图形 / 科学计算（本项目未使用）
    "numpy", "scipy", "pandas", "matplotlib", "PIL", "Pillow",
    "PyQt5", "PySide2", "PySide6", "qtpy",
    # 音频转换库（仅用户上传非WAV时需要，有优雅降级；内置音频已全部WAV）
    "soundfile", "sounddevice", "imageio_ffmpeg",
    # 注意：PyQt6.sip 是 PyQt6 运行必需模块，不可排除！
    "tkinter",
]


def _clean_path():
    """清理 PATH，移除可能导致 Qt6 DLL 冲突的目录（如 Anaconda3）。

    PyInstaller 在收集 DLL 时会搜索 PATH，若 PATH 中存在其他 Qt6
    安装（Anaconda3、Qt Creator 等），可能收集到错误版本的 Qt6Core.dll，
    导致运行时 "procedure not found" 错误。
    """
    python_dir = os.path.dirname(sys.executable)
    # 保留的系统目录
    safe_dirs = {
        python_dir,
        os.path.join(python_dir, "Scripts"),
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64"),
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows")),
    }
    old_path = os.environ.get("PATH", "")
    parts = old_path.split(os.pathsep)
    cleaned = []
    removed = []
    for p in parts:
        p_norm = os.path.normpath(p).lower() if p else ""
        if not p_norm:
            continue
        # 移除 Anaconda / conda / 其他可能含 Qt6 DLL 的目录
        if any(kw in p_norm for kw in ("anaconda", "conda", "qt", "qt6")):
            removed.append(p)
            continue
        cleaned.append(p)
    # 确保安全目录在前
    for d in reversed(list(safe_dirs)):
        d_norm = os.path.normpath(d)
        if d_norm not in [os.path.normpath(c) for c in cleaned]:
            cleaned.insert(0, d_norm)
    new_path = os.pathsep.join(cleaned)
    os.environ["PATH"] = new_path
    print(f"  PATH 清理: 移除 {len(removed)} 个冲突目录")
    for r in removed:
        print(f"    - {r}")
    print()


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    # 清理 PATH，避免 Anaconda3 等 Qt6 DLL 冲突
    _clean_path()

    args = [
        sys.executable, "-m", "PyInstaller",
        ENTRY,
        f"--name={APP_NAME}",
        "--noconsole",
        "--onefile",
        f"--distpath={DIST_DIR}",
        # 数据文件：音频资源
        "--add-data=assets/sounds;assets/sounds",
        # 数据文件：帮助文档（落入 help/ 目录）
        "--add-data=使用说明书.md;help",
        "--add-data=README.md;help",
        # 排除非必要包，最小化体积
        *[f"--exclude-module={m}" for m in EXCLUDES],
        # 关闭 UPX：避免杀毒误报
        "--noupx",
        # 覆盖已有输出
        "--noconfirm",
        # 清理缓存，确保重新收集 DLL
        "--clean",
    ]

    print("=" * 60)
    print(f"  打包应用: {APP_NAME}")
    print(f"  入口脚本: {ENTRY}")
    print(f"  输出目录: {DIST_DIR}/")
    print(f"  排除模块: {len(EXCLUDES)} 个")
    print("=" * 60)
    print()
    print("执行:", " ".join(args))
    print()
    ret = subprocess.call(args)

    if ret == 0:
        exe = os.path.join(root, DIST_DIR, f"{APP_NAME}.exe")
        if os.path.exists(exe):
            size_mb = os.path.getsize(exe) / (1024 * 1024)
            print()
            print("=" * 60)
            print(f"  打包完成!")
            print(f"  EXE 路径: {exe}")
            print(f"  EXE 大小: {size_mb:.1f} MB")
            print("=" * 60)
        else:
            print(f"\n警告: EXE 文件未找到: {exe}")
    else:
        print(f"\n打包失败，返回码: {ret}")
    return ret


if __name__ == "__main__":
    sys.exit(main())
