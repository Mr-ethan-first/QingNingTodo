"""帮助文档回归测试（PyQt6 offscreen）。

需求：帮助文档为单文件本地文档，优先用户版《使用说明书.md》，
其次技术版 README.md，不再依赖远程链接。
覆盖 SettingsPage._resolve_help_path 能定位到项目根目录的帮助文档。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_help_resolves_to_single_local_doc():
    """帮助文档解析必须指向单个本地 Markdown（优先用户版使用说明书）。"""
    from src.ui_qt.pages.settings_page import SettingsPage

    # 直接构造实例（不调用 __init__，避免加载大量依赖）
    sp = SettingsPage.__new__(SettingsPage)
    path = sp._resolve_help_path()
    assert path is not None, "未能定位帮助文档"
    assert os.path.exists(path), "解析到的帮助文档路径不存在"
    assert os.path.basename(path) in ("使用说明书.md", "README.md")
    assert os.path.getsize(path) > 0, "帮助文档不应为空"
