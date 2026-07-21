"""设计令牌（Design Tokens）——「青柠晨露」设计系统的单一事实来源。

所有间距 / 圆角 / 字阶 / 阴影 / 动效时长均从此处引用，禁止在 QSS 或布局中
写死魔法数字。组件（`widgets.py`）与 `theme.build_qss` 一律 import 本模块。

标度遵循 4/8px 网格与 ≈1.25 字阶比例，与 Vercel / Linear / Stripe 设计系统
的克制原则一致。

v2 升级：新增渐变令牌、发光令牌、动效曲线令牌，支撑「小清新 × 专业炫酷」
视觉升级——渐变按钮、发光焦点环、分层投影、悬浮微动。
v3 升级：补全 type_scale / space / radius / pad 全量阶梯,新增 z-index 层级管理。
"""
from types import SimpleNamespace

# ───── 间距标度（4 / 8px 网格） ─────
space = SimpleNamespace(
    xxs=2,
    xs=4,
    sm=8,
    md=12,
    lg=16,
    xl=20,
    xxl=24,
    xxxl=32,
    huge=48,
)

# ───── 圆角标度 ─────
radius = SimpleNamespace(
    xs=4,      # 微圆角(标签/小徽章)
    sm=8,      # 小圆角(输入框/列表项)
    md=12,     # 中圆角(按钮/面板)
    lg=16,     # 大圆角(卡片)
    xl=20,     # 加大圆角(对话框)
    xxl=28,    # 巨圆角(hero 卡片)
    pill=999,  # 胶囊(状态徽章)
)

# ───── 字阶标度（比例 ≈1.25，基准 13） ─────
type_scale = SimpleNamespace(
    xs=11,     # 辅助说明
    sm=12,     # 副文字/时间戳
    base=13,   # 正文
    md=14,     # 偏大正文
    lg=16,     # 小标题
    xl=18,     # 中标题/弹窗标题
    xxl=22,    # 大标题/页面标题
    xxxl=28,   # hero
    display=34,  # 计量卡数字/统计大字
)

# ───── 组件内边距（命名令牌，避免散落魔法数字） ─────
pad = SimpleNamespace(
    btn_y=10,
    btn_x=22,
    btn_sm_y=6,
    btn_sm_x=14,
    btn_lg_y=12,
    btn_lg_x=28,
    input_y=9,
    input_x=14,
    input_h=36,        # 输入框统一高度
    btn_h=36,          # 按钮统一高度
    btn_lg_h=44,       # 大按钮高度
    icon_btn=32,       # 图标按钮
    icon_btn_sm=28,    # 小图标按钮
    tight=6,
    tight_y=4,
    card_x=16,
    card_y=14,
    panel_x=20,
    panel_y=18,
    dialog_x=24,
    dialog_y=20,
    seg_x=14,
    chip_x=10,
    chip_y=4,
    list_x=14,
    list_y=10,
)

# ───── 阴影标度 (blur, offset_y, alpha) ─────
shadow = SimpleNamespace(
    sm=(16, 3, 18),       # 卡片静态态：轻柔贴近
    md=(28, 6, 30),       # 卡片悬浮态：明显抬升
    lg=(40, 10, 48),      # 对话框/弹层：高位悬浮
    glow_blur=16,         # 发光模糊半径
    glow_alpha=80,        # 发光透明度(0-255)
)

# ───── 动效时长（毫秒，按用途细分） ─────
motion = SimpleNamespace(
    instant=80,    # 瞬时反馈
    fast=150,      # 快速微动效
    base=240,      # 基础动画
    smooth=320,    # 较慢/页面过渡
    toggle=200,    # 滑块开关
    dialog=240,    # 弹窗进出
    toast=300,     # 通知提示
    carousel=450,  # 轮播
)

# ───── 动效曲线（QEasingCurve.Type 对应值） ─────
easing = SimpleNamespace(
    linear=0,           # Linear
    in_quad=1,          # InQuad
    out_quad=2,         # OutQuad
    in_out_quad=3,      # InOutQuad
    in_cubic=4,         # InCubic
    out_cubic=5,        # OutCubic — 自然减速（默认）
    in_out_cubic=6,     # InOutCubic — 平滑起止
    out_quint=8,        # OutQuint — 优雅减速
    out_back=10,        # OutBack — 轻微回弹
    out_elastic=12,     # OutElastic — 弹性
    in_out_quart=7,     # InOutQuart — 平滑过渡
)

# ───── 渐变方向令牌（供 QSS qlineargradient 使用） ─────
# 格式: (x1, y1, x2, y2) — 方向向量
gradient_dir = SimpleNamespace(
    vertical=(0, 0, 0, 1),       # 上→下
    horizontal=(0, 0, 1, 0),     # 左→右
    diagonal=(0, 0, 1, 1),       # 左上→右下
    diagonal_rev=(1, 0, 0, 1),   # 右上→左下
)

# ───── z-index 层级（统一管理 z-order, 避免遮挡冲突） ─────
z = SimpleNamespace(
    base=0,
    dropdown=50,
    sticky=100,
    toast=500,
    overlay=900,
    dialog=1000,
    popup=1500,
    menu=2000,
    tooltip=3000,
    always_on_top=9999,
)

# ───── 组件尺寸令牌（统一管理） ─────
size = SimpleNamespace(
    icon_xs=12,
    icon_sm=14,
    icon_md=16,
    icon_lg=20,
    icon_xl=24,
    avatar_sm=24,
    avatar_md=32,
    avatar_lg=40,
    control_h=32,        # 小控件
    input_h=36,          # 输入框
    btn_h=36,            # 按钮
    btn_lg_h=44,         # 大按钮
    toolbar_h=48,        # 工具栏
    titlebar_h=44,       # 标题栏
    card_max_w=560,      # 标准卡片最大宽
    sidebar_w=220,       # 侧栏宽度
    sidebar_collapsed_w=64,
)
