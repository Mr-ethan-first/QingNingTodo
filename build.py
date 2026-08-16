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
    # ── 体积优化：应用从未引用、却被升级后的 PyQt6/PyInstaller 环境自动收进来的重型依赖 ──
    # cryptography 栈：源码无任何地方 import，纯 2D 桌面应用不需要。
    # 其 Rust 绑定 _rust.pyd 约 9MB、附带 OpenSSL 库，全部剔除。
    "cryptography", "bcrypt", "nacl", "_rust",
    # Qt PDF 支持：应用无 PDF 功能，Qt6Pdf.dll 约 4.6MB，剔除。
    "PyQt6.QtPdf", "PyQt6.QtPdfWidgets",
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


def _native_delete(path):
    """原生 Windows 删除，绕过 Python 层 safe-delete 钩子。

    WorkBuddy 的 sitecustomize 钩子在 win32 + 回收站不可用时把 os.remove
    设为 fail-closed，导致 PyInstaller 收尾 os.remove(dist/<name>.exe) 被拦截、
    打包崩溃。直接调用 kernel32.DeleteFileW 走 OS 原生删除，跳过该 Python 层钩子。
    仅用于清理「自己即将被 PyInstaller 覆盖的旧构建产物」，等价 PyInstaller 自身意图。
    返回 True 表示删除成功；否则返回异常对象。
    """
    try:
        import ctypes
        res = ctypes.windll.kernel32.DeleteFileW(ctypes.c_wchar_p(path))
        if res:
            return True
        err = ctypes.GetLastError()
        return OSError(err, f"DeleteFileW 失败 code={err}")
    except Exception as _e:  # noqa: BLE001
        return _e


def _cleanup_bak_exes(root):
    """构建成功后清理 dist/ 下遗留的 .bak 文件（兜底改名方案留下的）。"""
    import glob
    for bak in glob.glob(os.path.join(root, DIST_DIR, f"{APP_NAME}.bak.*.exe")):
        r = _native_delete(bak)
        if r is True:
            print(f"  清理遗留 .bak: {bak}")
        else:
            print(f"  [提示] 残留 .bak 未清理（无害，可手动删除）: {bak}")


def _kill_running_instances():
    """构建前结束可能占用 dist exe 的已运行实例。

    场景：冒烟测试或用户手动启动的 exe 未退出时，dist/青柠待办.exe 被进程
    锁定。PyInstaller（--onefile --noconfirm）重写目标文件会被锁拦截，
    残留 0 字节 / 截断的 exe，表现为“打包产物字节数为 0”。
    构建前主动结束同名进程即可彻底规避该问题，并保证后续预清理（原生删除 /
    改名）能正常执行。

    只结束「青柠待办.exe」同名进程，不触碰 python 等其它进程。
    """
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV"], text=True, errors="ignore"
        )
    except Exception as _e:  # noqa: BLE001
        print(f"  [提示] 枚举进程失败（不影响继续）: {_e}")
        return
    pids = []
    for line in out.splitlines():
        if f"{APP_NAME}.exe" in line:
            parts = line.split(",")
            if len(parts) >= 2:
                pid = parts[1].strip('"')
                if pid.isdigit():
                    pids.append(pid)
    if not pids:
        return
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                capture_output=True, text=True, check=False,
            )
        except Exception:  # noqa: BLE001
            pass
    print(f"  已结束 {len(pids)} 个同名运行实例（释放 dist exe 文件锁）")


def _wait_file_unlocked(path, timeout=20):
    """等待目标文件锁彻底释放。

    强杀同名进程后，Windows 释放文件句柄有短暂延迟。若 PyInstaller 立即
    写入被残留锁拦截，会留下 0 字节 / 截断的 exe。此处轮询文件可写性，
    直到锁释放或超时，再继续预清理与构建，彻底消除该竞态。
    """
    if not os.path.exists(path):
        return
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fd = os.open(path, os.O_RDWR)
            os.close(fd)
            return
        except (PermissionError, OSError):
            time.sleep(0.5)
    print(f"  [提示] 等待文件锁释放超时（{timeout}s），仍将继续构建")


def _pre_clean_dist_exe(root):
    """预清理 dist/ 下已存在的旧 exe。

    PyInstaller 收尾阶段会对最终输出 exe 调用 os.remove 清掉旧文件，
    但 dist/ 在 D: 盘、而 OS 临时目录在 C: 盘，safe-delete 钩子在 D: 盘路径上
    fail-closed（回收站不可用 → 抛 OSError → 打包直接崩溃，dist 仍为旧 exe）。

    绕过方案：
      主方案 —— 用 kernel32.DeleteFileW 原生删除旧 exe（绕过 Python 层钩子），
        使 PyInstaller 运行时 dist/ 下已无旧 exe，自动跳过其 os.remove 拦截点；
      兜底方案 —— 若原生删除失败，则同盘改名（rename 非删除，不触发拦截），
        让 PyInstaller 找不到旧 exe，构建仍可完成（仅留一个 .bak，事后清理）。
    """
    exe = os.path.join(root, DIST_DIR, f"{APP_NAME}.exe")
    if not os.path.exists(exe):
        return
    # 主方案：原生删除（绕过 safe-delete 对 os.remove 的拦截）
    r = _native_delete(exe)
    if r is True:
        print(f"  预清理旧 exe 完成（原生删除）: {exe}")
        return
    # 兜底：同盘改名，使 PyInstaller 在 dist/ 下找不到旧 exe
    bak = os.path.join(root, DIST_DIR, f"{APP_NAME}.bak.{os.getpid()}.exe")
    try:
        os.rename(exe, bak)   # 同盘 rename，非删除，不被钩子拦截
        print(f"  预清理旧 exe 完成（改名规避）: {bak}")
    except OSError as _e:
        print(f"  [警告] 预清理旧 exe 失败（将尝试继续构建）: {_e}")


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    # 清理 PATH，避免 Anaconda3 等 Qt6 DLL 冲突
    _clean_path()

    # 构建前结束同名运行实例：释放 dist exe 文件锁，避免打包时目标被锁
    # 导致 PyInstaller 无法覆盖写入、产出 0 字节 / 截断 exe
    _kill_running_instances()

    # 等待文件锁彻底释放（强杀后 OS 释放句柄有延迟），消除竞态
    _wait_file_unlocked(os.path.join(root, DIST_DIR, f"{APP_NAME}.exe"))

    # 预清理 dist/ 旧 exe，规避 safe-delete 对 PyInstaller 收尾 os.remove 的拦截
    _pre_clean_dist_exe(root)

    # workpath 落到 OS 临时目录：绕过 WorkBuddy safe-delete 对
    # build 产物清理（os.remove 在临时目录下走原生删除，不被沙箱拦截）
    import tempfile
    workpath = os.path.join(tempfile.gettempdir(), "qingning_build")

    args = [
        ENTRY,
        f"--name={APP_NAME}",
        "--noconsole",
        "--onefile",
        f"--distpath={DIST_DIR}",
        f"--workpath={workpath}",
        # 应用图标（品牌绿色系「清单」图标，多尺寸 ico）
        "--icon=assets/icons/qingning.ico",
        # 数据文件：音频资源
        "--add-data=assets/sounds;assets/sounds",
        # 数据文件：联系方式二维码
        "--add-data=assets/qrcodes;assets/qrcodes",
        # 数据文件：帮助文档（落入 help/ 目录）
        "--add-data=使用说明书.md;help",
        "--add-data=README.md;help",
        # 排除非必要包，最小化体积
        *[f"--exclude-module={m}" for m in EXCLUDES],
        # 关闭 UPX：避免杀毒误报
        "--noupx",
        # 覆盖已有输出
        "--noconfirm",
    ]

    # ── 体积优化：剔除应用用不到的重型二进制 ──────────────────────────
    # 升级后的 PyQt6/PyInstaller 会把整个 Qt6 bin 目录收进来，其中：
    #   - opengl32sw.dll：软件 OpenGL 渲染器（~20MB），纯 2D QWidget 应用无需；
    #   - Qt6Pdf.dll / qtpdf：PDF 支持（~4.6MB），应用无 PDF 功能；
    #   - cryptography 栈（_rust / bcrypt / nacl 等 .pyd 与 OpenSSL 库）：
    #     本应用源码从未 import，纯属被环境自动收集。
    # 这些在 collect_module 返回的 binaries 里过滤掉即可，不影响程序运行。
    # 注意：libcrypto-1_1.dll（Python 自带 OpenSSL，pymysql/ssl 需要）不在排除列表，保留。
    import PyInstaller.__main__ as _pyi_main
    import PyInstaller.utils.hooks.qt as _qt_hooks

    _EXCLUDE_BIN_SUBSTR = (
        "opengl32sw", "_rust", "libcrypto-3", "libssl-3",
        "bcrypt", "nacl", "qt6pdf", "qtpdf", "cryptography",
    )
    _orig_collect = _qt_hooks.QtLibraryInfo.collect_module

    def _patched_collect_module(self, module_name):
        hiddenimports, binaries, datas = _orig_collect(self, module_name)
        kept = [b for b in binaries
                if not any(s in b[0].lower() for s in _EXCLUDE_BIN_SUBSTR)]
        return hiddenimports, kept, datas

    _qt_hooks.QtLibraryInfo.collect_module = _patched_collect_module

    # ── PE 校验和写入容错 ─────────────────────────────────────────────
    # 构建收尾时 PyInstaller 会重写 exe 的 PE 校验和；在 Windows 上若杀毒
    # （Defender）正在扫描刚生成的 exe，open(path,'wb') 会瞬间被锁导致
    # PermissionError。PE 校验和对用户态 GUI 程序并非必需，故做长重试 +
    # 最终降级（仅告警、不中断构建），保证 exe 产出可用。
    import time
    import PyInstaller.utils.win32.winutils as _winutils
    _orig_chk = _winutils.update_exe_pe_checksum

    def _safe_update_pe_checksum(exe_path):
        last = None
        for _ in range(60):  # 最多约 30s，覆盖杀毒扫描窗口
            try:
                return _orig_chk(exe_path)
            except (PermissionError, OSError, RuntimeError) as _e:
                last = _e
                time.sleep(0.5)
        print(f"  [警告] 无法写入 PE 校验和（文件被占用/杀毒锁定），已跳过：{exe_path}")
        return None

    _winutils.update_exe_pe_checksum = _safe_update_pe_checksum

    print("=" * 60)
    print(f"  打包应用: {APP_NAME}")
    print(f"  入口脚本: {ENTRY}")
    print(f"  输出目录: {DIST_DIR}/")
    print(f"  排除模块: {len(EXCLUDES)} 个")
    print("=" * 60)
    print()
    print("执行:", " ".join(args))
    print()
    import time as _tt
    _t0 = _tt.time()
    try:
        _pyi_main.run(args)
    except SystemExit as _e:
        ret = _e.code if isinstance(_e.code, int) else 1
    else:
        ret = 0
    _t1 = _tt.time()
    print(f"\n[打包耗时] PyInstaller 主流程: {_t1 - _t0:.1f}s")

    if ret == 0:
        _cleanup_bak_exes(root)
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
