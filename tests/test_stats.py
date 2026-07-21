"""统计图表回归测试（PyQt6 offscreen）。"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def _qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_fmt_minutes():
    from src.ui_qt.charts import fmt_minutes
    assert fmt_minutes(0) == "0 分钟"
    assert fmt_minutes(60) == "1 分钟"
    assert fmt_minutes(3600) == "1 小时 0 分"
    assert fmt_minutes(7200) == "2 小时 0 分"


def test_statcard_construction():
    _qapp()
    from src.ui_qt.charts import StatCard
    card = StatCard("累计专注", "100 分钟", "#8CC44A")
    assert card is not None


def test_barchart_set_data():
    _qapp()
    from src.ui_qt.charts import BarChart
    chart = BarChart()
    chart.set_data([{"label": "01/01", "value": 100},
                     {"label": "01/02", "value": 200}], "#8CC44A")
    assert len(chart._items) == 2


def test_trendchart_set_data():
    _qapp()
    from src.ui_qt.charts import TrendChart
    chart = TrendChart()
    chart.set_data([100, 200, 50, 0, 300], "#8CC44A")
    assert len(chart._series) == 5


def test_heatmap_set_data():
    _qapp()
    import datetime
    from src.ui_qt.charts import Heatmap
    hm = Heatmap()
    today = datetime.date.today()
    data = [{"belong_date": today - datetime.timedelta(days=i),
             "total": 1800} for i in range(10)]
    hm.set_data(data, "#8CC44A")
    assert hm._lay.count() == 30, "热力图应有 30 个格子（含空数据填充）"
