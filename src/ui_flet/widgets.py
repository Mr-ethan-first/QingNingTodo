"""通用 Flet UI 组件库（主题感知）。

所有组件均接收 theme（Theme）作为参数，颜色取自主题令牌，保证换肤统一。
"""
from flet import (
    Container, Column, Row, Text, ElevatedButton, OutlinedButton, IconButton,
    TextField, Dropdown, dropdown, Checkbox, Switch, Card, Divider,
    alignment, border, BorderSide, BoxShadow, padding, icons, FontWeight, TextAlign,
    Tooltip, PopupMenuButton, PopupMenuItem, ListView, ControlEvent,
    MainAxisAlignment,
)

from src.theme import Theme


def card(theme: Theme, content, padding_=16, **kwargs) -> Container:
    return Container(
        content=content,
        bgcolor=theme.surface,
        border_radius=theme.radius_lg,
        padding=pad.all(padding_),
        border=border.Border(left=BorderSide(1, theme.border), top=BorderSide(1, theme.border),
                              right=BorderSide(1, theme.border), bottom=BorderSide(1, theme.border)),
        shadow=BoxShadow(
            blur_radius=theme.shadow.get("blur_radius", 16),
            color=theme.shadow.get("color", "#00000010"),
            offset=theme.shadow.get("offset", (0, 4)),
        ),
        **kwargs,
    )


def section_title(theme: Theme, title: str, icon: str = None) -> Row:
    children = []
    if icon:
        children.append(
            Container(
                content=Text(icon, size=16, color=theme.primary),
                bgcolor=theme.soft(),
                border_radius=theme.radius_sm,
                width=34, height=34,
                alignment=align.center,
                margin=pad.only(right=10),
            )
        )
    children.append(
        Text(title, size=18, weight=FontWeight.W_600, color=theme.text)
    )
    return Row(children, alignment=MainAxisAlignment.START, spacing=0)


def primary_button(theme: Theme, text: str, on_click=None, icon=None, width=None, disabled=False):
    return ElevatedButton(
        content=Text(text, color=theme.on_primary), icon=icon, on_click=on_click,
        width=width, disabled=disabled, style=_btn_style(theme, filled=True),
    )


def ghost_button(theme: Theme, text: str, on_click=None, icon=None, width=None, disabled=False):
    return OutlinedButton(
        content=Text(text, color=theme.primary), icon=icon, on_click=on_click,
        width=width, disabled=disabled, style=_btn_style(theme, filled=False),
    )


def _btn_style(theme: Theme, filled: bool):
    from flet import ButtonStyle, RoundedRectangleBorder
    if filled:
        return ButtonStyle(
            color=theme.on_primary,
            bgcolor=theme.primary,
            overlay_color=theme.primary_hover,
            padding=pad.symmetric(horizontal=18, vertical=10),
            shape=RoundedRectangleBorder(radius=theme.radius_md),
        )
    return ButtonStyle(
        color=theme.primary,
        bgcolor=theme.surface,
        overlay_color=theme.soft(),
        side=BorderSide(1, theme.primary),
        padding=pad.symmetric(horizontal=18, vertical=10),
        shape=RoundedRectangleBorder(radius=theme.radius_md),
    )


def text_field(theme: Theme, label: str = None, value: str = "", password: bool = False,
               hint_text: str = None, multiline: bool = False, width=None, on_change=None):
    return TextField(
        label=label, value=value, password=password, can_reveal_password=password,
        hint_text=hint_text, multiline=multiline, width=width, on_change=on_change,
        bgcolor=theme.surface_variant,
        color=theme.text,
        border_color=theme.border,
        focused_border_color=theme.primary,
        label_style=TextStyle(color=theme.text_muted),
        cursor_color=theme.primary,
        border_radius=theme.radius_md,
    )


def dropdown_field(theme: Theme, label: str, options: list, value=None, width=None, on_change=None):
    opts = [dropdown.Option(text=o[1], key=str(o[0])) for o in options]
    return Dropdown(
        label=label, options=opts, value=value, width=width, on_select=on_change,
        bgcolor=theme.surface_variant, color=theme.text,
        border_color=theme.border, focused_border_color=theme.primary,
        label_style=TextStyle(color=theme.text_muted),
        border_radius=theme.radius_md,
    )


def badge(theme: Theme, text: str) -> Container:
    return Container(
        content=Text(text, size=12, color=theme.primary, weight=FontWeight.W_600),
        bgcolor=theme.soft(),
        border_radius=999,
        padding=pad.symmetric(horizontal=10, vertical=3),
    )


def hero_banner(theme: Theme, title: str, subtitle: str) -> Container:
    """页面顶部品牌横幅。"""
    return Container(
        content=Column([
            Text(title, size=22, weight=FontWeight.BOLD, color=theme.on_primary),
            Text(subtitle, size=13, color=theme.on_primary),
        ], spacing=4),
        gradient=_linear_gradient(theme),
        border_radius=theme.radius_lg,
        padding=pad.symmetric(horizontal=22, vertical=16),
        margin=pad.only(bottom=16),
    )


def _linear_gradient(theme: Theme):
    from flet import LinearGradient
    return LinearGradient(
        begin=align.top_left, end=align.bottom_right,
        colors=[theme.primary, theme.primary_hover],
    )


# 局部导入避免循环依赖
from flet import TextStyle  # noqa: E402
from src.ui_flet.align import align
from src.ui_flet.pad import pad


def border_1(theme: "Theme", color: str):
    """生成 1px 全描边。"""
    s = BorderSide(1, color)
    return border.Border(left=s, top=s, right=s, bottom=s)
