"""数据库表结构（DDL）定义。

依据《番茄ToDo-Windows本地版-产品使用规格说明书》第五章数据库设计。
所有表使用 InnoDB 引擎、utf8mb4 字符集。
"""

# 建表语句（按依赖顺序排列）
SCHEMA_STATEMENTS = [
    # 用户/本地档案表
    """
    CREATE TABLE IF NOT EXISTS `user` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `nickname` VARCHAR(64) NOT NULL,
        `avatar_path` VARCHAR(255) NULL,
        `created_at` DATETIME NOT NULL,
        `updated_at` DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 待办集表
    """
    CREATE TABLE IF NOT EXISTS `todo_group` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `name` VARCHAR(128) NOT NULL,
        `color` VARCHAR(16) NULL,
        `sort_order` INT NOT NULL DEFAULT 0,
        `created_at` DATETIME NOT NULL,
        KEY `idx_group_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 待办事项表
    """
    CREATE TABLE IF NOT EXISTS `todo` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `group_id` BIGINT NULL,
        `title` VARCHAR(255) NOT NULL,
        `timer_type` TINYINT NOT NULL DEFAULT 0,
        `duration` INT NOT NULL DEFAULT 1500,
        `break_duration` INT NOT NULL DEFAULT 300,
        `loop_count` INT NOT NULL DEFAULT 1,
        `priority` TINYINT NOT NULL DEFAULT 0,
        `repeat_type` TINYINT NOT NULL DEFAULT 0,
        `repeat_rule` VARCHAR(64) NULL,
        `remind_time` DATETIME NULL,
        `background_path` VARCHAR(255) NULL,
        `status` TINYINT NOT NULL DEFAULT 0,
        `sort_order` INT NOT NULL DEFAULT 0,
        `created_at` DATETIME NOT NULL,
        `completed_at` DATETIME NULL,
        KEY `idx_todo_user` (`user_id`),
        KEY `idx_todo_group` (`group_id`),
        KEY `idx_todo_status` (`status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 专注记录表
    """
    CREATE TABLE IF NOT EXISTS `focus_record` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `todo_id` BIGINT NULL,
        `record_name` VARCHAR(255) NULL,
        `timer_type` TINYINT NOT NULL DEFAULT 0,
        `planned_duration` INT NOT NULL DEFAULT 0,
        `actual_duration` INT NOT NULL DEFAULT 0,
        `is_completed` TINYINT NOT NULL DEFAULT 1,
        `interrupt_reason` VARCHAR(128) NULL,
        `note` TEXT NULL,
        `start_time` DATETIME NOT NULL,
        `end_time` DATETIME NOT NULL,
        `belong_date` DATE NOT NULL,
        `created_at` DATETIME NOT NULL,
        KEY `idx_focus_user` (`user_id`),
        KEY `idx_focus_todo` (`todo_id`),
        KEY `idx_focus_date` (`belong_date`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 目标表
    """
    CREATE TABLE IF NOT EXISTS `goal` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `goal_type` TINYINT NOT NULL DEFAULT 0,
        `target_duration` INT NULL,
        `title` VARCHAR(255) NULL,
        `deadline` DATETIME NULL,
        `created_at` DATETIME NOT NULL,
        KEY `idx_goal_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 未来计划表
    """
    CREATE TABLE IF NOT EXISTS `future_plan` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `title` VARCHAR(255) NOT NULL,
        `target_date` DATE NOT NULL,
        `remark` VARCHAR(255) NULL,
        `created_at` DATETIME NOT NULL,
        KEY `idx_plan_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 打卡记录表
    """
    CREATE TABLE IF NOT EXISTS `checkin_record` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `checkin_type` TINYINT NOT NULL DEFAULT 0,
        `checkin_time` DATETIME NOT NULL,
        `belong_date` DATE NOT NULL,
        `is_backfill` TINYINT NOT NULL DEFAULT 0,
        KEY `idx_checkin_user` (`user_id`),
        KEY `idx_checkin_date` (`belong_date`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 成就徽章表
    """
    CREATE TABLE IF NOT EXISTS `achievement` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `badge_code` VARCHAR(64) NOT NULL,
        `badge_name` VARCHAR(128) NOT NULL,
        `unlocked` TINYINT NOT NULL DEFAULT 0,
        `unlocked_at` DATETIME NULL,
        KEY `idx_ach_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 专注模式白名单表
    """
    CREATE TABLE IF NOT EXISTS `focus_whitelist` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `app_name` VARCHAR(128) NOT NULL,
        `process_name` VARCHAR(255) NOT NULL,
        `created_at` DATETIME NOT NULL,
        KEY `idx_wl_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 定时锁屏计划表
    """
    CREATE TABLE IF NOT EXISTS `lock_schedule` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `start_time` TIME NULL,
        `end_time` TIME NULL,
        `duration` INT NULL,
        `repeat_days` VARCHAR(32) NULL,
        `is_nap` TINYINT NOT NULL DEFAULT 0,
        `enabled` TINYINT NOT NULL DEFAULT 1,
        `created_at` DATETIME NOT NULL,
        KEY `idx_lock_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 白噪音表
    """
    CREATE TABLE IF NOT EXISTS `white_noise` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `name` VARCHAR(128) NOT NULL,
        `file_path` VARCHAR(255) NOT NULL,
        `category` VARCHAR(64) NULL,
        `is_builtin` TINYINT NOT NULL DEFAULT 1
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
    # 设置表
    """
    CREATE TABLE IF NOT EXISTS `settings` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `user_id` BIGINT NOT NULL,
        `setting_key` VARCHAR(64) NOT NULL,
        `setting_value` VARCHAR(255) NULL,
        `updated_at` DATETIME NOT NULL,
        UNIQUE KEY `uk_setting` (`user_id`, `setting_key`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """,
]

# 内置白噪音初始数据
DEFAULT_WHITE_NOISE = [
    ("雨声", "builtin://rain", "自然", 1),
    ("海浪", "builtin://wave", "自然", 1),
    ("森林", "builtin://forest", "自然", 1),
    ("咖啡厅", "builtin://cafe", "环境", 1),
    ("篝火", "builtin://fire", "自然", 1),
    ("白噪音", "builtin://white", "环境", 1),
]

# 默认成就徽章
DEFAULT_ACHIEVEMENTS = [
    ("first_focus", "初次专注"),
    ("focus_10", "专注达人 · 10 次"),
    ("focus_100", "专注大师 · 100 次"),
    ("streak_7", "连续专注 7 天"),
    ("streak_30", "连续专注 30 天"),
    ("early_bird", "早起鸟"),
]
