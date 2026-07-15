"""alignment 兼容层（Flet 0.86 移除 alignment.center 等预设，改用 Alignment 类）。

提供与旧版一致的名称：center / left / right / top / bottom /
top_left / top_right / bottom_left / bottom_right / center_left / center_right。
"""
from flet import alignment as _a


class _Align:
    center = _a.Alignment(0, 0)
    left = _a.Alignment(-1, 0)
    right = _a.Alignment(1, 0)
    top = _a.Alignment(0, -1)
    bottom = _a.Alignment(0, 1)
    top_left = _a.Alignment(-1, -1)
    top_right = _a.Alignment(1, -1)
    bottom_left = _a.Alignment(-1, 1)
    bottom_right = _a.Alignment(1, 1)
    center_left = _a.Alignment(-1, 0)
    center_right = _a.Alignment(1, 0)


align = _Align()
