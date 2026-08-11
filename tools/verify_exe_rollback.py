# -*- coding: utf-8 -*-
"""校验 dist 内 exe 是否为回退后的稳定版本（不含前端重构动画代码）。

用法: python tools/verify_exe_rollback.py
"""
import marshal
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "青柠待办.exe"

# 重构引入的标记（必须不存在）
MUST_ABSENT = ["_animate_page_in", "QGraphicsOpacityEffect", "_build_calendar_qss"]
# v1.4.0 应有的标记（必须存在）
MUST_PRESENT = ["_play_default_chime", "_calendar_qss", "ddyyll66666", "1461613752"]


def load_module_source_blobs():
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(EXE))
    pyz_name = None
    for name in reader.toc:
        if name.endswith("PYZ.pyz") or name == "PYZ-00.pyz":
            pyz_name = name
            break
    if pyz_name is None:
        raise SystemExit("未在 CArchive TOC 中找到 PYZ")

    pyz = reader.open_embedded_archive(pyz_name)
    blobs = {}
    for mod in pyz.toc:
        if not mod.startswith("src.ui_qt"):
            continue
        try:
            _typ, pos, length = pyz.toc[mod]
            pyz._file.seek(pyz._start + pos)
            raw = pyz._file.read(length)
            code = marshal.loads(zlib.decompress(raw))
        except Exception:
            try:
                code = pyz.extract(mod)
            except Exception:
                continue
        blobs[mod] = collect_strings(code)
    return blobs


def collect_strings(code, acc=None):
    if acc is None:
        acc = []
    try:
        acc.extend([c for c in code.co_names])
        acc.extend([c for c in code.co_consts if isinstance(c, str)])
        for c in code.co_consts:
            if hasattr(c, "co_names"):
                collect_strings(c, acc)
    except Exception:
        pass
    return acc


def main():
    if not EXE.exists():
        raise SystemExit(f"exe 不存在: {EXE}")
    print(f"[i] 校验: {EXE}  ({EXE.stat().st_size} bytes)")
    blobs = load_module_source_blobs()
    print(f"[i] 提取 src.ui_qt.* 模块 {len(blobs)} 个")

    all_strings = set()
    for names in blobs.values():
        all_strings.update(names)

    ok = True
    for token in MUST_ABSENT:
        hit = token in all_strings
        print(f"{'[FAIL]' if hit else '[ OK ]'} 不应存在: {token}  -> {'仍存在!' if hit else '已清除'}")
        ok &= not hit
    for token in MUST_PRESENT:
        hit = token in all_strings
        print(f"{'[ OK ]' if hit else '[FAIL]'} 应当存在: {token}  -> {'存在' if hit else '缺失!'}")
        ok &= hit

    print("\n==== 结论:", "PASS（exe 为回退后的稳定版本）" if ok else "FAIL（exe 与预期不符）", "====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
