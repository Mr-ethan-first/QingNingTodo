"""padding 兼容层（Flet 0.86 将 padding.all 等改为 Padding 类）。

提供 all / symmetric / only 工厂，统一返回 ft.padding.Padding 实例，
便于全局替换旧版 padding.all() 用法。
"""
from flet import padding as _pad


def all(value) -> _pad.Padding:
    return _pad.Padding(value, value, value, value)


def symmetric(horizontal=0, vertical=0) -> _pad.Padding:
    return _pad.Padding(vertical, horizontal, vertical, horizontal)


def only(left=0, top=0, right=0, bottom=0) -> _pad.Padding:
    return _pad.Padding(top, right, bottom, left)


class _Pad:
    all = staticmethod(all)
    symmetric = staticmethod(symmetric)
    only = staticmethod(only)


pad = _Pad()
