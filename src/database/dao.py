"""数据访问对象（DAO）。

对各业务实体提供 CRUD 与统计查询。所有方法基于 Database 实例。
"""
import datetime
from typing import List, Optional

from src.database.connection import Database


class BaseDAO:
    def __init__(self, db: Database):
        self.db = db

    def _default_user_id(self) -> int:
        row = self.db.query_one("SELECT id FROM `user` LIMIT 1")
        return row["id"] if row else 1


# ---------------- 待办集 ----------------
class TodoGroupDAO(BaseDAO):
    def create(self, name: str, color: Optional[str] = None, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `todo_group`(user_id, name, color, created_at) VALUES(%s,%s,%s,%s)",
            (uid, name, color, datetime.datetime.now()),
        )

    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `todo_group` WHERE user_id=%s ORDER BY sort_order, id", (uid,)
        )

    def update(self, group_id: int, name: str, color: Optional[str]) -> int:
        return self.db.execute(
            "UPDATE `todo_group` SET name=%s, color=%s WHERE id=%s", (name, color, group_id)
        )

    def delete(self, group_id: int) -> int:
        return self.db.execute("DELETE FROM `todo_group` WHERE id=%s", (group_id,))


# ---------------- 待办事项 ----------------
class TodoDAO(BaseDAO):
    def create(self, title: str, timer_type: int = 0, duration: int = 1500,
               break_duration: int = 300, loop_count: int = 1, priority: int = 0,
               repeat_type: int = 0, repeat_rule: Optional[str] = None,
               remind_time: Optional[datetime.datetime] = None,
               group_id: Optional[int] = None, background_path: Optional[str] = None,
               user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `todo`(user_id, group_id, title, timer_type, duration, break_duration, "
            "loop_count, priority, repeat_type, repeat_rule, remind_time, background_path, "
            "status, created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s)",
            (uid, group_id, title, timer_type, duration, break_duration, loop_count, priority,
             repeat_type, repeat_rule, remind_time, background_path, datetime.datetime.now()),
        )

    def get(self, todo_id: int) -> Optional[dict]:
        return self.db.query_one("SELECT * FROM `todo` WHERE id=%s", (todo_id,))

    def list(self, status: Optional[int] = None, group_id: Optional[int] = None,
             user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        sql = "SELECT * FROM `todo` WHERE user_id=%s"
        params: list = [uid]
        if status is not None:
            sql += " AND status=%s"
            params.append(status)
        if group_id is not None:
            sql += " AND group_id=%s"
            params.append(group_id)
        sql += " ORDER BY status, priority DESC, sort_order, id DESC"
        return self.db.query_all(sql, tuple(params))

    def update(self, todo_id: int, **fields) -> int:
        if not fields:
            return 0
        allowed = {"title", "timer_type", "duration", "break_duration", "loop_count",
                   "priority", "repeat_type", "repeat_rule", "remind_time", "group_id",
                   "background_path", "status", "sort_order", "completed_at"}
        sets, params = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"`{k}`=%s")
                params.append(v)
        if not sets:
            return 0
        params.append(todo_id)
        return self.db.execute(f"UPDATE `todo` SET {', '.join(sets)} WHERE id=%s", tuple(params))

    def complete(self, todo_id: int) -> int:
        return self.db.execute(
            "UPDATE `todo` SET status=1, completed_at=%s WHERE id=%s",
            (datetime.datetime.now(), todo_id),
        )

    def delete(self, todo_id: int) -> int:
        return self.db.execute("DELETE FROM `todo` WHERE id=%s", (todo_id,))


# ---------------- 专注记录 ----------------
class FocusRecordDAO(BaseDAO):
    def create(self, todo_id: Optional[int], timer_type: int, planned_duration: int,
               actual_duration: int, start_time: datetime.datetime,
               end_time: datetime.datetime, is_completed: int = 1,
               record_name: Optional[str] = None, interrupt_reason: Optional[str] = None,
               note: Optional[str] = None, belong_date: Optional[datetime.date] = None,
               user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        if belong_date is None:
            belong_date = self._belong_date(start_time)
        return self.db.execute(
            "INSERT INTO `focus_record`(user_id, todo_id, record_name, timer_type, "
            "planned_duration, actual_duration, is_completed, interrupt_reason, note, "
            "start_time, end_time, belong_date, created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, todo_id, record_name, timer_type, planned_duration, actual_duration,
             is_completed, interrupt_reason, note, start_time, end_time, belong_date,
             datetime.datetime.now()),
        )

    @staticmethod
    def _belong_date(start_time: datetime.datetime) -> datetime.date:
        """午夜模式：凌晨 0-4 点归属前一天。"""
        if start_time.hour < 4:
            return (start_time - datetime.timedelta(days=1)).date()
        return start_time.date()

    def list_recent(self, limit: int = 50, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `focus_record` WHERE user_id=%s ORDER BY start_time DESC LIMIT %s",
            (uid, limit),
        )

    def update_name(self, record_id: int, name: str) -> int:
        return self.db.execute(
            "UPDATE `focus_record` SET record_name=%s WHERE id=%s", (name, record_id)
        )


# ---------------- 统计 ----------------
class StatsDAO(BaseDAO):
    def total_focus(self, user_id: Optional[int] = None) -> dict:
        uid = user_id or self._default_user_id()
        row = self.db.query_one(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(actual_duration),0) AS total "
            "FROM `focus_record` WHERE user_id=%s AND is_completed=1", (uid,)
        )
        return {"count": row["cnt"], "total_seconds": int(row["total"])}

    def today_focus(self, user_id: Optional[int] = None,
                    today: Optional[datetime.date] = None) -> dict:
        uid = user_id or self._default_user_id()
        today = today or datetime.date.today()
        row = self.db.query_one(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(actual_duration),0) AS total "
            "FROM `focus_record` WHERE user_id=%s AND is_completed=1 AND belong_date=%s",
            (uid, today),
        )
        return {"count": row["cnt"], "total_seconds": int(row["total"])}

    def daily_distribution(self, days: int = 30, user_id: Optional[int] = None) -> List[dict]:
        """近 N 天每日专注时长（用于热力图）。"""
        uid = user_id or self._default_user_id()
        start = datetime.date.today() - datetime.timedelta(days=days - 1)
        return self.db.query_all(
            "SELECT belong_date, COALESCE(SUM(actual_duration),0) AS total, COUNT(*) AS cnt "
            "FROM `focus_record` WHERE user_id=%s AND is_completed=1 AND belong_date>=%s "
            "GROUP BY belong_date ORDER BY belong_date", (uid, start),
        )

    def hour_distribution(self, user_id: Optional[int] = None) -> List[dict]:
        """按小时统计专注时长（高效时间区间）。"""
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT HOUR(start_time) AS hour, COALESCE(SUM(actual_duration),0) AS total "
            "FROM `focus_record` WHERE user_id=%s AND is_completed=1 "
            "GROUP BY HOUR(start_time) ORDER BY hour", (uid,),
        )

    def group_distribution(self, user_id: Optional[int] = None) -> List[dict]:
        """按待办集统计专注时长分布。"""
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT COALESCE(g.name,'未分类') AS name, COALESCE(SUM(f.actual_duration),0) AS total "
            "FROM `focus_record` f LEFT JOIN `todo` t ON f.todo_id=t.id "
            "LEFT JOIN `todo_group` g ON t.group_id=g.id "
            "WHERE f.user_id=%s AND f.is_completed=1 GROUP BY g.name", (uid,),
        )

    def streak_days(self, user_id: Optional[int] = None) -> int:
        """连续专注天数（从今天往前）。"""
        uid = user_id or self._default_user_id()
        rows = self.db.query_all(
            "SELECT DISTINCT belong_date FROM `focus_record` "
            "WHERE user_id=%s AND is_completed=1 ORDER BY belong_date DESC", (uid,)
        )
        dates = {r["belong_date"] for r in rows}
        if not dates:
            return 0
        streak = 0
        cur = datetime.date.today()
        # 允许今天尚未专注：从今天或昨天开始计
        if cur not in dates:
            cur = cur - datetime.timedelta(days=1)
            if cur not in dates:
                return 0
        while cur in dates:
            streak += 1
            cur -= datetime.timedelta(days=1)
        return streak


# ---------------- 目标 ----------------
class GoalDAO(BaseDAO):
    def upsert_duration_goal(self, goal_type: int, target_duration: int,
                             user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        existing = self.db.query_one(
            "SELECT id FROM `goal` WHERE user_id=%s AND goal_type=%s AND title IS NULL",
            (uid, goal_type),
        )
        if existing:
            self.db.execute("UPDATE `goal` SET target_duration=%s WHERE id=%s",
                            (target_duration, existing["id"]))
            return existing["id"]
        return self.db.execute(
            "INSERT INTO `goal`(user_id, goal_type, target_duration, created_at) "
            "VALUES(%s,%s,%s,%s)", (uid, goal_type, target_duration, datetime.datetime.now()),
        )

    def create_long_term(self, title: str, deadline: datetime.datetime,
                         user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `goal`(user_id, goal_type, title, deadline, created_at) "
            "VALUES(%s,3,%s,%s,%s)", (uid, title, deadline, datetime.datetime.now()),
        )

    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all("SELECT * FROM `goal` WHERE user_id=%s ORDER BY id", (uid,))

    def delete(self, goal_id: int) -> int:
        return self.db.execute("DELETE FROM `goal` WHERE id=%s", (goal_id,))


# ---------------- 未来计划表 ----------------
class FuturePlanDAO(BaseDAO):
    def create(self, title: str, target_date: datetime.date, remark: Optional[str] = None,
               user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `future_plan`(user_id, title, target_date, remark, created_at) "
            "VALUES(%s,%s,%s,%s,%s)",
            (uid, title, target_date, remark, datetime.datetime.now()),
        )

    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `future_plan` WHERE user_id=%s ORDER BY target_date", (uid,)
        )

    def update(self, plan_id: int, title: str, target_date: datetime.date,
               remark: Optional[str]) -> int:
        return self.db.execute(
            "UPDATE `future_plan` SET title=%s, target_date=%s, remark=%s WHERE id=%s",
            (title, target_date, remark, plan_id),
        )

    def delete(self, plan_id: int) -> int:
        return self.db.execute("DELETE FROM `future_plan` WHERE id=%s", (plan_id,))


# ---------------- 打卡 ----------------
class CheckinDAO(BaseDAO):
    def checkin(self, checkin_type: int, checkin_time: Optional[datetime.datetime] = None,
                is_backfill: int = 0, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        checkin_time = checkin_time or datetime.datetime.now()
        return self.db.execute(
            "INSERT INTO `checkin_record`(user_id, checkin_type, checkin_time, belong_date, "
            "is_backfill) VALUES(%s,%s,%s,%s,%s)",
            (uid, checkin_type, checkin_time, checkin_time.date(), is_backfill),
        )

    def list_recent(self, limit: int = 30, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `checkin_record` WHERE user_id=%s ORDER BY checkin_time DESC LIMIT %s",
            (uid, limit),
        )


# ---------------- 成就 ----------------
class AchievementDAO(BaseDAO):
    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `achievement` WHERE user_id=%s ORDER BY id", (uid,)
        )

    def unlock(self, badge_code: str, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "UPDATE `achievement` SET unlocked=1, unlocked_at=%s "
            "WHERE user_id=%s AND badge_code=%s AND unlocked=0",
            (datetime.datetime.now(), uid, badge_code),
        )

    def evaluate(self, user_id: Optional[int] = None) -> List[str]:
        """根据当前统计解锁达成的徽章，返回本次新解锁的徽章码。"""
        uid = user_id or self._default_user_id()
        stats = StatsDAO(self.db)
        total = stats.total_focus(uid)
        streak = stats.streak_days(uid)
        newly = []
        rules = {
            "first_focus": total["count"] >= 1,
            "focus_10": total["count"] >= 10,
            "focus_100": total["count"] >= 100,
            "streak_7": streak >= 7,
            "streak_30": streak >= 30,
        }
        for code, ok in rules.items():
            if ok and self.unlock(code, uid) > 0:
                newly.append(code)
        return newly


# ---------------- 白名单 ----------------
class WhitelistDAO(BaseDAO):
    def add(self, app_name: str, process_name: str, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `focus_whitelist`(user_id, app_name, process_name, created_at) "
            "VALUES(%s,%s,%s,%s)", (uid, app_name, process_name, datetime.datetime.now()),
        )

    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `focus_whitelist` WHERE user_id=%s ORDER BY id", (uid,)
        )

    def delete(self, wl_id: int) -> int:
        return self.db.execute("DELETE FROM `focus_whitelist` WHERE id=%s", (wl_id,))


# ---------------- 定时锁屏 ----------------
class LockScheduleDAO(BaseDAO):
    def create(self, start_time=None, end_time=None, duration=None, repeat_days=None,
               is_nap: int = 0, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `lock_schedule`(user_id, start_time, end_time, duration, repeat_days, "
            "is_nap, enabled, created_at) VALUES(%s,%s,%s,%s,%s,%s,1,%s)",
            (uid, start_time, end_time, duration, repeat_days, is_nap, datetime.datetime.now()),
        )

    def list(self, user_id: Optional[int] = None) -> List[dict]:
        uid = user_id or self._default_user_id()
        return self.db.query_all(
            "SELECT * FROM `lock_schedule` WHERE user_id=%s ORDER BY id", (uid,)
        )

    def set_enabled(self, lock_id: int, enabled: int) -> int:
        return self.db.execute(
            "UPDATE `lock_schedule` SET enabled=%s WHERE id=%s", (enabled, lock_id)
        )

    def delete(self, lock_id: int) -> int:
        return self.db.execute("DELETE FROM `lock_schedule` WHERE id=%s", (lock_id,))


# ---------------- 白噪音 ----------------
class WhiteNoiseDAO(BaseDAO):
    def list(self) -> List[dict]:
        return self.db.query_all("SELECT * FROM `white_noise` ORDER BY id")


# ---------------- 设置 ----------------
class SettingsDAO(BaseDAO):
    def set(self, key: str, value: str, user_id: Optional[int] = None) -> int:
        uid = user_id or self._default_user_id()
        return self.db.execute(
            "INSERT INTO `settings`(user_id, setting_key, setting_value, updated_at) "
            "VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), "
            "updated_at=VALUES(updated_at)",
            (uid, key, value, datetime.datetime.now()),
        )

    def get(self, key: str, default: Optional[str] = None,
            user_id: Optional[int] = None) -> Optional[str]:
        uid = user_id or self._default_user_id()
        row = self.db.query_one(
            "SELECT setting_value FROM `settings` WHERE user_id=%s AND setting_key=%s",
            (uid, key),
        )
        return row["setting_value"] if row else default

    def all(self, user_id: Optional[int] = None) -> dict:
        uid = user_id or self._default_user_id()
        rows = self.db.query_all(
            "SELECT setting_key, setting_value FROM `settings` WHERE user_id=%s", (uid,)
        )
        return {r["setting_key"]: r["setting_value"] for r in rows}


# ---------------- 用户 ----------------
class UserDAO(BaseDAO):
    def get(self) -> Optional[dict]:
        return self.db.query_one("SELECT * FROM `user` LIMIT 1")

    def update_nickname(self, nickname: str) -> int:
        uid = self._default_user_id()
        return self.db.execute(
            "UPDATE `user` SET nickname=%s, updated_at=%s WHERE id=%s",
            (nickname, datetime.datetime.now(), uid),
        )
