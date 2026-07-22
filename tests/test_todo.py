# -*- coding: utf-8 -*-
"""待办清单模块自动化测试。

覆盖范围：
- TodoDAO 基础 CRUD（创建/查询/列表/更新/完成/删除）
- TodoDAO 边界场景（空标题、超长标题、不存在的ID）
- TodoGroupDAO CRUD
- TodoDAO 特殊类型（养习惯、定目标、背景图、提醒时间、
  完成后隐藏、学霸模式豁免、自定义休息时长）

使用 conftest.py 提供的 db / todo_dao / group_dao fixtures，
每个测试自动使用独立的临时数据库，互不干扰。
"""
import datetime

import pytest


# ===================== TodoDAO CRUD 测试 =====================

@pytest.mark.todo
def test_create_todo(todo_dao):
    """创建待办，验证返回 ID > 0。"""
    tid = todo_dao.create("写单元测试")
    assert tid is not None
    assert tid > 0


@pytest.mark.todo
def test_create_todo_with_all_fields(todo_dao, group_dao):
    """创建带所有字段的待办，验证读取后字段一致。"""
    gid = group_dao.create("工作", color="#FF5722")
    remind = datetime.datetime(2026, 7, 21, 9, 30, 0)
    tid = todo_dao.create(
        title="完成需求文档",
        timer_type=1,
        duration=1800,
        break_duration=300,
        loop_count=3,
        priority=2,
        repeat_type=1,
        repeat_rule="daily",
        remind_time=remind,
        group_id=gid,
        background_path="/path/to/bg.png",
        type=0,
        hide_after_complete=1,
        is_amway_mode_exempted=1,
        custom_break_duration=600,
        habit_target="每天阅读30分钟",
        habit_unit="分钟",
    )
    assert tid > 0

    row = todo_dao.get(tid)
    assert row is not None
    assert row["title"] == "完成需求文档"
    assert row["timer_type"] == 1
    assert row["duration"] == 1800
    assert row["break_duration"] == 300
    assert row["loop_count"] == 3
    assert row["priority"] == 2
    assert row["repeat_type"] == 1
    assert row["repeat_rule"] == "daily"
    assert row["group_id"] == gid
    assert row["background_path"] == "/path/to/bg.png"
    assert row["type"] == 0
    assert row["hide_after_complete"] == 1
    assert row["is_amway_mode_exempted"] == 1
    assert row["custom_break_duration"] == 600
    assert row["habit_target"] == "每天阅读30分钟"
    assert row["habit_unit"] == "分钟"
    # remind_time 在 SQLite 中以 TIMESTAMP 形式存储，比较时只看年月日时分秒
    assert row["remind_time"] is not None
    assert str(row["remind_time"])[:19] == remind.strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.todo
def test_get_todo(todo_dao):
    """创建后获取，验证关键字段正确。"""
    tid = todo_dao.create("买牛奶", timer_type=0, duration=600, priority=1)
    row = todo_dao.get(tid)
    assert row is not None
    assert row["id"] == tid
    assert row["title"] == "买牛奶"
    assert row["timer_type"] == 0
    assert row["duration"] == 600
    assert row["priority"] == 1
    assert row["status"] == 0  # 默认未完成


@pytest.mark.todo
def test_get_todo_not_exist(todo_dao):
    """获取不存在的 ID 返回 None。"""
    row = todo_dao.get(999999)
    assert row is None


@pytest.mark.todo
def test_list_todos(todo_dao):
    """创建多条后列表数量正确。"""
    assert len(todo_dao.list()) == 0
    todo_dao.create("任务A")
    todo_dao.create("任务B")
    todo_dao.create("任务C")
    todos = todo_dao.list()
    assert len(todos) == 3
    titles = {t["title"] for t in todos}
    assert titles == {"任务A", "任务B", "任务C"}


@pytest.mark.todo
def test_list_todos_by_status(todo_dao):
    """按状态筛选：未完成 status=0，已完成 status=1。"""
    t1 = todo_dao.create("未完成1")
    t2 = todo_dao.create("未完成2")
    t3 = todo_dao.create("已完成1")
    todo_dao.complete(t3)

    pending = todo_dao.list(status=0)
    done = todo_dao.list(status=1)
    assert len(pending) == 2
    assert len(done) == 1
    assert done[0]["id"] == t3
    assert all(t["status"] == 0 for t in pending)
    assert all(t["status"] == 1 for t in done)


@pytest.mark.todo
def test_list_todos_by_group(todo_dao, group_dao):
    """按分组筛选。"""
    g1 = group_dao.create("工作")
    g2 = group_dao.create("生活")
    todo_dao.create("任务1", group_id=g1)
    todo_dao.create("任务2", group_id=g1)
    todo_dao.create("任务3", group_id=g2)
    todo_dao.create("任务4")  # 无分组

    work = todo_dao.list(group_id=g1)
    life = todo_dao.list(group_id=g2)
    assert len(work) == 2
    assert len(life) == 1
    assert all(t["group_id"] == g1 for t in work)
    assert all(t["group_id"] == g2 for t in life)


@pytest.mark.todo
def test_update_todo(todo_dao):
    """更新标题/优先级等字段。"""
    tid = todo_dao.create("旧标题", priority=0, duration=1500)
    affected = todo_dao.update(tid, title="新标题", priority=3, duration=3000)
    assert affected > 0

    row = todo_dao.get(tid)
    assert row["title"] == "新标题"
    assert row["priority"] == 3
    assert row["duration"] == 3000
    # 未更新字段保持原值
    assert row["timer_type"] == 0


@pytest.mark.todo
def test_complete_todo(todo_dao):
    """标记完成，验证 status=1 且 completed_at 不为空。"""
    tid = todo_dao.create("待完成任务")
    assert todo_dao.get(tid)["status"] == 0
    assert todo_dao.get(tid)["completed_at"] is None

    affected = todo_dao.complete(tid)
    assert affected > 0

    row = todo_dao.get(tid)
    assert row["status"] == 1
    assert row["completed_at"] is not None


@pytest.mark.todo
def test_delete_todo(todo_dao):
    """删除后 list 不包含该待办。"""
    tid = todo_dao.create("将被删除")
    assert todo_dao.get(tid) is not None

    affected = todo_dao.delete(tid)
    assert affected > 0

    assert todo_dao.get(tid) is None
    todos = todo_dao.list()
    assert all(t["id"] != tid for t in todos)


@pytest.mark.todo
def test_create_todo_empty_title(todo_dao):
    """空标题不崩溃。

    schema 中 title 为 VARCHAR(255) NOT NULL，
    NOT NULL 仅约束 NULL，不约束空字符串，因此空串应可写入。
    """
    tid = todo_dao.create("")
    assert tid > 0
    row = todo_dao.get(tid)
    assert row["title"] == ""


@pytest.mark.todo
def test_create_todo_long_title(todo_dao):
    """超长标题（255 字符）应能正常写入。"""
    long_title = "A" * 255
    tid = todo_dao.create(long_title)
    assert tid > 0
    row = todo_dao.get(tid)
    assert row["title"] == long_title
    assert len(row["title"]) == 255


# ===================== TodoGroupDAO CRUD 测试 =====================

@pytest.mark.todo
def test_create_group(group_dao):
    """创建分组，验证返回 ID > 0。"""
    gid = group_dao.create("学习", color="#8CC44A")
    assert gid > 0


@pytest.mark.todo
def test_list_groups(group_dao):
    """列表正确返回已创建的分组。"""
    assert len(group_dao.list()) == 0
    group_dao.create("工作", color="#FF5722")
    group_dao.create("生活", color="#03A9F4")
    groups = group_dao.list()
    assert len(groups) == 2
    names = {g["name"] for g in groups}
    assert names == {"工作", "生活"}


@pytest.mark.todo
def test_update_group(group_dao):
    """更新名称和颜色。"""
    gid = group_dao.create("旧名称", color="#000000")
    affected = group_dao.update(gid, "新名称", "#FFFFFF")
    assert affected > 0

    groups = group_dao.list()
    target = next(g for g in groups if g["id"] == gid)
    assert target["name"] == "新名称"
    assert target["color"] == "#FFFFFF"


@pytest.mark.todo
def test_delete_group(group_dao):
    """删除分组后列表不再包含。"""
    gid = group_dao.create("将被删除", color="#123456")
    assert len(group_dao.list()) == 1

    affected = group_dao.delete(gid)
    assert affected > 0
    assert len(group_dao.list()) == 0


# ===================== TodoDAO 特殊类型测试 =====================

@pytest.mark.todo
def test_create_habit_todo(todo_dao):
    """创建养习惯类型（type=1）带 habit_target 和 habit_unit。"""
    tid = todo_dao.create(
        title="每日读书",
        type=1,
        habit_target="30分钟",
        habit_unit="分钟",
    )
    assert tid > 0
    row = todo_dao.get(tid)
    assert row["type"] == 1
    assert row["habit_target"] == "30分钟"
    assert row["habit_unit"] == "分钟"


@pytest.mark.todo
def test_create_goal_todo(todo_dao):
    """创建定目标类型（type=2）。"""
    tid = todo_dao.create(title="本月读完3本书", type=2)
    assert tid > 0
    row = todo_dao.get(tid)
    assert row["type"] == 2


@pytest.mark.todo
def test_todo_with_background(todo_dao):
    """设置背景图路径。"""
    bg = "/images/backgrounds/todo_001.png"
    tid = todo_dao.create(title="带背景的任务", background_path=bg)
    row = todo_dao.get(tid)
    assert row["background_path"] == bg


@pytest.mark.todo
def test_todo_with_remind_time(todo_dao):
    """设置提醒时间。"""
    remind = datetime.datetime(2026, 8, 1, 8, 0, 0)
    tid = todo_dao.create(title="带提醒的任务", remind_time=remind)
    row = todo_dao.get(tid)
    assert row["remind_time"] is not None
    assert str(row["remind_time"])[:19] == remind.strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.todo
def test_todo_hide_after_complete(todo_dao):
    """完成后隐藏标志。"""
    tid = todo_dao.create(title="隐藏任务", hide_after_complete=1)
    row = todo_dao.get(tid)
    assert row["hide_after_complete"] == 1

    # 默认值应为 0
    tid2 = todo_dao.create(title="不隐藏任务")
    row2 = todo_dao.get(tid2)
    assert row2["hide_after_complete"] == 0


@pytest.mark.todo
def test_todo_amway_exempted(todo_dao):
    """学霸模式豁免标志。"""
    tid = todo_dao.create(title="豁免任务", is_amway_mode_exempted=1)
    row = todo_dao.get(tid)
    assert row["is_amway_mode_exempted"] == 1

    # 默认值应为 0
    tid2 = todo_dao.create(title="不豁免任务")
    row2 = todo_dao.get(tid2)
    assert row2["is_amway_mode_exempted"] == 0


@pytest.mark.todo
def test_todo_custom_break(todo_dao):
    """自定义休息时长。"""
    tid = todo_dao.create(title="自定义休息", custom_break_duration=900)
    row = todo_dao.get(tid)
    assert row["custom_break_duration"] == 900

    # 未设置时为 NULL
    tid2 = todo_dao.create(title="默认休息")
    row2 = todo_dao.get(tid2)
    assert row2["custom_break_duration"] is None
