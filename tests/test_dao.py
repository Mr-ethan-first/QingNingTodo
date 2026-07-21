"""DAO 层业务逻辑测试。"""
import datetime

from src.database import dao


def test_todo_group_crud(db):
    g = dao.TodoGroupDAO(db)
    gid = g.create("学习", "#FF0000")
    assert gid > 0
    groups = g.list()
    assert any(x["id"] == gid for x in groups)
    g.update(gid, "学习2", "#00FF00")
    assert g.list()[0]["name"] == "学习2"
    g.delete(gid)
    assert all(x["id"] != gid for x in g.list())


def test_todo_crud_and_complete(db):
    t = dao.TodoDAO(db)
    tid = t.create("背单词", timer_type=0, duration=1500, priority=2)
    assert tid > 0
    got = t.get(tid)
    assert got["title"] == "背单词"
    assert got["status"] == 0

    # 更新
    t.update(tid, title="背单词v2", duration=3000)
    got = t.get(tid)
    assert got["title"] == "背单词v2"
    assert got["duration"] == 3000

    # 列表筛选
    assert len(t.list(status=0)) == 1
    assert len(t.list(status=1)) == 0

    # 完成
    t.complete(tid)
    got = t.get(tid)
    assert got["status"] == 1
    assert got["completed_at"] is not None
    assert len(t.list(status=1)) == 1

    # 删除
    t.delete(tid)
    assert t.get(tid) is None


def test_focus_record_and_stats(db):
    t = dao.TodoDAO(db)
    tid = t.create("专注任务", duration=1500)
    fr = dao.FocusRecordDAO(db)
    st = dao.StatsDAO(db)

    now = datetime.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    fr.create(tid, 0, 1500, 1500, now, now + datetime.timedelta(minutes=25))
    fr.create(tid, 0, 1500, 900, now, now + datetime.timedelta(minutes=15))
    # 一条放弃记录（不计入有效）
    fr.create(tid, 0, 1500, 300, now, now + datetime.timedelta(minutes=5), is_completed=0)

    total = st.total_focus()
    assert total["count"] >= 2
    assert total["total_seconds"] >= 2400  # 1500 + 900

    today = st.today_focus(today=now.date())
    assert today["count"] >= 2

    hours = st.hour_distribution()
    assert any(h["hour"] == 10 for h in hours)

    daily = st.daily_distribution(30)
    assert len(daily) >= 1


def test_belong_date_midnight_mode(db):
    fr = dao.FocusRecordDAO(db)
    # 凌晨2点应归属前一天
    t = datetime.datetime(2026, 7, 15, 2, 30, 0)
    assert fr._belong_date(t) == datetime.date(2026, 7, 14)
    # 早上9点归属当天
    t2 = datetime.datetime(2026, 7, 15, 9, 0, 0)
    assert fr._belong_date(t2) == datetime.date(2026, 7, 15)


def test_streak_days(db):
    fr = dao.FocusRecordDAO(db)
    st = dao.StatsDAO(db)
    today = datetime.date.today()
    for i in range(3):
        d = datetime.datetime.combine(today - datetime.timedelta(days=i),
                                      datetime.time(10, 0))
        fr.create(None, 0, 1500, 1500, d, d + datetime.timedelta(minutes=25),
                  belong_date=(today - datetime.timedelta(days=i)))
    assert st.streak_days() == 3


def test_achievement_evaluate(db):
    fr = dao.FocusRecordDAO(db)
    ach = dao.AchievementDAO(db)
    now = datetime.datetime.now().replace(hour=10)
    fr.create(None, 0, 1500, 1500, now, now + datetime.timedelta(minutes=25))
    newly = ach.evaluate()
    assert "first_focus" in newly
    # 再次评估不应重复解锁
    newly2 = ach.evaluate()
    assert "first_focus" not in newly2


def test_goal_upsert(db):
    g = dao.GoalDAO(db)
    g.upsert_duration_goal(0, 3600)  # 每日60分钟
    g.upsert_duration_goal(0, 7200)  # 更新为120分钟
    goals = [x for x in g.list() if x["goal_type"] == 0 and x["title"] is None]
    assert len(goals) == 1
    assert goals[0]["target_duration"] == 7200


def test_goal_long_term(db):
    g = dao.GoalDAO(db)
    gid = g.create_long_term("考研上岸", datetime.datetime(2026, 12, 31, 0, 0))
    assert gid > 0
    lt = [x for x in g.list() if x["title"] == "考研上岸"]
    assert len(lt) == 1


def test_future_plan_crud(db):
    fp = dao.FuturePlanDAO(db)
    pid = fp.create("生日", datetime.date.today() + datetime.timedelta(days=10), "备注")
    assert pid > 0
    assert len(fp.list()) == 1
    fp.update(pid, "生日2", datetime.date.today() + datetime.timedelta(days=20), None)
    assert fp.list()[0]["title"] == "生日2"
    fp.delete(pid)
    assert len(fp.list()) == 0


def test_checkin(db):
    c = dao.CheckinDAO(db)
    c.checkin(0)  # 起床
    c.checkin(1)  # 睡眠
    assert len(c.list_recent()) == 2


def test_whitelist_crud(db):
    wl = dao.WhitelistDAO(db)
    wid = wl.add("Chrome", "chrome.exe")
    assert wid > 0
    assert len(wl.list()) == 1
    wl.delete(wid)
    assert len(wl.list()) == 0


def test_lock_schedule_crud(db):
    lk = dao.LockScheduleDAO(db)
    lid = lk.create(start_time="23:00:00", end_time="07:00:00")
    assert lid > 0
    assert len(lk.list()) == 1
    lk.set_enabled(lid, 0)
    assert lk.list()[0]["enabled"] == 0
    lk.delete(lid)
    assert len(lk.list()) == 0


def test_settings_upsert_and_get(db):
    s = dao.SettingsDAO(db)
    s.set("theme_color", "#FF6347")
    assert s.get("theme_color") == "#FF6347"
    s.set("theme_color", "#000000")
    assert s.get("theme_color") == "#000000"  # 更新而非新增
    assert s.get("not_exist", "default") == "default"
    all_settings = s.all()
    assert all_settings["theme_color"] == "#000000"


def test_white_noise_seeded(db):
    wn = dao.WhiteNoiseDAO(db)
    assert len(wn.list()) >= 1


def test_user_nickname(db):
    u = dao.UserDAO(db)
    assert u.get() is not None
    u.update_nickname("小番茄")
    assert u.get()["nickname"] == "小番茄"


def test_group_distribution(db):
    g = dao.TodoGroupDAO(db)
    t = dao.TodoDAO(db)
    fr = dao.FocusRecordDAO(db)
    st = dao.StatsDAO(db)
    gid = g.create("英语_分布")
    tid = t.create("听力_分布", group_id=gid)
    now = datetime.datetime.now().replace(hour=10)
    fr.create(tid, 0, 1500, 1500, now, now + datetime.timedelta(minutes=25))
    dist = st.group_distribution()
    assert any(d["name"] == "英语_分布" and int(d["total"]) >= 1500 for d in dist)
