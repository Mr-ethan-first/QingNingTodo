# -*- coding: utf-8 -*-
"""设置页面与 DAO 层基础自动化测试。

覆盖范围：
- SettingsDAO: 设置项 CRUD 与默认值
- DEFAULT_SETTINGS: schema.py 中 26 个默认设置项验证
- GoalDAO: 时长目标与长期目标
- FuturePlanDAO: 未来计划 CRUD
- AchievementDAO: 成就徽章列表/解锁/评估
- WhitelistDAO: 专注白名单 CRUD
- LockScheduleDAO: 定时锁屏 CRUD
- WhiteNoiseDAO: 白噪音列表/添加/删除
- UserDAO: 用户信息读取与昵称更新
- HabitCheckinDAO: 习惯打卡与查重
- CheckinDAO: 起床/睡眠/补卡打卡
- AppConfig: 配置目录/后端切换/JSON 结构

每个测试自动使用独立的临时数据库（conftest._isolate_home），
默认种子数据包含：1 个用户(nickname="我")、26 条默认设置、
30 条内置白噪音、6 个默认成就徽章。
"""
import datetime
import json
import os

import pytest

# 模块级标记：所有测试都属于 settings 模块
pytestmark = pytest.mark.settings


# ===================== SettingsDAO 测试 =====================

class TestSettingsDAO:
    """SettingsDAO 的 set/get/all 基础功能。"""

    def test_set_and_get(self, settings_dao):
        """设置值后能正确读取。"""
        settings_dao.set("test_key_unique", "test_value")
        assert settings_dao.get("test_key_unique") == "test_value"

    def test_get_default(self, settings_dao):
        """读取不存在的 key 返回默认值。"""
        assert settings_dao.get("nonexistent_key_xyz", "default_val") == "default_val"

    def test_get_none_default(self, settings_dao):
        """读取不存在的 key 默认值为 None。"""
        assert settings_dao.get("nonexistent_key_xyz") is None

    def test_set_overwrite(self, settings_dao):
        """同一 key 设置两次，值为最后一次。

        注意：SQLite 后端将 ``INSERT ... ON DUPLICATE KEY UPDATE`` 转换为
        ``INSERT OR REPLACE``，替换时旧行被删除、新行插入，``id`` 会变化，
        但 ``(user_id, setting_key)`` 唯一键不变，功能等价。
        """
        settings_dao.set("overwrite_key", "value1")
        settings_dao.set("overwrite_key", "value2")
        assert settings_dao.get("overwrite_key") == "value2"

    def test_all(self, settings_dao):
        """设置多个 key 后 all() 返回全部。"""
        settings_dao.set("all_key1", "val1")
        settings_dao.set("all_key2", "val2")
        settings_dao.set("all_key3", "val3")
        all_settings = settings_dao.all()
        # 26 个默认设置 + 3 个新增 = 至少 29
        assert len(all_settings) >= 29
        assert all_settings["all_key1"] == "val1"
        assert all_settings["all_key2"] == "val2"
        assert all_settings["all_key3"] == "val3"

    def test_set_empty_value(self, settings_dao):
        """设置空字符串。"""
        settings_dao.set("empty_key", "")
        assert settings_dao.get("empty_key") == ""

    def test_set_special_chars(self, settings_dao):
        """设置特殊字符值。"""
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~ 中文 emoji 🎉"
        settings_dao.set("special_key", special)
        assert settings_dao.get("special_key") == special


# ===================== 默认设置验证 =====================

class TestDefaultSettings:
    """验证 schema.py 中 DEFAULT_SETTINGS 的 26 个默认设置项。"""

    def test_default_settings_exist(self, settings_dao):
        """验证 26 个默认设置项都存在且值正确。"""
        all_settings = settings_dao.all()
        expected = {
            "default_focus_duration": "1500",
            "default_break_duration": "300",
            "focus_motto": "专注是成功的基石",
            "focus_complete_sound": "default",
            "auto_switch_stopwatch": "false",
            "max_pause_minutes": "3",
            "ask_before_break": "true",
            "enable_focus_guard": "true",
            "strict_mode": "false",
            "fixed_sort": "false",
            "no_strikethrough": "false",
            "remember_list_expand": "true",
            "enable_search": "true",
            "midnight_shift": "false",
            "habit_reminder_time": "20:00",
            "trend_line_style": "curve",
            "chart_unit": "minutes",
            "monthly_display_range": "7",
            "theme_color": "#8CC44A",
            "app_background": "",
            "background_music_path": "",
            "bg_music_enabled": "false",
            "auto_play_on_start": "false",
            "auto_start": "false",
            "shortcut_key": "Ctrl+Shift+A",
            "confirm_on_close": "true",
        }
        assert len(expected) == 26
        for key, value in expected.items():
            assert key in all_settings, f"缺少默认设置项: {key}"
            assert all_settings[key] == value, (
                f"设置项 {key} 值不正确: 期望 {value!r}, 实际 {all_settings[key]!r}"
            )


# ===================== GoalDAO 测试 =====================

class TestGoalDAO:
    """GoalDAO 的时长目标 upsert、长期目标创建与删除。"""

    def test_upsert_duration_goal(self, goal_dao):
        """插入时长目标。"""
        gid = goal_dao.upsert_duration_goal(1, 3600)
        assert gid > 0
        goals = goal_dao.list()
        assert len(goals) == 1
        assert goals[0]["goal_type"] == 1
        assert goals[0]["target_duration"] == 3600

    def test_upsert_duration_goal_update(self, goal_dao):
        """再次 upsert 更新同一目标（ID 不变）。"""
        gid1 = goal_dao.upsert_duration_goal(1, 3600)
        gid2 = goal_dao.upsert_duration_goal(1, 7200)
        assert gid1 == gid2  # 同一目标 ID
        goals = goal_dao.list()
        assert len(goals) == 1
        assert goals[0]["target_duration"] == 7200

    def test_create_long_term(self, goal_dao):
        """创建长期目标。"""
        deadline = datetime.datetime(2025, 12, 31, 23, 59, 59)
        gid = goal_dao.create_long_term("学会Python", deadline)
        assert gid > 0
        goals = goal_dao.list()
        assert len(goals) == 1
        assert goals[0]["title"] == "学会Python"
        assert goals[0]["goal_type"] == 3

    def test_list_goals(self, goal_dao):
        """列表正确。"""
        goal_dao.upsert_duration_goal(1, 3600)
        goal_dao.upsert_duration_goal(2, 7200)
        goal_dao.create_long_term("目标1", datetime.datetime(2025, 12, 31))
        goals = goal_dao.list()
        assert len(goals) == 3

    def test_delete_goal(self, goal_dao):
        """删除后不存在。"""
        gid = goal_dao.upsert_duration_goal(1, 3600)
        affected = goal_dao.delete(gid)
        assert affected == 1
        goals = goal_dao.list()
        assert len(goals) == 0


# ===================== FuturePlanDAO 测试 =====================

class TestFuturePlanDAO:
    """FuturePlanDAO 的 CRUD 与过去日期兼容性。"""

    def test_create_plan(self, plan_dao):
        """创建未来计划。"""
        pid = plan_dao.create("计划1", datetime.date(2025, 12, 31))
        assert pid > 0
        plans = plan_dao.list()
        assert len(plans) == 1
        assert plans[0]["title"] == "计划1"
        assert plans[0]["target_date"] == datetime.date(2025, 12, 31)

    def test_list_plans(self, plan_dao):
        """列表正确，按 target_date 升序。"""
        plan_dao.create("计划A", datetime.date(2025, 12, 31))
        plan_dao.create("计划B", datetime.date(2026, 1, 15))
        plan_dao.create("计划C", datetime.date(2025, 6, 1))
        plans = plan_dao.list()
        assert len(plans) == 3
        assert plans[0]["target_date"] == datetime.date(2025, 6, 1)
        assert plans[1]["target_date"] == datetime.date(2025, 12, 31)
        assert plans[2]["target_date"] == datetime.date(2026, 1, 15)

    def test_update_plan(self, plan_dao):
        """更新标题和日期。"""
        pid = plan_dao.create("原计划", datetime.date(2025, 12, 31), "备注1")
        affected = plan_dao.update(pid, "新计划", datetime.date(2026, 1, 15), "备注2")
        assert affected == 1
        plans = plan_dao.list()
        assert plans[0]["title"] == "新计划"
        assert plans[0]["target_date"] == datetime.date(2026, 1, 15)
        assert plans[0]["remark"] == "备注2"

    def test_delete_plan(self, plan_dao):
        """删除未来计划。"""
        pid = plan_dao.create("计划1", datetime.date(2025, 12, 31))
        affected = plan_dao.delete(pid)
        assert affected == 1
        plans = plan_dao.list()
        assert len(plans) == 0

    def test_create_plan_past_date(self, plan_dao):
        """过去日期不崩溃。"""
        pid = plan_dao.create("过去计划", datetime.date(2020, 1, 1))
        assert pid > 0
        plans = plan_dao.list()
        assert len(plans) == 1


# ===================== AchievementDAO 测试 =====================

class TestAchievementDAO:
    """AchievementDAO 的列表、解锁与评估。"""

    def test_list_achievements(self, achievement_dao):
        """默认 6 个成就徽章。"""
        achievements = achievement_dao.list()
        assert len(achievements) == 6
        codes = {a["badge_code"] for a in achievements}
        expected_codes = {
            "first_focus", "focus_10", "focus_100",
            "streak_7", "streak_30", "early_bird",
        }
        assert codes == expected_codes

    def test_unlock_badge(self, achievement_dao):
        """解锁徽章。"""
        # 首次解锁成功
        affected = achievement_dao.unlock("first_focus")
        assert affected == 1
        # 重复解锁不生效（WHERE unlocked=0 不再匹配）
        affected2 = achievement_dao.unlock("first_focus")
        assert affected2 == 0
        # 验证状态
        achievements = achievement_dao.list()
        for a in achievements:
            if a["badge_code"] == "first_focus":
                assert a["unlocked"] == 1
                assert a["unlocked_at"] is not None

    def test_evaluate_no_data(self, achievement_dao):
        """无数据时 evaluate 不崩溃，返回空列表。"""
        newly = achievement_dao.evaluate()
        assert newly == []


# ===================== WhitelistDAO 测试 =====================

class TestWhitelistDAO:
    """WhitelistDAO 的 CRUD。"""

    def test_add_whitelist(self, whitelist_dao):
        """添加白名单。"""
        wid = whitelist_dao.add("微信", "WeChat.exe")
        assert wid > 0
        items = whitelist_dao.list()
        assert len(items) == 1
        assert items[0]["app_name"] == "微信"
        assert items[0]["process_name"] == "WeChat.exe"

    def test_list_whitelist(self, whitelist_dao):
        """列表正确。"""
        whitelist_dao.add("微信", "WeChat.exe")
        whitelist_dao.add("QQ", "QQ.exe")
        whitelist_dao.add("浏览器", "chrome.exe")
        items = whitelist_dao.list()
        assert len(items) == 3

    def test_delete_whitelist(self, whitelist_dao):
        """删除白名单。"""
        wid = whitelist_dao.add("微信", "WeChat.exe")
        affected = whitelist_dao.delete(wid)
        assert affected == 1
        items = whitelist_dao.list()
        assert len(items) == 0


# ===================== LockScheduleDAO 测试 =====================

class TestLockScheduleDAO:
    """LockScheduleDAO 的 CRUD 与启用/禁用。

    注意：start_time / end_time 在 SQLite 后端为 TEXT 列
    （schema 中 TIME 被 _convert_schema_stmt 转为 TEXT），
    传入字符串如 "22:00:00" 即可，无需 datetime.time 对象。
    """

    def test_create_lock(self, lock_dao):
        """创建锁屏计划。"""
        lid = lock_dao.create(
            start_time="22:00:00",
            end_time="06:00:00",
            duration=30,
            repeat_days="1,2,3,4,5",
            is_nap=0,
        )
        assert lid > 0
        locks = lock_dao.list()
        assert len(locks) == 1
        assert locks[0]["duration"] == 30
        assert locks[0]["repeat_days"] == "1,2,3,4,5"
        assert locks[0]["is_nap"] == 0
        assert locks[0]["enabled"] == 1  # 默认启用

    def test_list_locks(self, lock_dao):
        """列表正确。"""
        lock_dao.create(duration=30, is_nap=0)
        lock_dao.create(duration=15, is_nap=1)
        locks = lock_dao.list()
        assert len(locks) == 2

    def test_set_enabled(self, lock_dao):
        """启用/禁用。"""
        lid = lock_dao.create(duration=30, is_nap=0)
        # 默认 enabled=1，禁用
        affected = lock_dao.set_enabled(lid, 0)
        assert affected == 1
        locks = lock_dao.list()
        assert locks[0]["enabled"] == 0
        # 重新启用
        affected = lock_dao.set_enabled(lid, 1)
        assert affected == 1
        locks = lock_dao.list()
        assert locks[0]["enabled"] == 1

    def test_delete_lock(self, lock_dao):
        """删除锁屏计划。"""
        lid = lock_dao.create(duration=30, is_nap=0)
        affected = lock_dao.delete(lid)
        assert affected == 1
        locks = lock_dao.list()
        assert len(locks) == 0


# ===================== WhiteNoiseDAO 测试 =====================

class TestWhiteNoiseDAO:
    """WhiteNoiseDAO 的列表、添加与删除（含内置保护）。"""

    def test_list_noise(self, noise_dao):
        """默认 30 条内置白噪音。"""
        noises = noise_dao.list()
        assert len(noises) == 30
        for n in noises:
            assert n["is_builtin"] == 1

    def test_add_custom_noise(self, noise_dao):
        """添加自定义白噪音。"""
        nid = noise_dao.add("自定义音", "/path/to/custom.wav", "自定义", is_builtin=0)
        assert nid > 0
        noises = noise_dao.list()
        assert len(noises) == 31  # 30 内置 + 1 自定义
        custom = [n for n in noises if n["id"] == nid]
        assert len(custom) == 1
        assert custom[0]["name"] == "自定义音"
        assert custom[0]["is_builtin"] == 0

    def test_delete_custom_noise(self, noise_dao):
        """删除自定义（非内置）白噪音。"""
        nid = noise_dao.add("自定义音", "/path/to/custom.wav", "自定义", is_builtin=0)
        affected = noise_dao.delete(nid)
        assert affected == 1
        noises = noise_dao.list()
        assert len(noises) == 30  # 回到 30 条内置

    def test_delete_builtin_noise_fails(self, noise_dao):
        """删除内置白噪音应失败或不允许。

        WhiteNoiseDAO.delete() 的 SQL 包含 ``AND is_builtin=0`` 条件，
        对内置条目 DELETE 影响 0 行，返回 0，从而保护内置数据不被删除。
        """
        noises = noise_dao.list()
        builtin = [n for n in noises if n["is_builtin"] == 1]
        assert len(builtin) > 0
        builtin_id = builtin[0]["id"]
        affected = noise_dao.delete(builtin_id)
        assert affected == 0
        # 验证内置条目仍然存在
        noises_after = noise_dao.list()
        assert len(noises_after) == 30


# ===================== UserDAO 测试 =====================

class TestUserDAO:
    """UserDAO 的读取与昵称更新。"""

    def test_get_user(self, user_dao):
        """获取默认用户。"""
        user = user_dao.get()
        assert user is not None
        assert user["nickname"] == "我"  # 默认昵称
        assert "id" in user
        assert "created_at" in user

    def test_update_nickname(self, user_dao):
        """更新昵称。"""
        affected = user_dao.update_nickname("新昵称")
        assert affected == 1
        user = user_dao.get()
        assert user["nickname"] == "新昵称"


# ===================== HabitCheckinDAO 测试 =====================

class TestHabitCheckinDAO:
    """HabitCheckinDAO 的打卡、查重与查询。"""

    def test_habit_checkin(self, habit_dao):
        """习惯打卡。"""
        today = datetime.date.today()
        hid = habit_dao.checkin(todo_id=1, checkin_date=today)
        assert hid > 0
        record = habit_dao.get_today(todo_id=1, checkin_date=today)
        assert record is not None
        assert record["todo_id"] == 1

    def test_habit_checkin_duplicate(self, habit_dao):
        """同一天重复打卡返回 0。

        habit_checkins 表有 UNIQUE(todo_id, checkin_date) 约束，
        DAO 捕获 IntegrityError 后返回 0。
        """
        today = datetime.date.today()
        hid1 = habit_dao.checkin(todo_id=1, checkin_date=today)
        assert hid1 > 0
        hid2 = habit_dao.checkin(todo_id=1, checkin_date=today)
        assert hid2 == 0

    def test_get_today(self, habit_dao):
        """获取今日打卡。"""
        today = datetime.date.today()
        habit_dao.checkin(
            todo_id=1, checkin_date=today,
            checkin_time=datetime.datetime.now(),
            actual_value=30.0,
        )
        record = habit_dao.get_today(todo_id=1, checkin_date=today)
        assert record is not None
        assert record["todo_id"] == 1
        assert record["actual_value"] == 30.0

    def test_get_today_no_data(self, habit_dao):
        """无数据返回 None。"""
        today = datetime.date.today()
        record = habit_dao.get_today(todo_id=999, checkin_date=today)
        assert record is None


# ===================== CheckinDAO 测试 =====================

class TestCheckinDAO:
    """CheckinDAO 的起床/睡眠/补卡打卡与列表。"""

    def test_checkin_wake(self, checkin_dao):
        """起床打卡(type=0)。"""
        cid = checkin_dao.checkin(
            checkin_type=0,
            checkin_time=datetime.datetime(2025, 1, 1, 7, 0, 0),
        )
        assert cid > 0
        records = checkin_dao.list_recent()
        assert len(records) == 1
        assert records[0]["checkin_type"] == 0

    def test_checkin_sleep(self, checkin_dao):
        """睡眠打卡(type=1)。"""
        cid = checkin_dao.checkin(
            checkin_type=1,
            checkin_time=datetime.datetime(2025, 1, 1, 23, 0, 0),
        )
        assert cid > 0
        records = checkin_dao.list_recent()
        assert len(records) == 1
        assert records[0]["checkin_type"] == 1

    def test_checkin_backfill(self, checkin_dao):
        """补卡(is_backfill=1)。"""
        cid = checkin_dao.checkin(
            checkin_type=0,
            checkin_time=datetime.datetime(2025, 1, 1, 7, 0, 0),
            is_backfill=1,
        )
        assert cid > 0
        records = checkin_dao.list_recent()
        assert len(records) == 1
        assert records[0]["is_backfill"] == 1

    def test_list_recent(self, checkin_dao):
        """最近记录列表，按 checkin_time 倒序。"""
        checkin_dao.checkin(checkin_type=0,
                            checkin_time=datetime.datetime(2025, 1, 1, 7, 0, 0))
        checkin_dao.checkin(checkin_type=1,
                            checkin_time=datetime.datetime(2025, 1, 1, 23, 0, 0))
        checkin_dao.checkin(checkin_type=0,
                            checkin_time=datetime.datetime(2025, 1, 2, 7, 0, 0))
        records = checkin_dao.list_recent()
        assert len(records) == 3
        # checkin_time 在 SQLite 中为 TEXT，字符串比较与时间顺序一致
        assert str(records[0]["checkin_time"]) > str(records[1]["checkin_time"])
        assert str(records[1]["checkin_time"]) > str(records[2]["checkin_time"])


# ===================== AppConfig 测试 =====================

class TestAppConfig:
    """AppConfig 的配置目录、默认后端、切换与 JSON 结构。"""

    def test_config_dir_exists(self, app_config):
        """配置目录存在。"""
        app_config.ensure_dir()
        assert os.path.isdir(app_config.config_dir)

    def test_db_backend_default(self, app_config):
        """默认为 sqlite。"""
        assert app_config.db_backend == "sqlite"

    def test_save_and_load_backend(self, app_config):
        """保存后端切换。"""
        from src.config import DBConfig
        db_config = DBConfig(
            host="127.0.0.1", port=3306, user="root",
            password="123456", database="qingning_todo",
        )
        app_config.save(db_config, backend="mysql")
        assert app_config.db_backend == "mysql"
        # 切回 sqlite
        app_config.save_backend("sqlite")
        assert app_config.db_backend == "sqlite"

    def test_config_json_structure(self, app_config):
        """配置文件 JSON 结构正确。"""
        from src.config import DBConfig
        db_config = DBConfig(
            host="127.0.0.1", port=3306, user="root",
            password="123456", database="qingning_todo",
        )
        app_config.save(db_config, backend="mysql")
        assert os.path.isfile(app_config.config_path)
        with open(app_config.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "db_backend" in data
        assert data["db_backend"] == "mysql"
        assert "database_config" in data
        dbc = data["database_config"]
        assert dbc["host"] == "127.0.0.1"
        assert dbc["port"] == 3306
        assert dbc["user"] == "root"
        assert dbc["password"] == "123456"
        assert dbc["database"] == "qingning_todo"
        assert dbc["charset"] == "utf8mb4"
