# -*- coding: utf-8 -*-
"""数据统计模块自动化测试。

测试覆盖：
1. StatsDAO 各查询方法 — 正常场景（11 个）
2. StatsDAO 各查询方法 — 异常场景（7 个）
3. 数据统计设置项读写验证（6 个 key）
4. 时间段查询测试（9 个）
5. 打卡和打断数据测试（4 个）

BUG 修复说明（修复位置：src/database/dao.py + src/ui_qt/pages/stats_page.py）：
- BUG-1: StatsDAO.today_abandoned 原先返回 int，与 total_focus/today_focus 的 dict
  风格不一致；已修复为统一返回 {"count": N} 字典，并同步更新 stats_page.py 调用处。
- BUG-2: StatsDAO.todo_distribution 原先 SELECT 别名为 'name'，与方法签名文档中的
  'title' 不一致；已修复为返回 'title' 键，并同步更新 stats_page.py 4 处调用。
- BUG-3: StatsDAO.yearly_monthly 原先仅返回有数据的月份，无数据年份返回空列表；
  已修复为始终返回 1-12 月共 12 条记录，无数据月份 total/cnt 为 0。
"""
import datetime

import pytest

# 所有测试统一打 stats 标记
pytestmark = pytest.mark.stats


# ===================== 辅助函数 =====================

def _norm_date(d) -> datetime.date:
    """将各种日期类型统一转为 datetime.date。"""
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    if isinstance(d, str):
        return datetime.date.fromisoformat(d)
    raise TypeError(f"无法识别的日期类型: {type(d)}")


def _make_dt(date: datetime.date, hour: int = 10, minute: int = 0) -> datetime.datetime:
    """从 date 构造 datetime。"""
    return datetime.datetime(date.year, date.month, date.day, hour, minute)


def _create_focus(focus_dao, todo_id, date, hour, duration, completed=1,
                  belong_date=None):
    """快捷创建一条专注记录。

    默认显式指定 belong_date，避免午夜模式（0-4 点归属前一天）干扰测试。
    """
    start = _make_dt(date, hour)
    end = start + datetime.timedelta(seconds=duration)
    return focus_dao.create(
        todo_id=todo_id, timer_type=0, planned_duration=duration,
        actual_duration=duration, start_time=start, end_time=end,
        is_completed=completed, record_name=f"记录_{hour}点",
        belong_date=belong_date or date,
    )


# ================================================================== #
#  1. StatsDAO 正常场景测试
# ================================================================== #

def test_total_focus(stats_dao, focus_dao, todo_dao):
    """创建专注记录后验证总次数和总时长。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()

    # 3 条已完成记录
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)
    _create_focus(focus_dao, tid, today, 20, 600, completed=1)
    # 1 条未完成记录（不应计入）
    _create_focus(focus_dao, tid, today, 11, 300, completed=0)

    result = stats_dao.total_focus()
    assert result["count"] == 3
    assert result["total_seconds"] == 1500 + 1800 + 600


def test_today_focus(stats_dao, focus_dao, todo_dao):
    """验证今日专注统计。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # 今天 2 条已完成
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)
    # 昨天 1 条已完成（不应计入今日）
    _create_focus(focus_dao, tid, yesterday, 10, 600, completed=1)

    result = stats_dao.today_focus()
    assert result["count"] == 2
    assert result["total_seconds"] == 1500 + 1800


def test_today_abandoned(stats_dao, focus_dao, todo_dao):
    """验证今日放弃次数。

    BUG-1 修复验证：today_abandoned 应返回 dict {"count": N}，
    而非原先的 int。
    """
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # 今天 1 条已完成 + 2 条放弃
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 10, 600, completed=0)
    _create_focus(focus_dao, tid, today, 14, 300, completed=0)
    # 昨天的放弃记录（不应计入今日）
    _create_focus(focus_dao, tid, yesterday, 11, 400, completed=0)

    result = stats_dao.today_abandoned()
    assert isinstance(result, dict)
    assert "count" in result
    assert result["count"] == 2


def test_avg_daily_duration(stats_dao, focus_dao, todo_dao):
    """验证日均时长。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # 今天 2 条已完成：1500 + 1800 = 3300s
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)
    # 昨天 1 条已完成：900s
    _create_focus(focus_dao, tid, yesterday, 10, 900, completed=1)

    # 总时长 = 4200s，天数 = 2，日均 = 2100s
    result = stats_dao.avg_daily_duration()
    assert result == 2100


def test_hourly_range(stats_dao, focus_dao, todo_dao):
    """验证按小时统计（指定日期）。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.hourly_range(today)
    assert len(result) == 2
    hours = {int(r["hour"]): int(r["total"]) for r in result}
    assert hours[9] == 1500
    assert hours[14] == 1800


def test_daily_range(stats_dao, focus_dao, todo_dao):
    """验证日期范围每日时长。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    day1 = today - datetime.timedelta(days=2)
    day2 = today - datetime.timedelta(days=1)

    _create_focus(focus_dao, tid, day1, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, day2, 11, 1800, completed=1)
    _create_focus(focus_dao, tid, today, 12, 600, completed=1)

    result = stats_dao.daily_range(day1, today)
    assert len(result) == 3
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals[day1] == 1500
    assert totals[day2] == 1800
    assert totals[today] == 600


def test_todo_distribution(stats_dao, focus_dao, todo_dao):
    """验证按待办统计（饼图数据）。

    BUG-2 修复验证：todo_distribution 应返回 'title' 键，
    而非原先的 'name' 键。
    """
    tid1 = todo_dao.create("学习Python", timer_type=0, duration=1500)
    tid2 = todo_dao.create("写周报", timer_type=0, duration=1800)
    today = datetime.date.today()

    _create_focus(focus_dao, tid1, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid1, today, 10, 1200, completed=1)
    _create_focus(focus_dao, tid2, today, 14, 1800, completed=1)

    result = stats_dao.todo_distribution(today, today)
    assert len(result) == 2
    # 验证返回的键名是 'title' 而非 'name'
    assert "title" in result[0]
    title_map = {r["title"]: int(r["total"]) for r in result}
    assert title_map["学习Python"] == 1500 + 1200
    assert title_map["写周报"] == 1800
    # 验证 cnt 字段
    cnt_map = {r["title"]: int(r["cnt"]) for r in result}
    assert cnt_map["学习Python"] == 2
    assert cnt_map["写周报"] == 1


def test_monthly_hour_heatmap(stats_dao, focus_dao, todo_dao):
    """验证月度时段热力图。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    year_month = today.strftime("%Y-%m")

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)
    # 同一天不同小时各一条

    result = stats_dao.monthly_hour_heatmap(year_month)
    assert len(result) == 2
    for r in result:
        assert "day" in r
        assert "hour" in r
        assert "total" in r
        assert int(r["day"]) == today.day
    hours = {int(r["hour"]): int(r["total"]) for r in result}
    assert hours[9] == 1500
    assert hours[14] == 1800


def test_yearly_monthly(stats_dao, focus_dao, todo_dao):
    """验证年度月度时长。

    BUG-3 修复验证：yearly_monthly 应始终返回 12 个月的数据。
    """
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    year = today.year

    # 在当前月创建记录
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.yearly_monthly(year)
    # 应返回 12 个月
    assert len(result) == 12
    months = [int(r["month"]) for r in result]
    assert months == list(range(1, 13))
    # 当前月应有数据
    cur_month_data = next(r for r in result if int(r["month"]) == today.month)
    assert int(cur_month_data["total"]) == 1500 + 1800
    assert int(cur_month_data["cnt"]) == 2


def test_streak_days(stats_dao, focus_dao, todo_dao):
    """验证连续专注天数。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    day_before = today - datetime.timedelta(days=2)

    # 连续 3 天都有已完成记录
    _create_focus(focus_dao, tid, day_before, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, yesterday, 10, 1800, completed=1)
    _create_focus(focus_dao, tid, today, 10, 600, completed=1)

    result = stats_dao.streak_days()
    assert result == 3


def test_daily_distribution(stats_dao, focus_dao, todo_dao):
    """验证近 N 天每日时长。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, yesterday, 10, 1800, completed=1)

    result = stats_dao.daily_distribution(days=7)
    assert len(result) == 2
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals[today] == 1500
    assert totals[yesterday] == 1800


# ================================================================== #
#  2. StatsDAO 异常场景测试
# ================================================================== #

def test_total_focus_empty(stats_dao):
    """空数据库时返回 0。"""
    result = stats_dao.total_focus()
    assert result["count"] == 0
    assert result["total_seconds"] == 0


def test_today_focus_no_data(stats_dao, focus_dao, todo_dao):
    """今天无数据时返回 0。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    # 只在昨天创建记录
    _create_focus(focus_dao, tid, yesterday, 10, 1500, completed=1)

    result = stats_dao.today_focus()
    assert result["count"] == 0
    assert result["total_seconds"] == 0


def test_hourly_range_no_data(stats_dao):
    """指定日期无数据时返回空列表。"""
    future = datetime.date.today() + datetime.timedelta(days=365)
    result = stats_dao.hourly_range(future)
    assert result == []


def test_daily_range_invalid_range(stats_dao, focus_dao, todo_dao):
    """结束日期早于开始日期时返回空列表。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    _create_focus(focus_dao, tid, today, 10, 1500, completed=1)

    # 结束日期早于开始日期
    start = today
    end = today - datetime.timedelta(days=5)
    result = stats_dao.daily_range(start, end)
    assert result == []


def test_todo_distribution_no_completed(stats_dao, focus_dao, todo_dao):
    """全部未完成时不返回数据。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    # 只创建未完成记录
    _create_focus(focus_dao, tid, today, 9, 1500, completed=0)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=0)

    result = stats_dao.todo_distribution(today, today)
    assert result == []


def test_monthly_hour_heatmap_invalid_month(stats_dao, focus_dao, todo_dao):
    """无效月份格式（如 13 月）时返回空列表。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)

    # 13 月不存在
    invalid_month = f"{today.year}-13"
    result = stats_dao.monthly_hour_heatmap(invalid_month)
    assert result == []


def test_yearly_monthly_empty_year(stats_dao):
    """无数据年份返回 12 个月全 0。

    BUG-3 修复验证：原先返回空列表，修复后返回 12 条全 0 记录。
    """
    result = stats_dao.yearly_monthly(2099)
    assert len(result) == 12
    for r in result:
        assert int(r["total"]) == 0
        assert int(r["cnt"]) == 0
    months = [int(r["month"]) for r in result]
    assert months == list(range(1, 13))


# ================================================================== #
#  3. 数据统计设置项验证（6 个设置项）
# ================================================================== #

def test_settings_stats_show_wake(settings_dao):
    """stats_show_wake（显示起床打卡分布）: '1'/'0'。"""
    settings_dao.set("stats_show_wake", "1")
    assert settings_dao.get("stats_show_wake") == "1"
    settings_dao.set("stats_show_wake", "0")
    assert settings_dao.get("stats_show_wake") == "0"


def test_settings_stats_show_sleep(settings_dao):
    """stats_show_sleep（显示睡眠打卡分布）: '1'/'0'。"""
    settings_dao.set("stats_show_sleep", "1")
    assert settings_dao.get("stats_show_sleep") == "1"
    settings_dao.set("stats_show_sleep", "0")
    assert settings_dao.get("stats_show_sleep") == "0"


def test_settings_stats_show_interrupt(settings_dao):
    """stats_show_interrupt（显示月度打断原因分布）: '1'/'0'。"""
    settings_dao.set("stats_show_interrupt", "1")
    assert settings_dao.get("stats_show_interrupt") == "1"
    settings_dao.set("stats_show_interrupt", "0")
    assert settings_dao.get("stats_show_interrupt") == "0"


def test_settings_stats_trend_smooth(settings_dao):
    """stats_trend_smooth（趋势图线条）: '1'(曲线)/'0'(直线)。"""
    settings_dao.set("stats_trend_smooth", "1")
    assert settings_dao.get("stats_trend_smooth") == "1"
    settings_dao.set("stats_trend_smooth", "0")
    assert settings_dao.get("stats_trend_smooth") == "0"


def test_settings_stats_chart_unit(settings_dao):
    """stats_chart_unit（统计图单位）: 'minute'/'hour'。"""
    settings_dao.set("stats_chart_unit", "minute")
    assert settings_dao.get("stats_chart_unit") == "minute"
    settings_dao.set("stats_chart_unit", "hour")
    assert settings_dao.get("stats_chart_unit") == "hour"


def test_settings_stats_monthly_range(settings_dao):
    """stats_monthly_range（月度展示范围）: '7days'/'month'。"""
    settings_dao.set("stats_monthly_range", "7days")
    assert settings_dao.get("stats_monthly_range") == "7days"
    settings_dao.set("stats_monthly_range", "month")
    assert settings_dao.get("stats_monthly_range") == "month"


# ================================================================== #
#  4. 时间段查询测试
# ================================================================== #

def test_daily_range_today(stats_dao, focus_dao, todo_dao):
    """查询今天的范围。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.daily_range(today, today)
    assert len(result) == 1
    assert _norm_date(result[0]["belong_date"]) == today
    assert int(result[0]["total"]) == 1500 + 1800
    assert int(result[0]["cnt"]) == 2


def test_daily_range_week(stats_dao, focus_dao, todo_dao):
    """查询本周范围。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())  # 本周一
    sunday = monday + datetime.timedelta(days=6)               # 本周日

    # 在周一和今天各创建一条记录
    _create_focus(focus_dao, tid, monday, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.daily_range(monday, sunday)
    # 至少有周一和今天的数据（如果今天是周一则只有 1 条）
    assert len(result) >= 1
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals.get(monday) == 1500
    assert totals.get(today) == 1800


def test_daily_range_month(stats_dao, focus_dao, todo_dao):
    """查询本月范围。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    first_day = today.replace(day=1)

    _create_focus(focus_dao, tid, first_day, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.daily_range(first_day, today)
    assert len(result) >= 1
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals.get(first_day) == 1500
    assert totals.get(today) == 1800


def test_daily_range_custom(stats_dao, focus_dao, todo_dao):
    """自定义日期范围（起止日期）。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=3)
    end = today - datetime.timedelta(days=1)

    _create_focus(focus_dao, tid, start, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, end, 14, 1800, completed=1)
    # 范围外的数据不应出现
    _create_focus(focus_dao, tid, today, 16, 600, completed=1)

    result = stats_dao.daily_range(start, end)
    assert len(result) == 2
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals[start] == 1500
    assert totals[end] == 1800
    assert today not in totals


def test_daily_range_start_equals_end(stats_dao, focus_dao, todo_dao):
    """起止日期相同。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.daily_range(today, today)
    assert len(result) == 1
    assert int(result[0]["total"]) == 1500 + 1800
    assert int(result[0]["cnt"]) == 2


def test_daily_range_cross_month(stats_dao, focus_dao, todo_dao):
    """跨月查询。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    first_of_current_month = today.replace(day=1)
    last_of_prev_month = first_of_current_month - datetime.timedelta(days=1)

    _create_focus(focus_dao, tid, last_of_prev_month, 10, 1500, completed=1)
    _create_focus(focus_dao, tid, first_of_current_month, 14, 1800, completed=1)

    result = stats_dao.daily_range(last_of_prev_month, first_of_current_month)
    assert len(result) == 2
    totals = {_norm_date(r["belong_date"]): int(r["total"]) for r in result}
    assert totals[last_of_prev_month] == 1500
    assert totals[first_of_current_month] == 1800
    # 验证确实跨月
    assert last_of_prev_month.month != first_of_current_month.month


def test_hourly_range_today(stats_dao, focus_dao, todo_dao):
    """按小时查询今天。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()

    _create_focus(focus_dao, tid, today, 8, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 12, 1800, completed=1)
    _create_focus(focus_dao, tid, today, 18, 600, completed=1)

    result = stats_dao.hourly_range(today)
    assert len(result) == 3
    hours = {int(r["hour"]): int(r["total"]) for r in result}
    assert hours[8] == 1500
    assert hours[12] == 1800
    assert hours[18] == 600


def test_monthly_heatmap_current_month(stats_dao, focus_dao, todo_dao):
    """本月热力图。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    ym = today.strftime("%Y-%m")

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.monthly_hour_heatmap(ym)
    assert len(result) == 2
    for r in result:
        assert int(r["day"]) == today.day
    hours = {int(r["hour"]): int(r["total"]) for r in result}
    assert hours[9] == 1500
    assert hours[14] == 1800


def test_yearly_current_year(stats_dao, focus_dao, todo_dao):
    """今年年度数据。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    year = today.year

    _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    _create_focus(focus_dao, tid, today, 14, 1800, completed=1)

    result = stats_dao.yearly_monthly(year)
    assert len(result) == 12
    cur_month = next(r for r in result if int(r["month"]) == today.month)
    assert int(cur_month["total"]) == 1500 + 1800
    assert int(cur_month["cnt"]) == 2


# ================================================================== #
#  5. 打卡和打断数据测试
# ================================================================== #

def test_checkin_monthly_distribution(checkin_dao, habit_dao):
    """起床/睡眠打卡月度分布。"""
    today = datetime.date.today()
    ym = today.strftime("%Y-%m")

    # 起床打卡（type=0）: 7点和8点各一次
    checkin_dao.checkin(0, _make_dt(today, 7))
    checkin_dao.checkin(0, _make_dt(today, 8))
    # 睡眠打卡（type=1）: 22点和23点各一次
    checkin_dao.checkin(1, _make_dt(today, 22))
    checkin_dao.checkin(1, _make_dt(today, 23))

    # 验证起床打卡分布
    wake_result = habit_dao.monthly_distribution(ym, habit_type=0)
    assert len(wake_result) == 2
    wake_hours = {int(r["hour"]): int(r["cnt"]) for r in wake_result}
    assert wake_hours[7] == 1
    assert wake_hours[8] == 1

    # 验证睡眠打卡分布
    sleep_result = habit_dao.monthly_distribution(ym, habit_type=1)
    assert len(sleep_result) == 2
    sleep_hours = {int(r["hour"]): int(r["cnt"]) for r in sleep_result}
    assert sleep_hours[22] == 1
    assert sleep_hours[23] == 1


def test_interrupt_monthly_distribution(stats_dao, focus_dao, interrupt_dao,
                                         todo_dao):
    """打断原因月度分布。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    ym = today.strftime("%Y-%m")

    # 创建专注记录
    fr_id = _create_focus(focus_dao, tid, today, 9, 1500, completed=1)

    # 创建打断详情
    interrupt_dao.create(fr_id, "微信", _make_dt(today, 9, 10))
    interrupt_dao.create(fr_id, "微信", _make_dt(today, 9, 20))
    interrupt_dao.create(fr_id, "浏览器", _make_dt(today, 9, 30))

    result = interrupt_dao.monthly_distribution(ym)
    assert len(result) == 2
    # 按 cnt 降序排列，微信(2) 应在浏览器(1) 之前
    proc_cnt = {r["process_name"]: int(r["cnt"]) for r in result}
    assert proc_cnt["微信"] == 2
    assert proc_cnt["浏览器"] == 1
    # 验证排序：第一条 cnt >= 第二条
    assert int(result[0]["cnt"]) >= int(result[1]["cnt"])


def test_checkin_empty_month(checkin_dao, habit_dao):
    """空月份打卡分布。"""
    # 查询一个不存在的月份
    result = habit_dao.monthly_distribution("2099-01", habit_type=0)
    assert result == []

    result = habit_dao.monthly_distribution("2099-01", habit_type=1)
    assert result == []


def test_interrupt_empty_month(interrupt_dao, focus_dao, todo_dao):
    """空月份打断分布。"""
    tid = todo_dao.create("学习Python", timer_type=0, duration=1500)
    today = datetime.date.today()
    # 在当前月创建数据
    fr_id = _create_focus(focus_dao, tid, today, 9, 1500, completed=1)
    interrupt_dao.create(fr_id, "微信", _make_dt(today, 9, 10))

    # 查询一个不存在的月份
    result = interrupt_dao.monthly_distribution("2099-01")
    assert result == []
