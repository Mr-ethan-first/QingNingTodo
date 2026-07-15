"""主题系统（Flet）。

提供两套精心设计的视觉风格：
- LIGHT（白色风格）：清爽明亮、留白充足的现代浅色主题
- DARK（黑色风格）：沉稳高级、低饱和的深色主题

主题令牌（Theme）集中管理颜色、圆角、阴影、字体，页面通过
AppState 持有的当前主题渲染，切换主题时统一重新构建控件树。
"""
from dataclasses import dataclass, field
from typing import Dict

from flet import Colors, FontWeight


@dataclass
class Theme:
    """一套完整的视觉令牌。"""

    name: str                       # 主题唯一键
    label: str                      # 展示名
    # 基础色
    bg: str                         # 应用整体背景
    surface: str                    # 卡片/面板背景
    surface_variant: str            # 次级面板（输入框、悬浮行）
    primary: str                    # 主色（品牌色）
    primary_hover: str              # 主色 hover
    on_primary: str                 # 主色上的文字
    text: str                       # 主文字
    text_muted: str                 # 次要文字
    text_subtle: str                # 极弱文字
    border: str                     # 描边/分割线
    divider: str                    # 弱化分割线
    # 状态色
    success: str
    warning: str
    danger: str
    # 形状
    radius_sm: int = 8
    radius_md: int = 14
    radius_lg: int = 20
    # 阴影
    shadow: Dict = field(default_factory=dict)
    # 强调辅助（主色的浅底色，用于徽章/图标块）
    primary_soft: str = ""
    # 热力图基础色（主色）
    heat_base: str = ""

    def soft(self) -> str:
        return self.primary_soft or self.primary


# ----------------------------- 白色风格 -----------------------------
LIGHT = Theme(
    name="light",
    label="皓白 · 清新白",
    bg="#F4F6FB",
    surface="#FFFFFF",
    surface_variant="#F1F3F9",
    primary="#E2574C",          # 朱红（保留品牌识别）
    primary_hover="#C9443A",
    on_primary="#FFFFFF",
    text="#1F2430",
    text_muted="#5B6472",
    text_subtle="#9AA3B2",
    border="#E3E7F0",
    divider="#EEF1F6",
    success="#2E9E6B",
    warning="#E0A23B",
    danger="#D8453C",
    radius_sm=8,
    radius_md=14,
    radius_lg=20,
    shadow={"blur_radius": 18, "color": "#1F24301F", "offset": (0, 6)},
    primary_soft="#FBE9E7",
    heat_base="#E2574C",
)

# ----------------------------- 黑色风格 -----------------------------
DARK = Theme(
    name="dark",
    label="墨夜 · 深邃黑",
    bg="#15171C",
    surface="#1E2128",
    surface_variant="#262A33",
    primary="#F0726A",          # 偏亮朱红，深色背景上更醒目
    primary_hover="#FF8178",
    on_primary="#1A1C22",
    text="#ECEEF3",
    text_muted="#A6ADBB",
    text_subtle="#6E7686",
    border="#2E333D",
    divider="#262A33",
    success="#43C28A",
    warning="#E6B45C",
    danger="#F0726A",
    radius_sm=8,
    radius_md=14,
    radius_lg=20,
    shadow={"blur_radius": 22, "color": "#00000066", "offset": (0, 8)},
    primary_soft="#3A2A2A",
    heat_base="#F0726A",
)

THEMES: Dict[str, Theme] = {LIGHT.name: LIGHT, DARK.name: DARK}
DEFAULT_THEME = LIGHT.name


def get_theme(name: str) -> Theme:
    return THEMES.get(name, LIGHT)
