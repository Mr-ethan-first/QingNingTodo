"""图标工厂（PyQt6 / SVG，零外部素材）。

所有图标由内联 SVG 程序化生成，颜色取主题令牌（默认青柠绿主色），
无需任何图片文件。应用图标为青柠叶标志，整体替换原番茄（🍅）视觉。
"""
from typing import Callable, Dict, Tuple

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from src.theme import get_current_theme


# 线性图标：stroke 取主色、fill 透明
_LINE = '<g fill="none" stroke="{{c}}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{0}</g>'

SVGS = {
    # 应用标志：青柠叶（填充主色）
    "leaf": (
        '<g fill="{c}" stroke="none">'
        '<path d="M5 19 C5 10 12 4 20 5 C20 13 14 20 5 19 Z"/></g>'
        '<g fill="none" stroke="{c}" stroke-width="1.6" stroke-linecap="round" opacity="0.55">'
        '<path d="M9 16 C12 13 15 10 17 7"/></g>'
    ),
    "checklist": _LINE.format(
        '<rect x="3" y="5" width="6" height="6" rx="1.5"/>'
        '<path d="M4.6 8 L6 9.4 L8.4 6.6"/>'
        '<rect x="3" y="14" width="6" height="6" rx="1.5"/>'
        '<path d="M4.6 17 L6 18.4 L8.4 15.6"/>'
        '<path d="M12 8 H21"/><path d="M12 17 H21"/>'
    ),
    "timer": _LINE.format(
        '<circle cx="12" cy="13" r="8"/><path d="M12 13 V9"/>'
        '<path d="M9 2 H15"/><path d="M12 2 V5"/>'
    ),
    "chart": _LINE.format(
        '<path d="M4 20 V11"/><path d="M10 20 V4"/><path d="M16 20 V14"/>'
        '<path d="M22 20 V8"/><path d="M3 20 H23"/>'
    ),
    "map": _LINE.format(
        '<path d="M12 21 C12 21 5 14 5 9 A7 7 0 0 1 19 9 C19 14 12 21 12 21 Z"/>'
        '<circle cx="12" cy="9" r="2.4"/>'
    ),
    "settings": _LINE.format(
        '<path d="M3 6 H21"/><circle cx="8" cy="6" r="2.4"/>'
        '<path d="M3 12 H21"/><circle cx="16" cy="12" r="2.4"/>'
        '<path d="M3 18 H21"/><circle cx="10" cy="18" r="2.4"/>'
    ),
    "plus": _LINE.format('<path d="M12 5 V19"/><path d="M5 12 H19"/>'),
    "play": _LINE.format('<path d="M8 6 L18 12 L8 18 Z"/>'),
    "pause": _LINE.format(
        '<rect x="7" y="5" width="3.2" height="14" rx="1.2"/>'
        '<rect x="13.8" y="5" width="3.2" height="14" rx="1.2"/>'
    ),
    "stop": _LINE.format('<rect x="6" y="6" width="12" height="12" rx="2.4"/>'),
    "check": _LINE.format('<path d="M5 12 L10 17 L19 7"/>'),
    "music": _LINE.format(
        '<path d="M9 17 V6 L17 4 V15"/>'
        '<circle cx="7" cy="17" r="2.2" fill="{{c}}" stroke="none"/>'
        '<circle cx="15" cy="15" r="2.2" fill="{{c}}" stroke="none"/>'
    ),
    "edit": _LINE.format(
        '<path d="M4 20 L4 16 L15 5 L19 9 L8 20 Z"/><path d="M14 6 L18 10"/>'
    ),
    "trash": _LINE.format(
        '<path d="M4 7 H20"/><path d="M9 7 V4 H15 V7"/>'
        '<path d="M6 7 L7 20 H17 L18 7"/>'
    ),
    "more": _LINE.format(
        '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/>'
        '<circle cx="12" cy="19" r="1.6"/>'
    ),
    "close": _LINE.format('<path d="M6 6 L18 18"/><path d="M18 6 L6 18"/>'),
    "minimize": _LINE.format('<path d="M5 12 H19"/>'),
    "maximize": _LINE.format(
        '<rect x="5" y="5" width="14" height="14" rx="2"/>'
    ),
    "calendar": _LINE.format(
        '<rect x="4" y="5" width="16" height="15" rx="2.4"/>'
        '<path d="M4 9.5 H20"/><path d="M8 2.5 V6"/><path d="M16 2.5 V6"/>'
    ),
    "user": _LINE.format(
        '<circle cx="12" cy="8" r="4"/><path d="M5 20 C5 15 19 15 19 20"/>'
    ),
    "target": _LINE.format(
        '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/>'
    ),
    "shield": _LINE.format(
        '<path d="M12 3 L20 6 V11 C20 16 16 19 12 21 C8 19 4 16 4 11 V6 Z"/>'
        '<path d="M9 12 L11 14 L15 9"/>'
    ),
    "database": _LINE.format(
        '<ellipse cx="12" cy="6" rx="7" ry="3"/>'
        '<path d="M5 6 V18 C5 20.2 19 20.2 19 18 V6"/>'
        '<path d="M5 12 C5 14.2 19 14.2 19 12"/>'
    ),
    "chevron": _LINE.format('<path d="M9 6 L15 12 L9 18"/>'),
    "refresh": _LINE.format(
        '<path d="M20 11 A8 8 0 0 0 13 4"/><path d="M20 4 V9 H15"/>'
        '<path d="M4 13 A8 8 0 0 0 11 20"/><path d="M4 20 V15 H9"/>'
    ),
    # --- 新增图标 ---
    "clock": _LINE.format(
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 7 V12 L15.5 15.5"/>'
    ),
    "bell": _LINE.format(
        '<path d="M18 8 A6 6 0 0 0 6 8 C6 15 3 15 3 15 H21 C21 15 18 15 18 8"/>'
        '<path d="M10.5 19 A1.5 1.5 0 0 0 13.5 19"/>'
    ),
    "image": _LINE.format(
        '<rect x="3" y="3" width="18" height="18" rx="2.4"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/>'
        '<path d="M21 15 L16 10 L5 21"/>'
    ),
    "sort": _LINE.format(
        '<path d="M3 6 H21"/><path d="M3 12 H15"/><path d="M3 18 H9"/>'
    ),
    "top": _LINE.format(
        '<path d="M12 20 V4"/><path d="M5 11 L12 4 L19 11"/>'
    ),
    "up": _LINE.format(
        '<path d="M12 18 V6"/><path d="M6 12 L12 6 L18 12"/>'
    ),
    "down": _LINE.format(
        '<path d="M12 6 V18"/><path d="M6 12 L12 18 L18 12"/>'
    ),
    "move": _LINE.format(
        '<path d="M5 9 L3 12 L5 15"/><path d="M19 9 L21 12 L19 15"/>'
        '<path d="M9 5 L12 3 L15 5"/><path d="M9 19 L12 21 L15 19"/>'
        '<path d="M3 12 H21"/><path d="M12 3 V21"/>'
    ),
    "history": _LINE.format(
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 8 V12 L14.5 14.5"/>'
        '<path d="M3 12 C3 7 7 3 12 3"/>'
        '<path d="M12 3 L9 3 L12 6"/>'
    ),
    "toggle_on": _LINE.format(
        '<rect x="2" y="6" width="20" height="12" rx="6"/>'
        '<circle cx="16" cy="12" r="4"/>'
    ),
    "toggle_off": _LINE.format(
        '<rect x="2" y="6" width="20" height="12" rx="6"/>'
        '<circle cx="8" cy="12" r="4"/>'
    ),
    "link": _LINE.format(
        '<path d="M10 13 A5 5 0 0 0 15 18 L18 18 A5 5 0 0 0 18 8 L15 8"/>'
        '<path d="M14 11 A5 5 0 0 0 9 6 L6 6 A5 5 0 0 0 6 16 L9 16"/>'
    ),
    "loop": _LINE.format(
        '<path d="M17 2 L21 6 L17 10"/>'
        '<path d="M3 12 A9 9 0 0 1 21 6"/>'
        '<path d="M7 22 L3 18 L7 14"/>'
        '<path d="M21 12 A9 9 0 0 1 3 18"/>'
    ),
    "stopwatch": _LINE.format(
        '<circle cx="12" cy="13" r="7"/>'
        '<path d="M12 13 V9"/>'
        '<path d="M10 2 H14"/>'
        '<path d="M12 2 V4"/>'
        '<path d="M4 2 H8"/>'
    ),
    "habit": _LINE.format(
        '<path d="M12 2 C6.5 2 2 6.5 2 12 C2 17.5 6.5 22 12 22"/>'
        '<path d="M12 6 V12 L16 14"/>'
        '<path d="M16 2 L22 2 L22 8"/>'
        '<path d="M16 8 L22 2"/>'
    ),
    "goal_flag": _LINE.format(
        '<path d="M4 22 V4"/>'
        '<path d="M4 4 L18 4 L12 10 L18 16 L4 16"/>'
    ),
    "info": _LINE.format(
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 16 V12"/>'
        '<path d="M12 8 H12.01"/>'
    ),
    "left": _LINE.format('<path d="M15 18 L9 12 L15 6"/>'),
    "right": _LINE.format('<path d="M9 6 L15 12 L9 18"/>'),
    "chevron-down": _LINE.format('<path d="M6 9 L12 15 L18 9"/>'),
    "chevron-up": _LINE.format('<path d="M6 15 L12 9 L18 15"/>'),
    "sun": _LINE.format(
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2 V4"/>'
        '<path d="M12 20 V22"/>'
        '<path d="M4.93 4.93 L6.34 6.34"/>'
        '<path d="M17.66 17.66 L19.07 19.07"/>'
        '<path d="M2 12 H4"/>'
        '<path d="M20 12 H22"/>'
        '<path d="M4.93 19.07 L6.34 17.66"/>'
        '<path d="M17.66 6.34 L19.07 4.93"/>'
    ),
    "moon": _LINE.format(
        '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79 Z"/>'
    ),
    "gear": _LINE.format(
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83'
        'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0'
        'v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06'
        'a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15'
        'a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9'
        'a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06'
        'A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0'
        'v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06'
        'a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9'
        'a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>'
    ),
}


def icon(name: str, color: str = None, size: int = 20) -> QIcon:
    """取指定名称的青柠主题图标。color 缺省取当前主题主色。

    P0 修复: 加 LRU 缓存避免 hover/pressed 状态切换时反复重建 QSvgRenderer
    (QPushButton 在不同状态可能调用 icon() 多次, 此前每次都新建渲染器 → 性能瓶颈)
    """
    if name not in SVGS:
        name = "leaf"
    c = color or get_current_theme().primary
    cache_key = (name, c, size)
    cached = _icon_cache.get(cache_key)
    if cached is not None:
        return cached
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}">{SVGS[name].format(c=c)}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    result = QIcon(pm)
    # 防止缓存无限增长, 主题切换时调用 clear_icon_cache()
    if len(_icon_cache) >= _ICON_CACHE_MAX:
        _icon_cache.clear()
    _icon_cache[cache_key] = result
    return result


_icon_cache: Dict[Tuple[str, str, int], QIcon] = {}
_ICON_CACHE_MAX = 512


def clear_icon_cache() -> None:
    """主题切换后清空图标缓存, 让所有图标按新主题色重新渲染。"""
    _icon_cache.clear()


def app_icon(size: int = 128) -> QIcon:
    """应用图标（青柠叶）。"""
    return icon("leaf", get_current_theme().primary, size)


def tinted(color: str, size: int = 20) -> "Callable":
    """返回一个固定颜色的图标工厂，便于静态资源缓存。"""

    def _f(name):
        return icon(name, color, size)

    return _f
