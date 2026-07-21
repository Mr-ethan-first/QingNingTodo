"""数据库表结构（DDL）定义。

依据《青柠待办-产品规格说明书》第五章数据库设计。
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
        `type` TINYINT NOT NULL DEFAULT 0 COMMENT '0:普通,1:养习惯,2:定目标',
        `hide_after_complete` TINYINT NOT NULL DEFAULT 0 COMMENT '完成后第二天不再显示',
        `is_amway_mode_exempted` TINYINT NOT NULL DEFAULT 0 COMMENT '始终关闭学霸模式',
        `custom_break_duration` INT NULL COMMENT '自定义休息时长(秒)',
        `habit_target` VARCHAR(100) NULL COMMENT '习惯目标描述',
        `habit_unit` VARCHAR(20) NULL COMMENT '习惯单位(分钟/次)',
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
    # 打断详情表
    """
    CREATE TABLE IF NOT EXISTS `interrupt_details` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `focus_record_id` BIGINT NOT NULL,
        `process_name` VARCHAR(100) NOT NULL,
        `occurred_at` DATETIME NOT NULL,
        KEY `idx_int_focus` (`focus_record_id`),
        FOREIGN KEY (`focus_record_id`) REFERENCES `focus_record`(`id`) ON DELETE CASCADE
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
    # 习惯打卡表
    """
    CREATE TABLE IF NOT EXISTS `habit_checkins` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
        `todo_id` BIGINT NOT NULL,
        `checkin_date` DATE NOT NULL,
        `checkin_time` DATETIME NULL,
        `actual_value` FLOAT NULL,
        `created_at` DATETIME NOT NULL,
        UNIQUE KEY `uk_habit_date` (`todo_id`, `checkin_date`),
        KEY `idx_habit_todo` (`todo_id`)
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

# 默认设置初始数据
DEFAULT_SETTINGS = [
    ("default_focus_duration", "1500", "默认专注时长(秒)"),
    ("default_break_duration", "300", "默认休息时长(秒)"),
    ("focus_motto", "专注是成功的基石", "番茄钟格言"),
    ("focus_complete_sound", "default", "完成提示音"),
    ("auto_switch_stopwatch", "false", "倒计时自动转正计时"),
    ("max_pause_minutes", "3", "暂停时间上限(分钟)"),
    ("ask_before_break", "true", "休息前询问"),
    ("enable_focus_guard", "true", "启用学霸模式"),
    ("strict_mode", "false", "严格模式"),
    ("fixed_sort", "false", "固定排序"),
    ("no_strikethrough", "false", "不划完成线"),
    ("remember_list_expand", "true", "记住待办集展开状态"),
    ("enable_search", "true", "启用搜索"),
    ("midnight_shift", "false", "午夜模式"),
    ("habit_reminder_time", "20:00", "习惯提醒时间"),
    ("trend_line_style", "curve", "趋势图线条(curve/straight)"),
    ("chart_unit", "minutes", "统计图单位(minutes/hours)"),
    ("monthly_display_range", "7", "月度展示范围(7/full)"),
    ("theme_color", "#8CC44A", "主题颜色"),
    ("app_background", "", "背景海报路径"),
    ("background_music_path", "", "背景音乐路径"),
    ("bg_music_enabled", "false", "开启背景音(白噪音)"),
    ("auto_play_on_start", "false", "计时开始自动播放白噪音"),
    ("auto_start", "false", "开机自启"),
    ("shortcut_key", "Ctrl+Shift+A", "全局快捷键"),
    ("confirm_on_close", "true", "关闭窗口时确认（弹出退出提醒窗口）"),
]

# 内置白噪音初始数据（使用真实音频文件，来源 Wikimedia Commons / Mixkit 等免费资源）
# 名称根据下载源文件名翻译，去除 #1/#2/#3 编号
DEFAULT_WHITE_NOISE = [
    # 自然音 (Wikimedia Commons)
    ("雨声", "assets/sounds/自然音/rain_1.wav", "自然音", 1),          # Sound of rain.ogg
    ("雨滴", "assets/sounds/自然音/rain_2.wav", "自然音", 1),          # Rain drops (Gravity Sound).wav
    ("阵雨绵绵", "assets/sounds/自然音/rain_3.wav", "自然音", 1),      # Rain delay (Gravity Sound).wav
    ("海浪", "assets/sounds/自然音/ocean_1.wav", "自然音", 1),          # Life on the Ocean Wave.wav
    ("海浪拍岸", "assets/sounds/自然音/ocean_2.wav", "自然音", 1),      # Oceanwavescrushing.ogg
    ("森林鸟鸣", "assets/sounds/自然音/forest_1.wav", "自然音", 1),     # Birds Perungalathur Reserved Forest.wav
    ("林间鸟语", "assets/sounds/自然音/forest_2.wav", "自然音", 1),     # Birds forest.ogg
    ("翠鸟啼鸣", "assets/sounds/自然音/forest_3.wav", "自然音", 1),     # Bird squeak Taiwan.ogg
    ("雷声", "assets/sounds/自然音/thunder_1.wav", "自然音", 1),        # Thunder 01.ogg
    ("惊雷", "assets/sounds/自然音/thunder_3.wav", "自然音", 1),        # Nosferatu thunderclap.wav
    ("风声", "assets/sounds/自然音/wind_1.wav", "自然音", 1),           # Wind rustling (Gravity Sound).mp3
    ("林间风声", "assets/sounds/自然音/wind_2.wav", "自然音", 1),       # Wind in forest (Gravity Sound).wav
    ("落叶风声", "assets/sounds/自然音/wind_3.wav", "自然音", 1),       # Leaves in the wind (Gravity Sound).wav
    ("溪流", "assets/sounds/自然音/stream_1.wav", "自然音", 1),         # stream-river-water-up-close.wav
    ("涓涓细流", "assets/sounds/自然音/stream_2.wav", "自然音", 1),     # water-trickle.wav
    ("溪水潺潺", "assets/sounds/自然音/stream_3.wav", "自然音", 1),     # Hemlock stream.ogg
    # 氛围音
    ("咖啡厅", "assets/sounds/氛围音/cafe_1.wav", "氛围音", 1),        # Shopping mall ambience
    ("商场环境", "assets/sounds/氛围音/cafe_2.wav", "氛围音", 1),      # Bus drive ambience with talk
    ("街头氛围", "assets/sounds/氛围音/cafe_3.wav", "氛围音", 1),      # Alexa mall in Berlin
    ("篝火", "assets/sounds/氛围音/fire_1.wav", "氛围音", 1),          # Campfire sound ambience.ogg
    ("营火", "assets/sounds/氛围音/fire_2.wav", "氛围音", 1),          # Nl-Kampvuur-article.ogg
    ("蟋蟀合唱", "assets/sounds/氛围音/night_1.wav", "氛围音", 1),     # Crickets choir.ogg
    ("清晨虫鸣", "assets/sounds/氛围音/night_2.wav", "氛围音", 1),     # Sound of dogs, birds and crickets.wav
    ("夜林虫鸣", "assets/sounds/氛围音/night_3.wav", "氛围音", 1),     # Schritten nachts im Wald und Grillenzirpen.wav
    ("时钟嘀嗒", "assets/sounds/氛围音/clock_1.wav", "氛围音", 1),     # Clock ticking.ogg
    ("闹钟嘀嗒", "assets/sounds/氛围音/clock_2.wav", "氛围音", 1),     # Alarm clock ticking.ogg
    ("老座钟", "assets/sounds/氛围音/clock_3.wav", "氛围音", 1),        # Mixkit clock sound
    ("白噪音", "assets/sounds/氛围音/whitenoise_1.wav", "氛围音", 1),  # White-noise-sound-20sec.ogg
    ("纯白噪音", "assets/sounds/氛围音/whitenoise_2.wav", "氛围音", 1),# White noise.ogg
    ("高斯白噪音", "assets/sounds/氛围音/whitenoise_3.wav", "氛围音", 1), # Gaussian white noise.ogg
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
