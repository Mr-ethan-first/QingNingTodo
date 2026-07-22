# -*- coding: utf-8 -*-
"""专注计时模块自动化测试。

覆盖范围：
- FocusRecordDAO 基础 CRUD（创建/未完成记录/列表/时间倒序）
- FocusRecordDAO 午夜模式（_belong_date：凌晨 0-4 点归属前一天，
  4 点整归属当天）
- FocusRecordDAO 异常场景（todo_id 为 None、负时长）
- InterruptDetailDAO 关联查询（创建/列表/按专注记录筛选）

使用 conftest.py 提供的 db / focus_dao / interrupt_dao fixtures，
每个测试自动使用独立的临时数据库，互不干扰。
"""
import datetime

import pytest


# ===================== FocusRecordDAO 测试 =====================

@pytest.mark.focus
def test_create_focus_record(focus_dao):
    """创建专注记录，验证返回 ID > 0 且默认完成。"""
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None,
        timer_type=0,
        planned_duration=1500,
        actual_duration=1500,
        start_time=start,
        end_time=end,
        record_name="早晨专注",
    )
    assert rid > 0

    rows = focus_dao.list_recent()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == rid
    assert row["timer_type"] == 0
    assert row["planned_duration"] == 1500
    assert row["actual_duration"] == 1500
    assert row["is_completed"] == 1  # 默认完成
    assert row["record_name"] == "早晨专注"


@pytest.mark.focus
def test_create_uncompleted_record(focus_dao):
    """创建未完成记录（is_completed=0），验证字段正确。"""
    start = datetime.datetime(2026, 7, 21, 10, 0, 0)
    end = start + datetime.timedelta(seconds=300)
    rid = focus_dao.create(
        todo_id=None,
        timer_type=1,
        planned_duration=1800,
        actual_duration=300,
        start_time=start,
        end_time=end,
        is_completed=0,
        interrupt_reason="微信消息打扰",
        note="被打断",
    )
    assert rid > 0

    rows = focus_dao.list_recent()
    assert len(rows) == 1
    row = rows[0]
    assert row["is_completed"] == 0
    assert row["actual_duration"] == 300
    assert row["interrupt_reason"] == "微信消息打扰"
    assert row["note"] == "被打断"


@pytest.mark.focus
def test_list_recent(focus_dao):
    """创建多条后按时间倒序返回（最新的在最前）。"""
    base = datetime.datetime(2026, 7, 21, 9, 0, 0)
    ids = []
    for i in range(5):
        start = base + datetime.timedelta(hours=i)
        end = start + datetime.timedelta(seconds=1500)
        rid = focus_dao.create(
            todo_id=None, timer_type=0, planned_duration=1500,
            actual_duration=1500, start_time=start, end_time=end,
            record_name=f"专注_{i}",
        )
        ids.append(rid)

    rows = focus_dao.list_recent()
    assert len(rows) == 5
    # 倒序：最后创建的（start_time 最大）在最前
    for i in range(len(rows) - 1):
        assert rows[i]["start_time"] >= rows[i + 1]["start_time"]
    # 第一条应是最后创建的
    assert rows[0]["id"] == ids[-1]
    # 最后一条应是第一个创建的
    assert rows[-1]["id"] == ids[0]


@pytest.mark.focus
def test_list_recent_limit(focus_dao):
    """list_recent 支持 limit 参数。"""
    base = datetime.datetime(2026, 7, 21, 9, 0, 0)
    for i in range(10):
        start = base + datetime.timedelta(hours=i)
        end = start + datetime.timedelta(seconds=1500)
        focus_dao.create(
            todo_id=None, timer_type=0, planned_duration=1500,
            actual_duration=1500, start_time=start, end_time=end,
        )
    rows = focus_dao.list_recent(limit=3)
    assert len(rows) == 3


@pytest.mark.focus
def test_belong_date_normal(focus_dao):
    """正常时段（4:00 及之后）归属当天。"""
    from src.database.dao import FocusRecordDAO

    # 上午 9 点
    dt = datetime.datetime(2026, 7, 21, 9, 0, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 21)

    # 中午 12 点
    dt = datetime.datetime(2026, 7, 21, 12, 0, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 21)

    # 晚上 23:59
    dt = datetime.datetime(2026, 7, 21, 23, 59, 59)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 21)


@pytest.mark.focus
def test_belong_date_midnight(focus_dao):
    """凌晨 0-4 点（不含 4 点）归属前一天（午夜模式）。"""
    from src.database.dao import FocusRecordDAO

    # 凌晨 0 点
    dt = datetime.datetime(2026, 7, 21, 0, 0, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 20)

    # 凌晨 1 点
    dt = datetime.datetime(2026, 7, 21, 1, 30, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 20)

    # 凌晨 3:59
    dt = datetime.datetime(2026, 7, 21, 3, 59, 59)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 20)


@pytest.mark.focus
def test_belong_date_4am(focus_dao):
    """4 点整归属当天（午夜模式边界）。"""
    from src.database.dao import FocusRecordDAO

    # 4 点整
    dt = datetime.datetime(2026, 7, 21, 4, 0, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 21)

    # 4 点 01 分
    dt = datetime.datetime(2026, 7, 21, 4, 1, 0)
    assert FocusRecordDAO._belong_date(dt) == datetime.date(2026, 7, 21)


@pytest.mark.focus
def test_belong_date_applied_on_create(focus_dao):
    """创建专注记录时，belong_date 应根据 start_time 自动计算（午夜模式）。"""
    # 凌晨 2 点开始 → belong_date 应为前一天
    start = datetime.datetime(2026, 7, 21, 2, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start, end_time=end,
    )
    rows = focus_dao.list_recent()
    assert len(rows) == 1
    assert rows[0]["belong_date"] == datetime.date(2026, 7, 20)

    # 上午 10 点开始 → belong_date 当天
    start = datetime.datetime(2026, 7, 21, 10, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid2 = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start, end_time=end,
    )
    rows = focus_dao.list_recent()
    # 最新的在前
    assert rows[0]["id"] == rid2
    assert rows[0]["belong_date"] == datetime.date(2026, 7, 21)


# ===================== FocusRecordDAO 异常测试 =====================

@pytest.mark.focus
def test_create_with_null_todo_id(focus_dao):
    """todo_id 为 None 不崩溃（schema 允许 todo_id NULL）。"""
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None,
        timer_type=0,
        planned_duration=1500,
        actual_duration=1500,
        start_time=start,
        end_time=end,
    )
    assert rid > 0
    row = focus_dao.list_recent()[0]
    assert row["todo_id"] is None


@pytest.mark.focus
def test_create_negative_duration(focus_dao):
    """负时长不崩溃（或正确处理）。

    schema 中 planned_duration / actual_duration 仅有 NOT NULL DEFAULT 0
    约束，无 CHECK 防止负值，因此负数会被原样存入。
    本测试验证不抛异常，且能正常读取。
    """
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None,
        timer_type=0,
        planned_duration=-100,
        actual_duration=-50,
        start_time=start,
        end_time=end,
    )
    assert rid > 0
    row = focus_dao.list_recent()[0]
    # 负值被原样存入（DAO 未做防负处理）
    assert row["planned_duration"] == -100
    assert row["actual_duration"] == -50


# ===================== 专注记录统计关联测试 =====================

@pytest.mark.focus
def test_focus_with_interrupt(focus_dao, interrupt_dao):
    """创建专注记录 + 打断详情，验证关联查询。"""
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start, end_time=end,
    )

    occurred = start + datetime.timedelta(seconds=300)
    iid = interrupt_dao.create(
        focus_record_id=rid,
        process_name="WeChat.exe",
        occurred_at=occurred,
    )
    assert iid > 0

    interrupts = interrupt_dao.list_by_focus(rid)
    assert len(interrupts) == 1
    assert interrupts[0]["focus_record_id"] == rid
    assert interrupts[0]["process_name"] == "WeChat.exe"
    assert str(interrupts[0]["occurred_at"])[:19] == occurred.strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.focus
def test_focus_multiple_interrupts(focus_dao, interrupt_dao):
    """一条专注记录多条打断详情，验证全部返回且按时间排序。"""
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start, end_time=end,
    )

    # 添加 3 条打断
    interrupt_dao.create(rid, "WeChat.exe", start + datetime.timedelta(seconds=100))
    interrupt_dao.create(rid, "QQ.exe", start + datetime.timedelta(seconds=300))
    interrupt_dao.create(rid, "DingTalk.exe", start + datetime.timedelta(seconds=500))

    interrupts = interrupt_dao.list_by_focus(rid)
    assert len(interrupts) == 3
    # 按 occurred_at 升序排列
    for i in range(len(interrupts) - 1):
        assert interrupts[i]["occurred_at"] <= interrupts[i + 1]["occurred_at"]
    names = {it["process_name"] for it in interrupts}
    assert names == {"WeChat.exe", "QQ.exe", "DingTalk.exe"}


@pytest.mark.focus
def test_interrupt_list_by_focus(focus_dao, interrupt_dao):
    """按专注记录查询打断列表：只返回指定记录的打断。"""
    # 创建两条专注记录
    start1 = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end1 = start1 + datetime.timedelta(seconds=1500)
    rid1 = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start1, end_time=end1,
    )
    start2 = datetime.datetime(2026, 7, 21, 14, 0, 0)
    end2 = start2 + datetime.timedelta(seconds=1500)
    rid2 = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start2, end_time=end2,
    )

    # rid1 关联 2 条打断，rid2 关联 1 条打断
    interrupt_dao.create(rid1, "WeChat.exe", start1 + datetime.timedelta(seconds=100))
    interrupt_dao.create(rid1, "QQ.exe", start1 + datetime.timedelta(seconds=200))
    interrupt_dao.create(rid2, "DingTalk.exe", start2 + datetime.timedelta(seconds=100))

    r1_interrupts = interrupt_dao.list_by_focus(rid1)
    r2_interrupts = interrupt_dao.list_by_focus(rid2)
    assert len(r1_interrupts) == 2
    assert len(r2_interrupts) == 1
    # 验证隔离：r1 的打断都是 rid1
    assert all(it["focus_record_id"] == rid1 for it in r1_interrupts)
    assert all(it["focus_record_id"] == rid2 for it in r2_interrupts)
    # 验证 r2 的打断进程名
    assert r2_interrupts[0]["process_name"] == "DingTalk.exe"


@pytest.mark.focus
def test_interrupt_list_by_focus_empty(focus_dao, interrupt_dao):
    """查询没有打断的专注记录返回空列表。"""
    start = datetime.datetime(2026, 7, 21, 9, 0, 0)
    end = start + datetime.timedelta(seconds=1500)
    rid = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start, end_time=end,
    )
    interrupts = interrupt_dao.list_by_focus(rid)
    assert interrupts == []
    assert len(interrupts) == 0


@pytest.mark.focus
def test_interrupt_monthly_distribution(focus_dao, interrupt_dao):
    """monthly_distribution 月度打断原因分布查询。"""
    # 创建 2 条专注记录，分别在 2026-07 和 2026-06
    start1 = datetime.datetime(2026, 7, 15, 9, 0, 0)
    end1 = start1 + datetime.timedelta(seconds=1500)
    rid1 = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start1, end_time=end1,
    )
    start2 = datetime.datetime(2026, 6, 10, 14, 0, 0)
    end2 = start2 + datetime.timedelta(seconds=1500)
    rid2 = focus_dao.create(
        todo_id=None, timer_type=0, planned_duration=1500,
        actual_duration=1500, start_time=start2, end_time=end2,
    )

    # 7 月：WeChat 2 次，QQ 1 次
    interrupt_dao.create(rid1, "WeChat.exe", start1 + datetime.timedelta(seconds=100))
    interrupt_dao.create(rid1, "WeChat.exe", start1 + datetime.timedelta(seconds=200))
    interrupt_dao.create(rid1, "QQ.exe", start1 + datetime.timedelta(seconds=300))
    # 6 月：DingTalk 1 次
    interrupt_dao.create(rid2, "DingTalk.exe", start2 + datetime.timedelta(seconds=100))

    july = interrupt_dao.monthly_distribution("2026-07")
    assert len(july) == 2  # 2 种进程
    # 按次数倒序
    july_dict = {row["process_name"]: row["cnt"] for row in july}
    assert july_dict["WeChat.exe"] == 2
    assert july_dict["QQ.exe"] == 1

    june = interrupt_dao.monthly_distribution("2026-06")
    assert len(june) == 1
    assert june[0]["process_name"] == "DingTalk.exe"
    assert june[0]["cnt"] == 1
