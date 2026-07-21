"""主题系统（PyQt6 / QSS）。

1:1 还原自前端风格大全两个 HTML 原型：

- light（Organic Biophilic）—— 24-organic-biophilic.html
  - 有机自然风，浅米绿底 + 苔藓绿主色；
  - 16 / 10 / 24px 圆角；
  - Fraunces 标题 + Nunito Sans 正文；
  - 右上角绿色 radial-gradient 光晕；
  - 卡片采用 24px 8px 不对称圆角 + 浅色阴影。

- dark（Aurora UI）—— 10-aurora-ui.html
  - 极光暗夜风，深蓝夜空底 + 靛紫主色 + 翡翠绿 / 霓粉点缀；
  - 18 / 12 / 28px 圆角；
  - Outfit 标题 + Inter 正文；
  - conic-gradient 极光旋转（25s 周期）；
  - 玻璃卡片 backdrop-blur + 半透明 border。

所有色值、圆角、间距、阴影、字体、动画均严格对应 HTML :root 变量。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Dict

from PyQt6.QtCore import QObject


# ═════════════════════════════════════════════════════════════════════════════
# 颜色工具
# ═════════════════════════════════════════════════════════════════════════════

def _hex_to_rgb(hex_color: str):
    """'#RRGGBB' -> (r, g, b)。非法返回 None。"""
    c = hex_color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return None
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return None


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _lighten(rgb, ratio: float):
    """按比例向白色混合（ratio>0 变亮，<0 变暗）。"""
    r, g, b = rgb
    return (_lerp(r, 255, ratio), _lerp(g, 255, ratio), _lerp(b, 255, ratio))


def _relative_luminance(rgb) -> float:
    """WCAG 相对亮度（sRGB）。"""
    def ch(x):
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _on_color(hex_color: str) -> str:
    """根据主色返回对比度更高的前景文字色（深/浅）。"""
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return "#FFFFFF"
    lum_bg = _relative_luminance(rgb)
    dark_text, light_text = "#1A1D23", "#FFFFFF"
    lum_dark = _relative_luminance(_hex_to_rgb(dark_text))
    lum_light = _relative_luminance(_hex_to_rgb(light_text))
    contrast_dark = (max(lum_bg, lum_dark) + 0.05) / (min(lum_bg, lum_dark) + 0.05)
    contrast_light = (max(lum_bg, lum_light) + 0.05) / (min(lum_bg, lum_light) + 0.05)
    return dark_text if contrast_dark >= contrast_light else light_text


def hex_rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' + alpha(0~1) -> 'rgba(r,g,b,a)'."""
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return "rgba(0,0,0,0.0)"
    r, g, b = rgb
    a = max(0.0, min(1.0, alpha))
    return f"rgba({r},{g},{b},{a:.3f})"


# ═════════════════════════════════════════════════════════════════════════════
# Theme 数据类
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Theme:
    """一套完整的视觉令牌（颜色均为十六进制字符串）。"""

    name: str                       # 主题唯一键
    label: str                      # 展示名
    # ── 基础色（直接对应 :root 变量） ──
    bg: str                         # body 底色（--c-bg）
    bg_soft: str                    # 装饰背景（--c-bgSoft）
    surface: str                    # 卡片/面板（--c-surface）
    surface_variant: str            # 次级面板（--c-surface2）
    # ── 字体（直接对应 :root 变量） ──
    font_d: str                     # 标题字体（--font-d）
    font_b: str                     # 正文字体（--font-b）
    # ── 侧栏 ──
    sidebar: str                    # 侧栏底色
    sidebar_text: str               # 侧栏文字
    sidebar_muted: str              # 侧栏次要文字
    # ── 主色 ──
    primary: str
    primary_hover: str
    primary_pressed: str
    on_primary: str
    primary_soft: str
    # ── 副色 ──
    secondary: str                  # --c-secondary（翡翠绿，light=#7BAE5C，dark=#34D399）
    accent: str                     # --c-accent（大地橙/霓粉）

    @property
    def accent2(self) -> str:
        """兼容旧代码: 即 secondary 字段（翡翠绿副色）."""
        return self.secondary
    # ── 文字 ──
    text: str
    text_muted: str
    text_subtle: str
    # ── 描边/分割线 ──
    border: str
    divider: str
    # ── 开关轨道（未开启态底色） ──
    switch_track: str
    # ── 状态色 ──
    success: str
    success_hover: str
    warning: str
    danger: str
    danger_hover: str
    # ── 圆角（直接对应 --r / --r-sm / --r-lg） ──
    radius_sm: int
    radius_md: int
    radius_lg: int
    # ── 阴影（直接对应 --sh） ──
    shadow: str

    @property
    def soft(self) -> str:
        return self.primary_soft

    @property
    def primary_ghost(self) -> str:
        """幽灵按钮/描边场景的主色。原型中均使用 primary 直接值。"""
        return self.primary

    # ── 状态色程序化派生 ──
    @property
    def on_success(self) -> str:
        return _on_color(self.success)

    @property
    def on_warning(self) -> str:
        return _on_color(self.warning)

    @property
    def on_danger(self) -> str:
        return _on_color(self.danger)

    def _state_soft(self, hex_color: str) -> str:
        rgb = _hex_to_rgb(hex_color)
        if not rgb:
            return hex_color
        ratio = -0.82 if self.name == "dark" else 0.85
        return _rgb_to_hex(*_lighten(rgb, ratio))

    def _state_pressed(self, hex_color: str) -> str:
        rgb = _hex_to_rgb(hex_color)
        if not rgb:
            return hex_color
        return _rgb_to_hex(*_lighten(rgb, -0.10))

    @property
    def success_soft(self) -> str:
        return self._state_soft(self.success)

    @property
    def warning_soft(self) -> str:
        return self._state_soft(self.warning)

    @property
    def danger_soft(self) -> str:
        return self._state_soft(self.danger)

    @property
    def success_pressed(self) -> str:
        return self._state_pressed(self.success)

    @property
    def warning_pressed(self) -> str:
        return self._state_pressed(self.warning)

    @property
    def danger_pressed(self) -> str:
        return self._state_pressed(self.danger)


# ═════════════════════════════════════════════════════════════════════════════
# 主题实例（严格对应 :root 变量）
# ═════════════════════════════════════════════════════════════════════════════

# ───── 浅色（Organic Biophilic）── 1:1 还原 :root ─────
LIGHT = Theme(
    name="light",
    label="Organic",
    # :root --c-bg / --c-bgSoft / --c-surface / --c-surface2
    bg="#F2F5EE",
    bg_soft="#E8F0E0",
    surface="#FFFFFF",
    surface_variant="#F5F8F0",
    # 字体
    font_d='"Fraunces", "Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Noto Sans SC", serif',
    font_b='"Nunito Sans", "Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif',
    # 侧栏
    sidebar="#F2F5EE",
    sidebar_text="#2A3A1F",
    sidebar_muted="#6B7A5A",
    # :root --c-primary / --c-secondary / --c-accent
    primary="#5B8A3A",
    primary_hover="#7BAE5C",
    primary_pressed="#4A7330",
    on_primary="#FFFFFF",
    primary_soft="#E0EFD0",
    secondary="#7BAE5C",
    accent="#C97B3F",
    # :root --c-text / --c-textMuted
    text="#2A3A1F",
    text_muted="#6B7A5A",
    text_subtle="#7A8A65",
    border="#C8D6BD",
    divider="#E8F0E0",
    switch_track="#C8D6BD",
    # 状态色
    success="#4A7330",
    success_hover="#5B8A3A",
    warning="#C97B3F",
    danger="#EF4444",
    danger_hover="#DC2626",
    # :root --r / --r-sm / --r-lg
    radius_sm=10,
    radius_md=16,
    radius_lg=24,
    # :root --sh: 0 6px 20px rgba(120,180,100,0.12)
    shadow="0 6px 20px rgba(120,180,100,0.12)",
)


# ───── 深色（Aurora UI）── 1:1 还原 :root ─────
DARK = Theme(
    name="dark",
    label="Aurora",
    # :root --c-bg / --c-bgSoft / --c-surface / --c-surface2
    bg="#0B1026",
    bg_soft="#141B3A",
    surface="#161E40",
    surface_variant="#1C2550",
    # 字体
    font_d='"Outfit", "Inter", "Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif',
    font_b='"Inter", "Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif',
    # 侧栏
    sidebar="#0B1026",
    sidebar_text="#E0E7FF",
    sidebar_muted="#8B95C7",
    # :root --c-primary / --c-secondary / --c-accent
    primary="#818CF8",
    primary_hover="#A5B4FC",
    primary_pressed="#6366F1",
    on_primary="#FFFFFF",
    primary_soft="#1E2A5C",
    secondary="#34D399",
    accent="#F472B6",
    text="#E0E7FF",
    text_muted="#8B95C7",
    text_subtle="#8B95C7",
    border="#2A3460",
    divider="#1C2550",
    switch_track="#445188",
    # 状态色
    success="#34D399",
    success_hover="#6EE7B7",
    warning="#FBBF24",
    danger="#F472B6",
    danger_hover="#EC4899",
    # :root --r / --r-sm / --r-lg
    radius_sm=12,
    radius_md=18,
    radius_lg=28,
    # :root --sh: 0 10px 30px rgba(0,0,0,0.4)
    shadow="0 10px 30px rgba(0,0,0,0.4)",
)


THEMES: Dict[str, Theme] = {LIGHT.name: LIGHT, DARK.name: DARK}
DEFAULT_THEME = LIGHT.name


def get_theme(name: str) -> Theme:
    return THEMES.get(name, LIGHT)


def derive_theme_with_primary(base: Theme, hex_color: str) -> Theme:
    """以 base 主题为基础，用自定义主色派生一套主题。"""
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return base
    primary = hex_color
    hr, hg, hb = _lighten(rgb, 0.12)
    pr, pg, pb = _lighten(rgb, -0.10)
    if base.name == "dark":
        sr, sg, sb = _lighten(rgb, -0.82)
    else:
        sr, sg, sb = _lighten(rgb, 0.82)
    primary_soft = _rgb_to_hex(sr, sg, sb)
    on_primary = _on_color(primary)
    return replace(
        base,
        primary=primary,
        primary_hover=_rgb_to_hex(hr, hg, hb),
        primary_pressed=_rgb_to_hex(pr, pg, pb),
        on_primary=on_primary,
        primary_soft=primary_soft,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 当前主题单例
# ═════════════════════════════════════════════════════════════════════════════

_CURRENT: Theme = LIGHT


def set_current_theme(theme: Theme) -> None:
    global _CURRENT
    _CURRENT = theme


def get_current_theme() -> Theme:
    return _CURRENT


def apply_theme(app, theme: Theme) -> None:
    """将主题应用到 QApplication：注入 QSS 并记录当前主题令牌。"""
    set_current_theme(theme)
    app.setStyleSheet(build_qss(theme))


# ═════════════════════════════════════════════════════════════════════════════
# 日历 popup 注入（QDateEdit.calendarPopup 独立顶层窗口）
# ═════════════════════════════════════════════════════════════════════════════

def setup_calendar_popup(date_edit) -> None:
    """配置 QDateEdit 日历弹出面板的 QSS（独立顶层窗口，无法继承父 QSS）。"""
    from PyQt6.QtCore import QEvent
    try:
        from PyQt6.QtWidgets import QCalendarWidget
        cal = date_edit.calendarWidget()
        if cal is not None:
            _apply_calendar_qss(cal)
        date_edit._cal_popup_filter = _CalendarPopupFilter(date_edit)
        date_edit.installEventFilter(date_edit._cal_popup_filter)
    except Exception:
        pass


def _apply_calendar_qss(cal) -> None:
    try:
        from PyQt6.QtWidgets import QCalendarWidget
        cal.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setGridVisible(False)
        cal.setStyleSheet(_build_calendar_qss())
    except Exception:
        pass


class _CalendarPopupFilter(QObject):
    """拦截 QDateEdit 首次 Show 事件，注入 QSS 到 calendarWidget。"""

    def __init__(self, date_edit):
        super().__init__(date_edit)
        self._de = date_edit
        self._injected = False

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if not self._injected and event.type() == QEvent.Type.Show:
            cal = self._de.calendarWidget()
            if cal is not None:
                _apply_calendar_qss(cal)
                self._injected = True
        return False


def _build_calendar_qss() -> str:
    """1:1 还原 Organic Biophilic / Aurora UI 的日历样式。"""
    t = get_current_theme()
    is_dark = t.name == "dark"

    # 选中态、悬浮态颜色
    if is_dark:
        sel_bg = hex_rgba(t.primary, 0.30)
        sel_fg = t.text
        nav_bg = hex_rgba(t.surface, 0.40)
        weekend_color = t.danger
        prev_next_color = hex_rgba(t.text_subtle, 0.5)
        focus_outline = hex_rgba(t.primary, 0.40)
    else:
        sel_bg = t.primary
        sel_fg = t.on_primary
        nav_bg = t.primary_soft
        weekend_color = t.danger
        prev_next_color = t.text_subtle
        focus_outline = hex_rgba(t.primary, 0.35)

    return f"""
    QCalendarWidget {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        font-family: {t.font_b};
        font-size: 13px;
        min-width: 320px;
    }}
    QCalendarWidget QToolButton {{
        background: transparent;
        color: {t.text};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 6px 12px;
        font-size: 14px;
        font-weight: 600;
    }}
    QCalendarWidget QToolButton:hover {{
        background: {nav_bg};
        color: {t.primary};
    }}
    QCalendarWidget QToolButton:pressed {{
        background: {t.primary};
        color: {t.on_primary};
    }}
    QCalendarWidget QToolButton#qt_calendar_prevmonth,
    QCalendarWidget QToolButton#qt_calendar_nextmonth {{
        min-width: 36px; max-width: 36px;
        min-height: 36px; max-height: 36px;
        border-radius: 18px;
        font-size: 18px;
    }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background: {t.surface_variant};
        border-bottom: 1px solid {t.border};
        border-top-left-radius: {t.radius_md}px;
        border-top-right-radius: {t.radius_md}px;
        min-height: 44px;
    }}
    QCalendarWidget QWidget#qt_calendar_monthbutton,
    QCalendarWidget QWidget#qt_calendar_yearbutton {{
        background: transparent;
        color: {t.text};
        font-family: {t.font_d};
        font-size: 16px;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: {t.radius_sm}px;
        min-width: 70px;
    }}
    QCalendarWidget QWidget#qt_calendar_monthbutton:hover,
    QCalendarWidget QWidget#qt_calendar_yearbutton:hover {{
        color: {t.primary};
        background: {hex_rgba(t.primary, 0.10)};
    }}
    QCalendarWidget QWidget#qt_calendar_monthbutton::menu-indicator {{
        image: none;
        subcontrol-position: right center;
        width: 0;
        height: 0;
    }}
    QCalendarWidget QTableView {{
        background: transparent;
        alternate-background-color: transparent;
        border: none;
        gridline-color: transparent;
        outline: 0;
        selection-background-color: {sel_bg};
        selection-color: {sel_fg};
    }}
    QCalendarWidget QTableView::item {{
        background: transparent;
        color: {t.text};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 0;
        margin: 2px;
    }}
    QCalendarWidget QTableView::item:hover {{
        background: {hex_rgba(t.primary, 0.12)};
        border-radius: {t.radius_sm}px;
    }}
    QCalendarWidget QTableView::item:selected {{
        background: {sel_bg};
        color: {sel_fg};
        font-weight: 700;
        border-radius: {t.radius_sm}px;
    }}
    QCalendarWidget QHeaderView::section {{
        background: transparent;
        color: {t.text_muted};
        border: none;
        padding: 8px 0;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    """


# ═════════════════════════════════════════════════════════════════════════════
# 日历下拉图标（嵌入 QDateEdit 右内侧）
# ═════════════════════════════════════════════════════════════════════════════

def _ensure_calendar_icon(theme: Theme) -> str:
    """生成主题色日历图标 SVG，返回 QSS url() 路径。"""
    import tempfile
    color = theme.text
    rgb = _hex_to_rgb(theme.text)
    fill_rgb = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})" if rgb else color
    # 三段式日历图标：圆角外框 + 顶部横线 + 装订线
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="18" '
        'viewBox="0 0 24 24" fill="none">'
        # 半透明日期区
        f'<path d="M4 8 H20 V18 C20 19.1 19.1 20 18 20 H6 C4.9 20 4 19.1 4 18 Z" '
        f'fill="{fill_rgb}" fill-opacity="0.12"/>'
        # 外框
        f'<rect x="4" y="5" width="16" height="15" rx="3" '
        f'stroke="{color}" stroke-width="1.8" fill="none"/>'
        # 顶部横线
        f'<path d="M4 9.5 H20" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round"/>'
        # 装订线
        f'<path d="M8 3 V6.5" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round"/>'
        f'<path d="M16 3 V6.5" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round"/>'
        '</svg>'
    )
    icon_dir = os.path.join(
        os.environ.get("QINGNING_TODO_HOME",
                        os.path.join(os.path.expanduser("~"), ".qingning_todo")),
        "_icons")
    os.makedirs(icon_dir, exist_ok=True)
    icon_path = os.path.join(icon_dir, f"cal_{theme.name}.svg")
    try:
        with open(icon_path, "w", encoding="utf-8") as f:
            f.write(svg)
    except OSError:
        icon_path = os.path.join(tempfile.gettempdir(), f"qingning_cal_{theme.name}.svg")
        with open(icon_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return icon_path.replace("\\", "/")


# ═════════════════════════════════════════════════════════════════════════════
# QSS 生成器（核心：1:1 还原 HTML 原型）
# ═════════════════════════════════════════════════════════════════════════════

def _grad(direction: tuple, stops: list) -> str:
    """生成 qlineargradient 字符串。"""
    parts = [f"qlineargradient(x1:{direction[0]}, y1:{direction[1]}, "
             f"x2:{direction[2]}, y2:{direction[3]}"]
    for pos, color in stops:
        parts.append(f", stop:{pos} {color}")
    parts.append(")")
    return "".join(parts)


def build_qss(t: Theme) -> str:
    """1:1 还原两个 HTML 原型的视觉。

    关键设计（来自 HTML 原型）：
    - light：右上角 radial-gradient 绿色光晕 + 卡片 24px 8px 不对称圆角 + 浅色阴影
    - dark：conic-gradient 极光旋转 + 玻璃卡片 backdrop-blur + 18px 统一圆角
    """
    is_dark = t.name == "dark"
    cal_icon_path = _ensure_calendar_icon(t)

    # ── 渐变令牌 ──
    # 主按钮渐变：与 .btn-primary 一致（实际纯色即可，原型 .btn 已是单色）
    # Hero 渐变：1:1 还原 linear-gradient(135deg, primary, secondary)
    if is_dark:
        # Aurora UI hero: 高不透明度渐变，确保白色文字清晰可读
        # 原型 Aurora UI .hero 使用 backdrop-blur + 半透明，但 QSS 无 blur，
        # 用高 alpha (0.85/0.70/0.85) 模拟玻璃态的浓郁极光感
        hero_grad = _grad(
            (0, 0, 1, 1),
            [(0, hex_rgba(t.primary, 0.85)),
             (0.5, hex_rgba(t.secondary, 0.70)),
             (1, hex_rgba(t.accent, 0.85))]
        )
    else:
        # Organic Biophilic hero: linear-gradient(135deg, #5B8A3A, #7BAE5C 50%, #A8C97F)
        # 但带 8px 32px 8px 32px 不对称圆角（通过单独对象实现）
        hero_grad = _grad(
            (0, 0, 1, 1),
            [(0, t.primary), (0.5, t.secondary), (1, "#A8C97F")]
        )

    # 进度条渐变
    progress_grad = _grad(
        (0, 0, 1, 0),
        [(0, t.primary), (1, t.secondary)]
    )

    # 头像渐变
    avatar_grad = _grad(
        (0, 0, 1, 1),
        [(0, t.primary), (1, t.secondary)]
    )

    # 圆形头像渐变
    avatar_round_grad = _grad(
        (0, 0, 1, 1),
        [(0, t.secondary), (1, t.accent)]
    )

    # ── 背景：1:1 还原 body 渐变 ──
    # Organic Biophilic:
    #   body { background: #F2F5EE; background-image: radial-gradient(ellipse at top right, rgba(120,180,100,0.1), transparent 50%) }
    # Aurora UI:
    #   body::before { conic-gradient(from 0deg at 70% 30%, primary, secondary, accent, primary); filter: blur(90px); opacity: .4; animation: auroraSpin 25s linear infinite }
    if is_dark:
        # 主背景叠加（极光）—— 通过 QSS 静态 conic-gradient 实现，
        # 动画由 main_window 中的 QLabel 极光层完成。
        aurora_grad = (
            f"qconicalgradient(cx:0.7, cy:0.3, angle:0, "
            f"stop:0 {t.primary}, "
            f"stop:0.5 {t.secondary}, "
            f"stop:1 {t.accent})"
        )
        main_bg = (
            f"background-color: {t.bg}; "
            f"background-image: {aurora_grad}; "
            f"background-repeat: no-repeat; "
            f"background-position: center;"
        )
    else:
        # Organic Biophilic 右上角绿色椭圆光晕
        bg_glow = hex_rgba("#78B464", 0.10)
        main_bg = (
            f"background-color: {t.bg}; "
            f"background-image: qradialgradient("
            f"cx:1, cy:0, radius:1.2, "
            f"fx:1, fy:0, "
            f"stop:0 {bg_glow}, "
            f"stop:0.5 {bg_glow}, "
            f"stop:1 transparent); "
            f"background-repeat: no-repeat;"
        )

    # ── 圆角变体（统一对称圆角） ──
    if is_dark:
        card_radius = f"{t.radius_lg}px"  # 28px 对称
        hero_radius = f"{t.radius_lg}px"  # 28px 对称
    else:
        card_radius = f"{t.radius_lg}px"  # 对称圆角
        hero_radius = f"{t.radius_lg}px"  # 对称圆角

    # ── 状态色 rgba 派生（hover/selected 软底） ──
    if is_dark:
        nav_hover = hex_rgba(t.primary, 0.12)
        card_hover_glow = hex_rgba(t.primary, 0.30)
        focus_glow = hex_rgba(t.primary, 0.50)
        btn_hover_border = hex_rgba(t.primary, 0.35)
        slider_glow = hex_rgba(t.primary, 0.40)
    else:
        nav_hover = hex_rgba(t.primary, 0.06)
        card_hover_glow = hex_rgba(t.primary, 0.20)
        focus_glow = hex_rgba(t.primary, 0.35)
        btn_hover_border = hex_rgba(t.primary, 0.15)
        slider_glow = hex_rgba(t.primary, 0.25)

    # ── 状态色软底（chip、soft） ──
    success_soft = hex_rgba(t.success, 0.15)
    warning_soft = hex_rgba(t.warning, 0.15)
    danger_soft = hex_rgba(t.danger, 0.15)
    primary_soft_15 = hex_rgba(t.primary, 0.15)

    return f"""
    /* ═════ 基础 ═════ */
    QWidget {{
        {main_bg}
        color: {t.text};
        font-family: {t.font_b};
        font-size: 13px;
    }}
    QLabel {{
        background: transparent;
        color: {t.text};
        font-family: {t.font_b};
    }}
    QLabel#titleDisplay {{ font-family: {t.font_d}; }}
    QLabel#subtitle {{ color: {t.text_muted}; font-size: 12px; }}
    QLabel#muted {{ color: {t.text_muted}; }}
    QLabel#subtle {{ color: {t.text_subtle}; font-size: 12px; }}

    /* ═════ 卡片：1:1 还原 .component-card 样式 ═════ */
    QFrame#card {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {card_radius};
    }}
    QFrame#card:hover {{
        border: 1px solid {t.primary};
    }}
    QFrame#panel {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
    }}

    /* 玻璃卡片：Aurora UI .component-card backdrop-blur 模拟 */
    QFrame#glassCard {{
        background: {hex_rgba(t.surface, 0.85)};
        border: 1px solid {hex_rgba(t.primary, 0.18) if is_dark else hex_rgba('#FFFFFF', 0.6)};
        border-radius: {t.radius_lg}px;
    }}

    /* ═════ 侧栏：1:1 还原 .sidebar 样式 ═════ */
    QWidget#sidebar, QFrame#sidebarItem {{
        background: {t.bg};
        border: none;
        border-right: 1px solid {t.border};
    }}
    QFrame#sidebarSeparator {{ background: {t.border}; }}

    /* ═════ 按钮：1:1 还原 .btn 系列 ═════ */
    QPushButton#primary {{
        background: {t.primary};
        color: {t.on_primary};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 6px 16px;
        font-weight: 500;
        font-size: 12px;
        min-height: 28px;
    }}
    QPushButton#primary:hover {{
        opacity: 0.9;
    }}
    QPushButton#primary:pressed {{
        background: {t.primary_pressed};
    }}
    QPushButton#primary:disabled {{
        background: {t.surface_variant};
        color: {t.text_subtle};
        opacity: 0.5;
    }}

    /* 幽灵按钮 */
    QPushButton#ghost {{
        background: transparent;
        color: {t.primary};
        border: 1px solid {t.primary};
        border-radius: {t.radius_sm}px;
        padding: 6px 15px;
        font-weight: 500;
        font-size: 12px;
    }}
    QPushButton#ghost:hover {{
        background: {t.primary_soft};
    }}
    QPushButton#ghost:pressed {{
        background: {t.primary_soft};
        color: {t.primary_pressed};
    }}
    QPushButton#ghost:disabled {{
        color: {t.text_subtle};
        border: 1px solid {t.border};
    }}

    /* 成功/危险/强调按钮 */
    QPushButton#success {{
        background: {t.success};
        color: {t.on_success};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 7px 16px;
        font-weight: 500;
        font-size: 12px;
    }}
    QPushButton#success:hover {{ background: {t.success_hover}; }}
    QPushButton#success:pressed {{ background: {t.success_pressed}; }}
    QPushButton#success:disabled {{
        background: {t.surface_variant};
        color: {t.text_subtle};
    }}

    QPushButton#danger {{
        background: {t.danger};
        color: {t.on_danger};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 7px 16px;
        font-weight: 500;
        font-size: 12px;
    }}
    QPushButton#danger:hover {{ background: {t.danger_hover}; }}
    QPushButton#danger:disabled {{
        background: {t.surface_variant};
        color: {t.text_subtle};
    }}

    QPushButton#danger_ghost {{
        background: transparent;
        color: {t.danger};
        border: 1.5px solid {t.danger};
        border-radius: {t.radius_sm}px;
        padding: 6px 15px;
        font-weight: 500;
    }}
    QPushButton#danger_ghost:hover {{
        background: {t.danger};
        color: {t.on_danger};
    }}

    /* 图标按钮 */
    QPushButton#iconBtn {{
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 0;
    }}
    QPushButton#iconBtn:hover {{
        background: {nav_hover};
    }}

    /* ═════ 输入框：1:1 还原 .input / .preview-input ═════ */
    QLineEdit {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 7px 10px;
        font-size: 12px;
        font-family: {t.font_b};
        min-height: 30px;
    }}
    QLineEdit:hover {{
        border: 1px solid {t.primary};
    }}
    QLineEdit:focus {{
        border: 1px solid {t.primary};
    }}
    QLineEdit:disabled {{
        color: {t.text_subtle};
        background: {t.surface_variant};
    }}

    /* 下拉框 */
    QComboBox {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 0 10px;
        font-size: 12px;
        min-height: 24px;
    }}
    QComboBox:hover {{ border: 1px solid {t.primary}; }}
    QComboBox:focus {{ border: 1px solid {t.primary}; }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox::down-arrow {{
        width: 8px; height: 8px;
        border-left: 2px solid {t.text_muted};
        border-bottom: 2px solid {t.text_muted};
        transform: rotate(-45deg);
    }}
    QComboBox QAbstractItemView {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        selection-background-color: {t.primary_soft};
        selection-color: {t.primary};
        padding: 4px;
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 6px 10px;
        border-radius: {t.radius_sm}px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {nav_hover};
    }}

    /* 多行文本 */
    QTextEdit, QPlainTextEdit {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 7px 10px;
        font-family: {t.font_b};
        font-size: 12px;
        selection-background-color: {t.primary_soft};
        selection-color: {t.text};
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {t.primary};
    }}

    /* ═════ 数字/时间/日期 ═════ */
    QSpinBox, QDoubleSpinBox, QTimeEdit, QDateEdit, QDateTimeEdit {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 7px 10px;
        font-size: 12px;
        min-height: 34px;
    }}
    QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover, QDateEdit:hover, QDateTimeEdit:hover {{
        border: 1px solid {t.primary};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus, QDateEdit:focus, QDateTimeEdit:focus {{
        border: 1px solid {t.primary};
    }}
    QSpinBox:disabled, QDoubleSpinBox:disabled, QTimeEdit:disabled, QDateEdit:disabled, QDateTimeEdit:disabled {{
        color: {t.text_subtle};
        background: {t.surface_variant};
    }}

    /* SpinBox：隐藏原生上下箭头（已用 PlusMinusSpinBox +/- 按钮替代） */
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QTimeEdit::up-button, QDateTimeEdit::up-button {{
        width: 0px; height: 0px; border: none; background: transparent;
        margin: 0; padding: 0;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button,
    QTimeEdit::down-button, QDateTimeEdit::down-button {{
        width: 0px; height: 0px; border: none; background: transparent;
        margin: 0; padding: 0;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QTimeEdit::up-arrow, QDateTimeEdit::up-arrow {{
        image: none; width: 0; height: 0;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
    QTimeEdit::down-arrow, QDateTimeEdit::down-arrow {{
        image: none; width: 0; height: 0;
    }}

    /* QDateEdit：隐藏原生上下箭头按钮（已被 CalendarDateEdit 替代，保留兼容） */
    QDateEdit {{ padding: 7px 10px; }}
    QDateEdit::up-button {{
        width: 0px; height: 0px; border: none; background: transparent;
        margin: 0; padding: 0;
    }}
    QDateEdit::down-button {{
        width: 0px; height: 0px; border: none; background: transparent;
        margin: 0; padding: 0;
    }}
    QDateEdit::down-arrow {{ image: none; width: 0; height: 0; }}
    QDateEdit::up-arrow {{ image: none; width: 0; height: 0; }}

    /* ═════ 复选框：1:1 还原 .chk-box ═════ */
    QCheckBox {{
        spacing: 6px;
        color: {t.text};
        font-size: 12px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border-radius: 3px;
        border: 2px solid {t.border};
        background: {t.surface};
    }}
    QCheckBox::indicator:hover {{
        border: 2px solid {t.primary};
    }}
    QCheckBox::indicator:checked {{
        background: {t.primary};
        border: 2px solid {t.primary};
        image: none;
    }}
    QCheckBox:disabled {{ color: {t.text_subtle}; }}
    QCheckBox::indicator:disabled {{
        background: {t.surface_variant};
        border-color: {t.divider};
    }}

    /* ═════ 单选：1:1 还原 .rad-dot ═════ */
    QRadioButton {{
        spacing: 6px;
        color: {t.text};
        font-size: 12px;
    }}
    QRadioButton::indicator {{
        width: 16px; height: 16px;
        border-radius: 8px;
        border: 2px solid {t.border};
        background: {t.surface};
    }}
    QRadioButton::indicator:hover {{
        border: 2px solid {t.primary};
    }}
    QRadioButton::indicator:checked {{
        border: 2px solid {t.primary};
        background: {t.surface};
    }}
    QRadioButton::indicator:checked::after {{
        /* QSS 不支持 ::after；选中效果由 QPainter 替代，详见 widgets.py */
    }}
    QRadioButton:disabled {{ color: {t.text_subtle}; }}

    /* ═════ 开关 Switch：1:1 还原 .switch ═════ */
    QCheckBox#switch {{ spacing: 10px; }}
    QCheckBox#switch::indicator {{
        width: 40px; height: 22px;
        border-radius: 11px;
        border: none;
        background: {t.switch_track};
    }}
    QCheckBox#switch::indicator:hover {{
        background: {t.border};
    }}
    QCheckBox#switch::indicator:checked {{
        background: {t.primary};
    }}

    /* ═════ 滑块：1:1 还原 .slider-track/.slider-knob ═════ */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t.border};
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t.primary};
        border-radius: 3px;
    }}
    QSlider::add-page:horizontal {{
        background: {t.border};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {t.surface};
        border: 2px solid {t.primary};
        width: 16px; height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{
        border: 2px solid {t.primary};
    }}
    QSlider::groove:vertical {{
        width: 6px;
        background: {t.border};
        border-radius: 3px;
    }}
    QSlider::sub-page:vertical {{
        background: {t.primary};
        border-radius: 3px;
    }}
    QSlider::handle:vertical {{
        background: {t.surface};
        border: 2px solid {t.primary};
        width: 16px; height: 16px;
        margin: 0 -5px;
        border-radius: 8px;
    }}

    /* ═════ 进度条：1:1 还原 .progress ═════ */
    QProgressBar {{
        background: {t.border};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
        color: {t.text};
        font-size: 11px;
    }}
    QProgressBar::chunk {{
        background: {progress_grad};
        border-radius: 4px;
    }}

    /* ═════ 标签页：1:1 还原 .tab-bar/.tab-item ═════ */
    QTabWidget::pane {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t.text_muted};
        border: none;
        padding: 8px 14px;
        font-size: 12px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {t.primary};
        border-bottom: 2px solid {t.primary};
    }}
    QTabBar::tab:hover:!selected {{ color: {t.text}; }}

    /* ═════ 表格：1:1 还原 .table ═════ */
    QTableWidget, QTableView {{
        background: {t.surface};
        alternate-background-color: {t.surface_variant};
        color: {t.text};
        gridline-color: {t.divider};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        selection-background-color: {t.primary_soft};
        selection-color: {t.text};
        outline: none;
    }}
    QHeaderView::section {{
        background: {t.surface_variant};
        color: {t.text_muted};
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid {t.border};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }}
    QHeaderView::section:hover {{
        color: {t.primary};
    }}
    QTableWidget::item, QTableView::item {{
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid {t.divider};
    }}
    QTableWidget::item:selected, QTableView::item:selected {{
        background: {t.primary_soft};
        color: {t.text};
    }}

    /* ═════ 列表：1:1 还原 ═════ */
    QListWidget, QListView {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item, QListView::item {{
        padding: 6px 10px;
        border-radius: {t.radius_sm}px;
        border: none;
    }}
    QListWidget::item:hover, QListView::item:hover {{
        background: {nav_hover};
    }}
    QListWidget::item:selected, QListView::item:selected {{
        background: {t.primary_soft};
        color: {t.primary};
        font-weight: 600;
    }}

    /* 树 */
    QTreeView, QTreeWidget {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        padding: 4px;
        outline: none;
    }}
    QTreeView::item, QTreeWidget::item {{
        padding: 4px 8px;
        border-radius: {t.radius_sm}px;
        min-height: 24px;
    }}
    QTreeView::item:hover, QTreeWidget::item:hover {{
        background: {nav_hover};
    }}
    QTreeView::item:selected, QTreeWidget::item:selected {{
        background: {t.primary_soft};
        color: {t.primary};
    }}

    /* 分组框 */
    QGroupBox {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        margin-top: 16px;
        padding: 16px 14px 14px 14px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        background: {t.surface};
        color: {t.text};
    }}

    /* 工具栏 */
    QToolBar {{
        background: {t.surface};
        border-bottom: 1px solid {t.border};
        spacing: 4px;
        padding: 4px;
    }}
    QToolBar::separator {{
        background: {t.divider};
        width: 1px;
        margin: 4px 6px;
    }}

    /* 状态栏 */
    QStatusBar {{
        background: {t.surface};
        color: {t.text_muted};
        border-top: 1px solid {t.divider};
    }}

    /* 菜单 */
    QMenuBar {{
        background: {t.surface};
        color: {t.text};
        border-bottom: 1px solid {t.divider};
        padding: 2px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: {t.radius_sm}px;
    }}
    QMenuBar::item:selected {{
        background: {nav_hover};
        color: {t.primary};
    }}
    QMenu {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 32px 8px 16px;
        border-radius: {t.radius_sm}px;
        margin: 1px 0;
    }}
    QMenu::item:selected {{
        background: {t.primary_soft};
        color: {t.text};
    }}
    QMenu::item:disabled {{ color: {t.text_subtle}; }}
    QMenu::separator {{
        height: 1px;
        background: {t.divider};
        margin: 4px 8px;
    }}
    QMenu::icon {{ width: 16px; height: 16px; }}

    /* 工具提示 */
    QToolTip {{
        background: {t.text};
        color: {t.surface};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 6px 12px;
        font-size: 11px;
    }}

    /* 对话框 */
    QDialog {{ background: {t.bg}; }}
    QMessageBox {{
        background: {t.surface};
        color: {t.text};
    }}
    QMessageBox QLabel {{
        color: {t.text};
        font-size: 12px;
    }}
    QMessageBox QPushButton {{ min-width: 80px; }}

    /* 停靠窗口 */
    QDockWidget {{
        color: {t.text};
        font-size: 12px;
    }}
    QDockWidget::title {{
        background: {t.surface_variant};
        padding: 6px 10px;
        border-bottom: 1px solid {t.border};
        font-weight: 600;
    }}

    /* ═════ 滚动条：1:1 还原 ::-webkit-scrollbar ═════ */
    QScrollBar:vertical {{
        background: transparent; width: 6px; margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        border-radius: 3px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.text_muted};
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border};
        border-radius: 3px; min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t.text_muted};
    }}
    QScrollBar:horizontal {{
        background: transparent; height: 6px; margin: 2px 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        height: 0; width: 0; background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}

    /* ═════ 胶囊/标签 Chip：1:1 还原 .tag ═════ */
    QLabel#chip, QLabel#tag {{
        background: {t.surface_variant};
        color: {t.primary};
        border: 1px solid {hex_rgba(t.primary, 0.30)};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#chipPill {{
        background: {primary_soft_15};
        color: {t.primary};
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#chipSuccess {{
        background: {success_soft};
        color: {t.success};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#chipWarning {{
        background: {warning_soft};
        color: {t.warning};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#chipDanger {{
        background: {danger_soft};
        color: {t.danger};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#chipSolid {{
        background: {t.accent};
        color: #FFFFFF;
        border-radius: 9px;
        padding: 0 5px;
        min-width: 18px;
        min-height: 18px;
        font-size: 10px;
        font-weight: 700;
    }}

    /* 状态徽章（pill） */
    QLabel#statusPill, QLabel#pill {{
        background: {t.surface_variant};
        color: {t.primary};
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#pillOn {{
        background: {t.surface_variant};
        color: {t.primary};
        border-radius: 8px;
        padding: 1px 6px;
        font-size: 11px;
        font-weight: 500;
    }}

    /* 头像 */
    QLabel#avatar {{
        background: {avatar_grad};
        color: #FFFFFF;
        border-radius: 50%;
        font-weight: 600;
        font-size: 13px;
    }}
    QLabel#avatarRect {{
        background: {avatar_grad};
        color: #FFFFFF;
        border-radius: {t.radius_sm}px;
        font-weight: 600;
        font-size: 13px;
    }}

    /* ═════ 标题栏 ═════ */
    QWidget#titleBar {{
        background: {t.bg};
        border: none;
        border-bottom: 1px solid {t.border};
    }}
    QWidget#titleDrag {{ background: transparent; }}
    QLabel#titleText {{ color: {t.sidebar_text}; font-size: 12px; font-weight: 600; }}

    /* ═════ 导航按钮：1:1 还原 .sidebar-item（含左侧指示条） ═════ */
    QPushButton#navBtn {{
        background: transparent;
        border: none;
        border-radius: 0;
        font-size: 13px;
        font-weight: 400;
        color: {t.text_muted};
        text-align: left;
        padding: 8px 20px;
        margin: 0;
    }}
    QPushButton#navBtn:hover {{
        background: {t.surface_variant};
        color: {t.primary};
    }}
    QPushButton#navBtn:checked {{
        background: {t.surface_variant};
        color: {t.primary};
        font-weight: 500;
        border-left: 3px solid {t.primary};
    }}

    /* ═════ Hero 横幅：1:1 还原 .hero ═════ */
    QFrame#heroBanner {{
        background: {hero_grad};
        border-radius: {hero_radius};
        {'border: 1px solid ' + hex_rgba(t.primary, 0.30) + ';' if is_dark else ''}
    }}
    QLabel#heroTitle {{
        color: #FFFFFF;
        font-family: {t.font_d};
        font-size: 32px;
        font-weight: 700;
    }}
    QLabel#heroDesc {{
        color: #FFFFFF;
        font-size: 15px;
        opacity: 0.9;
    }}
    QLabel#heroMeta {{
        color: #FFFFFF;
        font-size: 13px;
        opacity: 0.85;
    }}

    /* ═════ 分段控件：1:1 还原 .tab-bar 风格 ═════ */
    QPushButton#segTab {{
        background: {t.surface_variant};
        color: {t.text_muted};
        border: none;
        border-radius: {t.radius_sm}px;
        padding: 4px 14px;
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton#segTab:hover {{
        background: {t.surface};
        color: {t.text};
    }}
    QPushButton#segTab:checked {{
        background: {t.primary};
        color: {t.on_primary};
        font-weight: 600;
    }}

    /* 选择芯片 */
    QPushButton#chip {{
        background: {t.surface_variant};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 0 10px;
        font-size: 11px;
        min-height: 26px;
    }}
    QPushButton#chip:hover {{
        border: 1px solid {t.primary};
    }}
    QPushButton#chip:checked {{
        background: {t.primary};
        color: {t.on_primary};
        border: 1px solid {t.primary};
        font-weight: 600;
    }}

    QPushButton#chipMuted {{
        background: {t.surface_variant};
        color: {t.text_muted};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 0 10px;
        font-size: 11px;
    }}
    QPushButton#chipMuted:hover {{ color: {t.text}; }}
    QPushButton#chipMuted:checked {{
        background: {t.text_muted};
        color: {t.surface};
        border: 1px solid {t.text_muted};
        font-weight: 600;
    }}

    QPushButton#chipDashed {{
        background: transparent;
        color: {t.primary};
        border: 1px dashed {t.primary};
        border-radius: {t.radius_sm}px;
        padding: 0 10px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton#chipDashed:hover {{
        background: {t.primary};
        color: {t.on_primary};
        border-style: solid;
    }}

    /* ═════ 大号开关（Switch）═══ */
    QCheckBox#switch {{ spacing: 10px; }}
    QCheckBox#switch::indicator {{
        width: 40px; height: 20px;
        border-radius: 10px;
        border: 1px solid {t.border};
        background: {t.switch_track};
    }}
    QCheckBox#switch::indicator:hover {{ border: 1px solid {focus_glow}; }}
    QCheckBox#switch::indicator:checked {{
        background: {t.primary};
        border: 1px solid {t.primary};
    }}

    /* ═════ 焦点通用样式（无障碍） ═════ */
    QPushButton:focus {{
        outline: none;
        border: 1px solid {focus_glow};
    }}
    QPushButton#primary:focus {{
        border: none;
    }}
    QPushButton:disabled {{
        color: {t.text_subtle};
        background: {t.surface_variant};
    }}

    /* ═════ 卡片分割/装饰元素 ═════ */
    QLabel#divider {{
        background: {t.divider};
        max-height: 1px;
        min-height: 1px;
    }}

    /* ═════ 统计大数字 ═════ */
    QLabel#statValue {{
        color: {t.text};
        font-family: {t.font_d};
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }}
    QLabel#statLabel {{
        color: {t.text_muted};
        font-size: 11px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    QLabel#statDelta {{
        color: {t.success};
        font-size: 11px;
        font-weight: 600;
    }}

    /* ═════ QMainWindow / QStackedWidget 透明背景（让 body 渐变透出） ═════ */
    QMainWindow {{
        background: transparent;
    }}
    QMainWindow::separator {{
        background: {t.border};
        width: 1px; height: 1px;
    }}
    QStackedWidget {{
        background: transparent;
    }}
    QWidget#appContent {{
        {main_bg}
    }}

    /* ═════ 日历 Widget (calendarPopup 是独立顶层窗口, 走 _build_calendar_qss) ═════ */
    {_build_calendar_qss()}
    QFrame#toast {{
        background: {t.surface};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
        padding: 10px 16px;
    }}
    QFrame#toastSuccess {{ background: {t.success}; color: #FFFFFF; border-radius: {t.radius_md}px; padding: 10px 16px; }}
    QFrame#toastError {{ background: {t.danger}; color: #FFFFFF; border-radius: {t.radius_md}px; padding: 10px 16px; }}
    QFrame#toastWarning {{ background: {t.warning}; color: #FFFFFF; border-radius: {t.radius_md}px; padding: 10px 16px; }}
    QFrame#toastInfo {{ background: {t.primary}; color: #FFFFFF; border-radius: {t.radius_md}px; padding: 10px 16px; }}

    /* 段落标题 */
    QLabel#recHeader {{ color: {t.text_muted}; font-weight: 700; }}
    """
