"""数据统计图表（PyQt6 / QPainter 自绘，零外部依赖）。

所有图表自适应主题：颜色取自全局当前主题令牌（src.theme.get_current_theme()），
切换主题时由页面调用 set_data 重绘即可，无需重建控件树。
"""
import datetime

import math

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QPainterPath, QLinearGradient,
    QBrush,
)
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from src.theme import get_current_theme


def fmt_minutes(seconds: int) -> str:
    s = int(seconds)
    if s <= 0:
        return "0 分钟"
    m = s // 60
    if m >= 60:
        return f"{m // 60} 小时 {m % 60} 分"
    return f"{m} 分钟"


class StatCard(QFrame):
    """概览大数字卡片（统一内边距、大字号数字 + 小字号标签）。"""

    def __init__(self, title: str, value: str, accent: str):
        super().__init__()
        self.setObjectName("card")
        self._accent = accent
        t = get_current_theme()
        # 数字：28px 大字号
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"font-size:28px; font-weight:700; color:{accent};")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 标签：12px 小字号，使用主题 text_muted 色代替硬编码
        self._title = QLabel(title)
        self._title.setStyleSheet(f"font-size:12px; color:{t.text_muted};")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 统一内边距
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        # 顶部装饰条
        top = QFrame()
        top.setFixedSize(34, 3)
        top.setStyleSheet(f"background:{accent}; border-radius:999px;")
        h = QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(top, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._val)
        lay.addWidget(self._title)

    def set_value(self, value: str):
        self._val.setText(value)


class BarChart(QWidget):
    """竖向柱状图（标签在底部，自适应宽度）。"""

    def __init__(self, accent: str = None):
        super().__init__()
        self._items = []
        self._accent = accent
        self.setMinimumHeight(170)

    def set_data(self, items, accent: str = None):
        self._items = items or []
        if accent:
            self._accent = accent
        n = len(self._items)
        self.setMinimumHeight(170)
        self.setMinimumWidth(max(220, n * 30))
        self.update()

    def paintEvent(self, ev):
        if not self._items:
            self._empty("暂无数据", ev)
            return
        t = get_current_theme()
        accent = self._accent or t.primary
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # 底部预留空间：条目多时标签旋转绘制，需要更大留白
        pad_b = 44
        area_h = h - pad_b - 6
        n = len(self._items)
        gap = 6
        bw = max(10, (w - (n - 1) * gap) / n)
        maxv = max((it.get("value", 0) for it in self._items), default=1) or 1
        # 计算标签间隔：条目过多时只显示约 10 个标签，避免重叠
        label_interval = 1
        if n > 12:
            label_interval = max(1, n // 10)
        for i, it in enumerate(self._items):
            x = i * (bw + gap)
            val = it.get("value", 0)
            bh = int((val / maxv) * area_h) if val > 0 else 3
            bh = max(bh, 3)
            y = h - pad_b - bh
            color = QColor(accent) if val > 0 else QColor(t.text_subtle)
            if val == 0:
                color.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            r = QRect(int(x), int(y), int(bw), int(bh))
            p.drawRoundedRect(r, 5, 5)
            # 只在间隔位置绘制标签
            if i % label_interval == 0 or i == n - 1:
                label_text = str(it.get("label", ""))
                p.setPen(QColor(t.text_muted))
                if bw < 22:
                    # 柱宽较窄时倾斜绘制，完整展示日期标签避免截断
                    p.save()
                    p.translate(int(x + bw / 2), h - pad_b + 6)
                    p.rotate(-40)
                    p.setFont(QFont("Microsoft YaHei UI", 8))
                    p.drawText(
                        QRectF(-80, 0, 160, 14),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        label_text)
                    p.restore()
                else:
                    p.setFont(QFont("Microsoft YaHei UI", 8))
                    p.drawText(int(x) - 4, h - pad_b + 4, int(bw) + 8, 16,
                               Qt.AlignmentFlag.AlignHCenter |
                               Qt.AlignmentFlag.AlignTop, label_text)
        p.end()
        super().paintEvent(ev)

    def _empty(self, msg, ev):
        t = get_current_theme()
        p = QPainter(self)
        p.setPen(QColor(t.text_muted))
        p.setFont(QFont("Microsoft YaHei UI", 13))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
        p.end()
        super().paintEvent(ev)


class TrendChart(QWidget):
    """近 N 天专注趋势：细柱 + 顶部圆点 + 基线。"""

    def __init__(self):
        super().__init__()
        self._series = []
        self._accent = None
        self.setMinimumHeight(120)

    def set_data(self, series, accent: str = None):
        self._series = series or []
        self._accent = accent
        self.setMinimumHeight(120)
        self.setMinimumWidth(max(220, len(self._series) * 12))
        self.update()

    def paintEvent(self, ev):
        if not self._series:
            self._empty("暂无数据", ev)
            return
        t = get_current_theme()
        accent = self._accent or t.primary
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad_b = 6
        area_h = h - pad_b - 6
        n = len(self._series)
        gap = 3
        bw = max(4, (w - (n - 1) * gap) / n)
        maxv = max(self._series, default=1) or 1
        for i, v in enumerate(self._series):
            x = i * (bw + gap)
            bh = int((v / maxv) * area_h) if v > 0 else 3
            bh = max(bh, 3)
            y = h - pad_b - bh
            if v == 0:
                color = QColor(t.text_subtle)
                color.setAlpha(60)
            else:
                color = QColor(accent)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(int(x), int(y), int(bw), int(bh), 3, 3)
            if v > 0:
                p.setBrush(QColor(accent))
                p.drawEllipse(int(x + bw / 2 - 2), int(y - 4), 4, 4)
        p.end()
        super().paintEvent(ev)

    def _empty(self, msg, ev):
        t = get_current_theme()
        p = QPainter(self)
        p.setPen(QColor(t.text_muted))
        p.setFont(QFont("Microsoft YaHei UI", 13))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
        p.end()
        super().paintEvent(ev)


class Heatmap(QWidget):
    """近 30 天专注热力图（6 列 x 5 行网格，悬浮查看明细）。"""

    def __init__(self):
        super().__init__()
        self._lay = QGridLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(5)
        self.setMinimumHeight(150)

    def set_data(self, rows, base: str = None):
        t = get_current_theme()
        base = base or t.primary
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        vals = {r["belong_date"]: int(r["total"]) for r in rows}
        today = datetime.date.today()
        for i in range(30):
            d = today - datetime.timedelta(days=29 - i)
            v = vals.get(d, 0)
            cell = QFrame()
            cell.setFixedSize(22, 22)
            cell.setStyleSheet(
                f"background:{self._shade(base, v, t)}; border-radius:6px;")
            cell.setToolTip(f"{d} · {fmt_minutes(v)}")
            self._lay.addWidget(cell, i // 6, i % 6)

    @staticmethod
    def _shade(base, v, t):
        if v == 0:
            return t.surface_variant
        ratio = min(1.0, v / 7200)  # 2 小时封顶
        alpha = 0.28 + ratio * 0.72
        c = QColor(base)
        c.setAlphaF(alpha)
        # P0 修复: c.name() 不含 alpha 通道 → 所有 cell 渲染为不透明
        # 改用 rgba(r, g, b, a) 字符串, QSS/Qt 都能正确解析 alpha
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alphaF():.3f})"


# ======================= 饼图调色板 =======================
PIE_PALETTE = [
    "#8CC44A", "#26A69A", "#E6A050", "#E75244", "#5C6BC0",
    "#AB47BC", "#26A69A", "#EF6C00", "#78909C", "#EC407A",
]


# ======================= PieChart 饼图 =======================
class PieChart(QWidget):
    """QPainter 自绘饼图（扇区 + 引线标签），无外部依赖。"""

    def __init__(self):
        super().__init__()
        self._items = []   # [{"name": str, "value": int}, ...]
        self.setMinimumHeight(200)

    def set_data(self, items):
        """items: [{"name": str, "value": int}, ...]"""
        self._items = [{"name": str(it.get("name", "")),
                        "value": int(it.get("value", 0))}
                       for it in (items or [])]
        self.update()

    def paintEvent(self, ev):
        if not self._items:
            t = get_current_theme()
            p = QPainter(self)
            p.setPen(QColor(t.text_muted))
            p.setFont(QFont("Microsoft YaHei UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return
        t = get_current_theme()
        total = sum(it["value"] for it in self._items)
        if total <= 0:
            p = QPainter(self)
            p.setPen(QColor(t.text_muted))
            p.setFont(QFont("Microsoft YaHei UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 饼图半径与位置
        radius = min(w * 0.3, h * 0.4, 140)
        cx = w * 0.35
        cy = h * 0.5

        start_angle = 90 * 16  # 12 点方向起始
        for i, it in enumerate(self._items):
            ratio = it["value"] / total
            span = int(ratio * 360 * 16)
            color = QColor(PIE_PALETTE[i % len(PIE_PALETTE)])
            p.setPen(QPen(QColor(t.surface), 2))
            p.setBrush(QBrush(color))
            p.drawPie(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                      start_angle, span)
            start_angle += span

        # 引线标签（右侧）
        label_x = cx + radius + 20
        label_y = cy - len(self._items) * 12
        p.setFont(QFont("Microsoft YaHei UI", 11))
        for i, it in enumerate(self._items):
            ratio = it["value"] / total
            color = QColor(PIE_PALETTE[i % len(PIE_PALETTE)])
            ly = label_y + i * 24
            # 色块
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(label_x, ly, 12, 12), 2, 2)
            # 名称
            name = it["name"] if len(it["name"]) <= 10 else it["name"][:10] + ".."
            p.setPen(QColor(t.text))
            p.drawText(QRectF(label_x + 18, ly - 2, 120, 16), Qt.AlignmentFlag.AlignVCenter, name)
            # 百分比
            pct = f"{ratio * 100:.1f}%"
            p.setPen(QColor(t.text_muted))
            p.drawText(QRectF(label_x + 145, ly - 2, 60, 16), Qt.AlignmentFlag.AlignVCenter, pct)

        p.end()
        super().paintEvent(ev)


# ======================= AreaLineChart 面积折线图 =======================
class AreaLineChart(QWidget):
    """带渐变填充的折线/曲线面积图，用于月度/年度趋势。"""

    def __init__(self):
        super().__init__()
        self._series = []   # [int, ...]  每日/每月数值（秒）
        self._labels = []   # [str, ...]  X 轴标签
        self._accent = None
        self._smooth = True  # 曲线/直线
        self._unit = "minute"  # minute / hour
        self.setMinimumHeight(160)

    def set_data(self, series, labels=None, accent: str = None,
                 smooth: bool = True, unit: str = "minute"):
        self._series = series or []
        self._labels = labels or []
        self._accent = accent
        self._smooth = smooth
        self._unit = unit
        self.setMinimumHeight(160)
        self.setMinimumWidth(max(220, len(self._series) * 8))
        self.update()

    def paintEvent(self, ev):
        if not self._series:
            t = get_current_theme()
            p = QPainter(self)
            p.setPen(QColor(t.text_muted))
            p.setFont(QFont("Microsoft YaHei UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            p.end()
            return

        t = get_current_theme()
        accent = self._accent or t.primary
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 46, 16, 14, 24
        area_w = w - pad_l - pad_r
        area_h = h - pad_t - pad_b

        # 转换单位
        divisor = 3600 if self._unit == "hour" else 60
        unit_label = "h" if self._unit == "hour" else "m"
        values = [v / divisor for v in self._series]
        maxv = max(values) if values else 1
        if maxv <= 0:
            maxv = 1

        # Y 轴刻度（3 档）
        p.setFont(QFont("Microsoft YaHei UI", 9))
        for i in range(4):
            val = maxv * i / 3
            y = pad_t + area_h - int((val / maxv) * area_h)
            p.setPen(QColor(t.text_subtle))
            p.drawText(QRectF(0, y - 8, pad_l - 6, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val:.0f}{unit_label}")
            # 网格线
            p.setPen(QPen(QColor(t.divider), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(pad_l), int(y), int(w - pad_r), int(y))

        # 构造点坐标
        n = len(values)
        if n == 0:
            p.end()
            return
        step = area_w / max(n - 1, 1)
        points = []
        for i, v in enumerate(values):
            x = pad_l + i * step
            y = pad_t + area_h - (v / maxv) * area_h
            points.append(QPointF(x, y))

        # 填充路径
        fill_path = QPainterPath()
        fill_path.moveTo(points[0].x(), pad_t + area_h)
        fill_path.lineTo(points[0].x(), points[0].y())
        if self._smooth and n > 2:
            fill_path.cubicTo(
                self._ctrl(points, 0, 1, 0.3), self._ctrl(points, 0, 1, 0.7),
                points[1])
            for i in range(1, n - 1):
                fill_path.cubicTo(
                    self._ctrl(points, i, i + 1, 0.3),
                    self._ctrl(points, i, i + 1, 0.7),
                    points[i + 1])
        else:
            for pt in points[1:]:
                fill_path.lineTo(pt.x(), pt.y())
        fill_path.lineTo(points[-1].x(), pad_t + area_h)
        fill_path.closeSubpath()

        # 渐变填充
        grad = QLinearGradient(0, pad_t, 0, pad_t + area_h)
        base_color = QColor(accent)
        base_color.setAlphaF(0.25)
        grad.setColorAt(0, base_color)
        base_color.setAlphaF(0.03)
        grad.setColorAt(1, base_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill_path)

        # 折线
        line_path = QPainterPath()
        line_path.moveTo(points[0])
        if self._smooth and n > 2:
            line_path.cubicTo(
                self._ctrl(points, 0, 1, 0.3), self._ctrl(points, 0, 1, 0.7),
                points[1])
            for i in range(1, n - 1):
                line_path.cubicTo(
                    self._ctrl(points, i, i + 1, 0.3),
                    self._ctrl(points, i, i + 1, 0.7),
                    points[i + 1])
        else:
            for pt in points[1:]:
                line_path.lineTo(pt)
        p.setPen(QPen(QColor(accent), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line_path)

        # 数据点
        for pt in points:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(accent)))
            p.drawEllipse(pt, 3, 3)

        # X 轴标签
        if self._labels:
            p.setFont(QFont("Microsoft YaHei UI", 8))
            p.setPen(QColor(t.text_subtle))
            # 根据空间决定间隔
            max_labels = area_w / 36
            step_label = max(1, math.ceil(n / max_labels))
            for i in range(0, n, step_label):
                x = pad_l + i * step
                p.drawText(QRectF(x - 18, pad_t + area_h + 4, 36, 16),
                           Qt.AlignmentFlag.AlignCenter, str(self._labels[i]))

        p.end()

    @staticmethod
    def _ctrl(pts, i, j, t):
        """计算贝塞尔控制点（真正的 Catmull-Rom 转换为三次贝塞尔）。

        P0 修复: 原实现仅做线性插值, 与注释"Catmull-Rom 近似"不符 → 平滑失效。
        此处使用标准 Catmull-Rom → Cubic Bezier 控制点公式:
            B0 = P_i
            B1 = P_i + (P_{i+1} - P_{i-1}) / 6
            B2 = P_{i+1} - (P_{i+2} - P_i) / 6
            B3 = P_{i+1}
        """
        n = len(pts)
        # 边界用 Clamped 模式: P_{-1} = P_0, P_n = P_{n-1}
        p_prev = pts[i - 1] if i > 0 else pts[i]
        p_next = pts[j] if j < n else pts[j - 1]
        p_next_next = pts[j + 1] if j + 1 < n else pts[j]
        # Catmull-Rom → Bezier 控制点
        c1 = QPointF(
            pts[i].x() + (p_next.x() - p_prev.x()) / 6.0,
            pts[i].y() + (p_next.y() - p_prev.y()) / 6.0,
        )
        c2 = QPointF(
            pts[j].x() - (p_next_next.x() - pts[i].x()) / 6.0,
            pts[j].y() - (p_next_next.y() - pts[i].y()) / 6.0,
        )
        # t 参数用于缩放控制点张度(可选), 此处不缩放, 返回 (c1, c2) 用两段调用替代
        return c1 if t < 0.5 else c2


# ======================= MonthHeatmap 月度热力图 =======================
class MonthHeatmap(QWidget):
    """月度专注时段分布热力图：X 轴 = 日期(1-31)，Y 轴 = 小时(0-23)。"""

    def __init__(self):
        super().__init__()
        self._data = {}  # {(day, hour): seconds}
        self._days_in_month = 31
        self.setMinimumHeight(280)

    def set_data(self, rows, days_in_month: int = 31):
        """rows: [{"day": int, "hour": int, "total": int}, ...]"""
        self._data = {}
        self._days_in_month = days_in_month
        for r in rows:
            self._data[(int(r["day"]), int(r["hour"]))] = int(r["total"])
        self.setMinimumHeight(max(280, days_in_month * 8 + 60))
        self.update()

    def paintEvent(self, ev):
        t = get_current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._data:
            p.setPen(QColor(t.text_muted))
            p.setFont(QFont("Microsoft YaHei UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无数据")
            p.end()
            return

        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 36, 12, 8, 20
        area_w = w - pad_l - pad_r
        area_h = h - pad_t - pad_b

        days = self._days_in_month
        hours = 24

        cell_w = area_w / days
        cell_h = area_h / hours

        # 找最大值用于颜色映射
        maxv = max(self._data.values(), default=1) or 1

        # 基色
        base_color = QColor(t.primary)

        p.setFont(QFont("Microsoft YaHei UI", 8))

        for d in range(1, days + 1):
            x = pad_l + (d - 1) * cell_w
            # 日期标签（每隔几天显示）
            if days <= 10 or d % max(1, days // 10) == 1 or d == days:
                p.setPen(QColor(t.text_subtle))
                p.drawText(QRectF(x, pad_t + area_h + 2, cell_w, 16),
                           Qt.AlignmentFlag.AlignCenter, str(d))
            for hr in range(hours):
                y = pad_t + hr * cell_h
                val = self._data.get((d, hr), 0)
                if val > 0:
                    ratio = min(1.0, val / maxv)
                    alpha = 0.2 + ratio * 0.8
                    c = QColor(base_color)
                    c.setAlphaF(alpha)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(c))
                else:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(QColor(t.surface_variant)))
                p.drawRoundedRect(QRectF(x + 0.5, y + 0.5, cell_w - 1, cell_h - 1), 2, 2)

        # Y 轴小时标签
        p.setPen(QColor(t.text_subtle))
        for hr in range(0, 24, 3):
            y = pad_t + hr * cell_h + cell_h / 2
            p.drawText(QRectF(0, y - 6, pad_l - 4, 12),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{hr:02d}")

        p.end()
        super().paintEvent(ev)
