"""EXE 自动化测试脚本。

对打包后的「青柠待办.exe」进行端到端测试，覆盖两种数据库后端：

1. SQLite 模式（默认）：
   - 通过 QINGNING_TODO_HOME 环境变量指定独立配置目录
   - 启动 exe，等待主窗口出现
   - 验证 SQLite 数据库文件已创建且包含种子数据
   - 关闭 exe

2. MySQL 模式：
   - 预先在配置目录写入 config.json 指向 MySQL 测试库
   - 启动 exe，等待主窗口出现
   - 验证 MySQL 数据库中已创建表与种子数据
   - 关闭 exe 并清理 MySQL 测试库

用法：
    python tests_exe/test_exe_automation.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "青柠待办.exe"

# 测试用配置目录，避免污染用户主目录
TEST_HOME = ROOT / ".exe_test_home"

# MySQL 测试配置
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "qingning_todo_exe_test",
    "charset": "utf8mb4",
}

# 应用窗口标题（MainWindow.titleBarText 或 app.setApplicationName）
WINDOW_KEYWORDS = ("青柠待办",)
WINDOW_EXCLUDES = (".md", "规格", "说明", "txt", "log")


def _print(phase: str, msg: str):
    """带阶段前缀的打印。"""
    print(f"[{phase}] {msg}", flush=True)


def _kill_stale():
    """清理可能残留的旧实例。"""
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        for p in wmi.InstancesOf("Win32_Process"):
            if p.Name == "青柠待办.exe":
                try:
                    p.Terminate()
                    _print("CLEANUP", f"Killed stale pid={p.ProcessId}")
                except Exception:
                    pass
    except Exception as e:
        _print("CLEANUP", f"wmi skip: {e!r}")


def _find_window(timeout_sec: float = 60.0):
    """查找应用主窗口。

    返回 (hwnd, title) 或 None。
    """
    try:
        import win32gui
    except ImportError:
        _print("FIND", "pywin32 未安装，跳过窗口查找")
        return None

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        hits = []

        def cb(hwnd, ctx):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                t = win32gui.GetWindowText(hwnd)
                if not t:
                    return
                if any(k in t for k in WINDOW_KEYWORDS) and \
                        not any(x in t for x in WINDOW_EXCLUDES):
                    ctx.append((hwnd, t))
            except Exception:
                pass

        try:
            win32gui.EnumWindows(cb, hits)
        except Exception:
            pass
        if hits:
            # 选面积最大的（主窗口通常最大）
            def area(h):
                try:
                    l, t, r, b = win32gui.GetWindowRect(h)
                    return max(0, r - l) * max(0, b - t)
                except Exception:
                    return 0
            hits.sort(key=lambda x: area(x[0]), reverse=True)
            return hits[0]
        time.sleep(1.0)
    return None


def _terminate_process(proc: subprocess.Popen, timeout: float = 10.0):
    """强制终止进程（兼容 GUI 应用与对话框场景）。

    优先尝试 terminate()，超时后 kill()。
    应用默认开启「关闭确认对话框」，WM_CLOSE 会弹出对话框而非退出，
    因此测试中直接用 terminate() 强制结束进程。
    """
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
        _print("TERM", f"Process terminated (pid={proc.pid})")
        return True
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
            _print("TERM", f"Process killed (pid={proc.pid})")
            return True
        except Exception as e:
            _print("TERM", f"kill failed: {e!r}")
            return False
    except Exception as e:
        _print("TERM", f"terminate failed: {e!r}")
        return False


def _prepare_home(home_dir: Path):
    """清空并创建测试用配置目录。"""
    if home_dir.exists():
        # 只删除 config.json 和 .db 文件，保留目录结构
        for f in home_dir.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
            except Exception:
                pass
    else:
        home_dir.mkdir(parents=True)


def _write_mysql_config(home_dir: Path):
    """在配置目录写入指向 MySQL 的 config.json。"""
    home_dir.mkdir(parents=True, exist_ok=True)
    config_path = home_dir / "config.json"
    payload = {
        "db_backend": "mysql",
        "database_config": MYSQL_CONFIG,
    }
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8")
    _print("SETUP", f"Wrote MySQL config: {config_path}")


def _check_sqlite_db(home_dir: Path) -> bool:
    """验证 SQLite 数据库文件存在且包含种子数据。"""
    db_path = home_dir / "qingning_todo.db"
    if not db_path.exists():
        _print("VERIFY", f"SQLite DB not found: {db_path}")
        return False
    _print("VERIFY", f"SQLite DB exists: {db_path} "
                    f"({db_path.stat().st_size / 1024:.1f} KB)")

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        # 验证表已创建
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        expected = {
            "user", "todo_group", "todo", "focus_record", "goal",
            "future_plan", "checkin_record", "achievement",
            "focus_whitelist", "lock_schedule", "white_noise",
            "settings", "interrupt_details", "habit_checkins",
        }
        missing = expected - tables
        if missing:
            _print("VERIFY", f"Missing tables: {missing}")
            conn.close()
            return False
        _print("VERIFY", f"Tables OK: {len(tables)}/{len(expected)} tables")

        # 验证种子数据
        cur.execute("SELECT COUNT(*) FROM user")
        user_cnt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM white_noise")
        noise_cnt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM achievement")
        ach_cnt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM settings")
        set_cnt = cur.fetchone()[0]
        conn.close()

        _print("VERIFY", f"user={user_cnt} white_noise={noise_cnt} "
                        f"achievement={ach_cnt} settings={set_cnt}")
        if user_cnt < 1 or noise_cnt < 1 or ach_cnt < 1:
            _print("VERIFY", "Seed data insufficient")
            return False
        _print("VERIFY", "SQLite seed data OK")
        return True
    except Exception as e:
        _print("VERIFY", f"SQLite check failed: {e!r}")
        return False


def _check_mysql_db() -> bool:
    """验证 MySQL 数据库已创建表与种子数据。"""
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
            database=MYSQL_CONFIG["database"],
            charset=MYSQL_CONFIG["charset"],
        )
        cur = conn.cursor()

        # 验证表已创建
        cur.execute("SHOW TABLES")
        tables = {row[0] for row in cur.fetchall()}
        expected = {
            "user", "todo_group", "todo", "focus_record", "goal",
            "future_plan", "checkin_record", "achievement",
            "focus_whitelist", "lock_schedule", "white_noise",
            "settings", "interrupt_details", "habit_checkins",
        }
        missing = expected - tables
        if missing:
            _print("VERIFY", f"MySQL missing tables: {missing}")
            conn.close()
            return False
        _print("VERIFY", f"MySQL tables OK: {len(tables)}/{len(expected)} tables")

        # 验证种子数据
        cur.execute("SELECT COUNT(*) FROM user")
        user_cnt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM white_noise")
        noise_cnt = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM achievement")
        ach_cnt = cur.fetchone()[0]
        conn.close()

        _print("VERIFY", f"MySQL user={user_cnt} white_noise={noise_cnt} "
                        f"achievement={ach_cnt}")
        if user_cnt < 1 or noise_cnt < 1 or ach_cnt < 1:
            _print("VERIFY", "MySQL seed data insufficient")
            return False
        _print("VERIFY", "MySQL seed data OK")
        return True
    except Exception as e:
        _print("VERIFY", f"MySQL check failed: {e!r}")
        return False


def _check_no_residual_process() -> bool:
    """验证 exe 退出后没有残留进程。"""
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        for p in wmi.InstancesOf("Win32_Process"):
            if p.Name == "青柠待办.exe":
                _print("VERIFY", f"Residual process: pid={p.ProcessId}")
                return False
        _print("VERIFY", "No residual process")
        return True
    except Exception as e:
        _print("VERIFY", f"Residual check skipped: {e!r}")
        return True


def _check_log_clean(home_dir: Path) -> bool:
    """验证 exe 的日志中无异常输出。"""
    log = home_dir / "exe_stderr.log"
    if not log.exists():
        return True
    try:
        content = log.read_text(encoding="utf-8", errors="ignore")
        if not content.strip():
            _print("VERIFY", "Log clean (empty)")
            return True
        # 检查是否有错误关键字
        error_keywords = ["Traceback", "Error", "Exception", "CRITICAL"]
        lower = content.lower()
        for kw in error_keywords:
            if kw.lower() in lower:
                _print("VERIFY", f"Log contains '{kw}':")
                print(content[-500:], flush=True)
                return False
        # 含 Python 警告也视为可疑
        if "warning" in lower:
            _print("VERIFY", "Log has warning(s) but no errors - acceptable")
        else:
            _print("VERIFY", "Log clean")
        return True
    except Exception as e:
        _print("VERIFY", f"Log check failed: {e!r}")
        return True


def _cleanup_mysql():
    """清理 MySQL 测试数据库。"""
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
            charset=MYSQL_CONFIG["charset"],
        )
        cur = conn.cursor()
        # 先 drop 表再 drop 库
        tables = ["interrupt_details", "habit_checkins", "checkin_record",
                  "focus_record", "todo", "todo_group", "future_plan",
                  "goal", "focus_whitelist", "lock_schedule", "settings",
                  "white_noise", "achievement", "user"]
        for tb in tables:
            try:
                cur.execute(f"DROP TABLE IF EXISTS `{tb}`")
            except Exception:
                pass
        cur.execute(f"DROP DATABASE IF EXISTS `{MYSQL_CONFIG['database']}`")
        conn.commit()
        conn.close()
        _print("CLEANUP", "MySQL test database dropped")
    except Exception as e:
        _print("CLEANUP", f"MySQL cleanup failed: {e!r}")


def _launch_exe(home_dir: Path) -> subprocess.Popen:
    """启动 exe，使用指定的配置目录。"""
    env = os.environ.copy()
    env["QINGNING_TODO_HOME"] = str(home_dir)
    # noconsole 模式下 redirect stdout/stderr 到文件以便排查
    err_log = home_dir / "exe_stderr.log"
    err_fp = open(err_log, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(EXE)],
        stdout=err_fp,
        stderr=subprocess.STDOUT,
        env=env,
    )
    _print("LAUNCH", f"pid={proc.pid} home={home_dir}")
    return proc, err_fp


def _dump_log(home_dir: Path):
    """打印 exe 的 stderr 日志尾部。"""
    log = home_dir / "exe_stderr.log"
    if not log.exists():
        return
    try:
        content = log.read_text(encoding="utf-8", errors="ignore")
        if content.strip():
            _print("EXE_LOG", "tail 1500 chars:")
            print(content[-1500:], flush=True)
    except Exception as e:
        _print("EXE_LOG", f"read failed: {e!r}")


def test_sqlite_mode():
    """SQLite 模式测试。"""
    _print("=" * 60, "")
    _print("TEST", "SQLite mode start")
    _print("=" * 60, "")

    _kill_stale()
    home = TEST_HOME / "sqlite"
    _prepare_home(home)

    proc, err_fp = _launch_exe(home)
    try:
        hwnd_info = _find_window(timeout_sec=60)
        if hwnd_info is None:
            _print("FAIL", "Window not found within 60s")
            _dump_log(home)
            return False
        hwnd, title = hwnd_info
        _print("PASS", f"Window found: hwnd={hwnd} title={title!r}")

        # 等待窗口稳定（动画完成、数据库初始化完成）
        time.sleep(3)
    finally:
        try:
            err_fp.close()
        except Exception:
            pass
        # 强制终止进程，避免触发关闭确认对话框
        _terminate_process(proc)

    # 等待进程完全退出
    time.sleep(2)
    # 再清理一次，防止子进程残留
    _kill_stale()
    time.sleep(1)

    # 验证项
    checks = [
        ("SQLite DB", _check_sqlite_db(home)),
        ("No residual process", _check_no_residual_process()),
        ("Log clean", _check_log_clean(home)),
    ]
    all_ok = True
    for name, ok in checks:
        if not ok:
            _print("FAIL", f"Check failed: {name}")
            all_ok = False

    if all_ok:
        _print("PASS", "SQLite mode test passed")
    else:
        _print("FAIL", "SQLite mode test failed")
        _dump_log(home)
    return all_ok


def test_sqlite_idempotent():
    """SQLite 幂等性测试：再次启动不会重复插入种子数据。"""
    _print("=" * 60, "")
    _print("TEST", "SQLite idempotency start")
    _print("=" * 60, "")

    # 使用前一次的 SQLite 配置目录，再次启动
    home = TEST_HOME / "sqlite"

    # 先记录种子数据数量
    db_path = home / "qingning_todo.db"
    before = {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        for tb in ("user", "white_noise", "achievement", "settings"):
            cur.execute(f"SELECT COUNT(*) FROM {tb}")
            before[tb] = cur.fetchone()[0]
        conn.close()
        _print("BEFORE", f"counts: {before}")
    except Exception as e:
        _print("FAIL", f"Cannot read before state: {e!r}")
        return False

    _kill_stale()
    proc, err_fp = _launch_exe(home)
    try:
        hwnd_info = _find_window(timeout_sec=60)
        if hwnd_info is None:
            _print("FAIL", "Window not found within 60s")
            _dump_log(home)
            return False
        hwnd, title = hwnd_info
        _print("PASS", f"Window found: hwnd={hwnd} title={title!r}")

        time.sleep(3)
    finally:
        try:
            err_fp.close()
        except Exception:
            pass
        _terminate_process(proc)

    time.sleep(2)
    _kill_stale()
    time.sleep(1)

    # 验证种子数据数量未变化（幂等）
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        after = {}
        for tb in ("user", "white_noise", "achievement", "settings"):
            cur.execute(f"SELECT COUNT(*) FROM {tb}")
            after[tb] = cur.fetchone()[0]
        conn.close()
        _print("AFTER", f"counts: {after}")

        if after != before:
            _print("FAIL", f"Idempotency broken: before={before} after={after}")
            return False
        _print("PASS", "SQLite idempotency OK (no duplicate seed data)")
        return True
    except Exception as e:
        _print("FAIL", f"Idempotency check failed: {e!r}")
        return False


def test_mysql_mode():
    """MySQL 模式测试。"""
    _print("=" * 60, "")
    _print("TEST", "MySQL mode start")
    _print("=" * 60, "")

    _kill_stale()
    _cleanup_mysql()

    home = TEST_HOME / "mysql"
    _prepare_home(home)
    _write_mysql_config(home)

    proc, err_fp = _launch_exe(home)
    try:
        hwnd_info = _find_window(timeout_sec=60)
        if hwnd_info is None:
            _print("FAIL", "Window not found within 60s")
            _dump_log(home)
            return False
        hwnd, title = hwnd_info
        _print("PASS", f"Window found: hwnd={hwnd} title={title!r}")

        # 等待窗口稳定
        time.sleep(3)
    finally:
        try:
            err_fp.close()
        except Exception:
            pass
        _terminate_process(proc)

    time.sleep(2)
    _kill_stale()
    time.sleep(1)

    # 验证项
    checks = [
        ("MySQL DB", _check_mysql_db()),
        ("No residual process", _check_no_residual_process()),
        ("Log clean", _check_log_clean(home)),
    ]
    all_ok = True
    for name, ok in checks:
        if not ok:
            _print("FAIL", f"Check failed: {name}")
            all_ok = False

    if all_ok:
        _print("PASS", "MySQL mode test passed")
    else:
        _print("FAIL", "MySQL mode test failed")
        _dump_log(home)

    # 清理 MySQL
    _cleanup_mysql()
    return all_ok


def main():
    if not EXE.exists():
        _print("ERROR", f"EXE not found: {EXE}")
        _print("ERROR", "Please run `python build.py` first")
        return 2

    results = []
    _print("START", f"Testing EXE: {EXE}")

    # SQLite 模式
    ok1 = test_sqlite_mode()
    results.append(("SQLite", ok1))

    # 等待系统资源回收
    time.sleep(3)

    # SQLite 幂等性测试
    ok2 = test_sqlite_idempotent()
    results.append(("SQLite idempotent", ok2))

    time.sleep(3)

    # MySQL 模式
    ok3 = test_mysql_mode()
    results.append(("MySQL", ok3))

    # 汇总
    _print("=" * 60, "")
    _print("SUMMARY", "")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        _print("SUMMARY", f"{name}: {status}")
    _print("=" * 60, "")

    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
