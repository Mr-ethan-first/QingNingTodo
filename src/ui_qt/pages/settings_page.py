"""设置页面（PyQt6）- 全面改造版。

分区：
1. 个人信息          2. 外观 | 主题       3. 专注计时设置
4. 待办显示设置      5. 习惯提醒         6. 系统集成
7. 习惯养成          8. 定时锁屏         9. 本地数据
10. 关于 | 帮助
"""
import json
import os
import sys

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QTimeEdit, QVBoxLayout, QWidget,
)

from src.theme import THEMES
from src.ui_qt.icons import icon
from src.ui_qt.pages import PageBase
from src.ui_qt.widgets import (
    combo_box, line_edit, primary_button, ghost_button,
    section_title, card, ToggleSwitch, PlusMinusSpinBox, PlusMinusTimeEdit,
)

# ---------- 分区标题图标映射 ----------
SECTION_ICONS = {
    "个人信息": "user",
    "外观 | 主题": "settings",
    "专注计时设置": "timer",
    "待办显示设置": "checklist",
    "习惯提醒": "bell",
    "系统集成": "link",
    "习惯养成": "target",
    "定时锁屏": "shield",
    "本地数据": "database",
    "关于 | 帮助": "info",
}


class SettingsPage(PageBase):
    def __init__(self, state):
        self.user_dao = state.user_dao
        self.settings_dao = state.settings_dao
        self.goal_dao = state.goal_dao
        self.wl_dao = state.whitelist_dao
        self.lock_dao = state.lock_schedule_dao
        self.wn_dao = state.white_noise_dao
        super().__init__(state)

    # ================================================================
    #  构建页面
    # ================================================================
    def _build(self):
        self._lay.addWidget(section_title("设置", "settings"))
        su = QLabel("调墨色、定目标、守专注 · 随心而设")
        su.setObjectName("muted")
        self._lay.addWidget(su)

        self._add_section("个人信息", self._build_user)
        self._add_section("外观 | 主题", self._build_theme)
        self._add_section("专注计时设置", self._build_focus)
        self._add_section("待办显示设置", self._build_todo_display)
        self._add_section("习惯提醒", self._build_habit_reminder)
        self._add_section("系统集成", self._build_system)
        self._add_section("习惯养成", self._build_goal)
        self._add_section("定时锁屏", self._build_lock)
        self._add_section("本地数据", self._build_data)
        self._add_section("关于 | 帮助", self._build_about)
        self._lay.addStretch(1)

    # ================================================================
    #  通用辅助
    # ================================================================
    def _add_section(self, title: str, builder):
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        lay.addWidget(section_title(title, SECTION_ICONS.get(title)))
        builder(lay)
        self._lay.addWidget(c)
        self._lay.addSpacing(20)  # 分区间距 20px

    def _setting_row(self, lay, icon_name, label_text, desc_text,
                    right_widget, indent: bool = False):
        """统一行布局：左侧 [图标块] 标签 + 描述，右侧控件。"""
        row = QHBoxLayout()
        row.setSpacing(12)

        # 图标块：统一 34x34，primary_soft 背景色，primary 图标色
        ico_lbl = QLabel()
        t_ = self._t
        ico_lbl.setPixmap(icon(icon_name, t_.primary, 18).pixmap(34, 34))
        ico_lbl.setFixedSize(34, 34)
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet(
            f"background:{t_.primary_soft}; border-radius:{t_.radius_sm}px;")
        row.addWidget(ico_lbl)

        # 文字区：统一字体
        col = QVBoxLayout()
        col.setSpacing(2)
        lab = QLabel(label_text)
        lab.setStyleSheet(f"font-size:14px; font-weight:500; color:{t_.text};")
        col.addWidget(lab)
        if desc_text:
            desc = QLabel(desc_text)
            desc.setStyleSheet(f"font-size:12px; color:{t_.text_muted};")
            col.addWidget(desc)
        row.addLayout(col, 1)

        # 右侧控件
        if isinstance(right_widget, QWidget):
            row.addWidget(right_widget)
        else:
            row.addLayout(right_widget)
        if indent:
            row.setContentsMargins(46, 2, 0, 2)  # 图标34 + 间距12
        lay.addLayout(row)

    def _switch_row(self, lay, icon_name, label_text, desc_text,
                    key: str, indent: bool = False):
        """创建开关行，返回 ToggleSwitch（丝滑滑块开关）。"""
        val = self.settings_dao.get(key, "false").lower()
        sw = ToggleSwitch(checked=(val == "true"))
        sw.toggled.connect(lambda checked: self.settings_dao.set(key, "true" if checked else "false"))
        self._setting_row(lay, icon_name, label_text, desc_text, sw, indent)
        return sw

    def _sep(self, lay):
        """水平分隔线。"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{self._t.divider}; max-height:1px;")
        lay.addWidget(line)

    # ================================================================
    #  分区 1：个人信息
    # ================================================================
    def _build_user(self, lay):
        self.ed_nick = line_edit("昵称")
        row = QHBoxLayout()
        row.addWidget(self.ed_nick, 1)
        row.addWidget(primary_button("保存昵称", on_click=self._save_nick))
        lay.addLayout(row)

    # ================================================================
    #  分区 2：外观 | 主题
    # ================================================================
    def _build_theme(self, lay):
        # 2a. 主题选择 (light/dark)
        self.cb_theme = combo_box(
            [(v.name, v.label) for v in THEMES.values()],
            value=self.state.theme_name, on_change=self._on_theme_change, min_w=260)
        self._setting_row(lay, "settings", "界面主题",
                          "一键切换白色 / 黑色风格，立即全局生效。",
                          self.cb_theme)

        self._sep(lay)

        # 2b. 主题颜色选择器
        t_ = self._t
        saved_color = self.settings_dao.get("theme_color", t_.primary)
        self._theme_color = QColor(saved_color)
        self.btn_color = primary_button("选择颜色", on_click=self._pick_theme_color)
        self.btn_color.setStyleSheet(
            f"background:{saved_color}; color:#fff; border:none;"
            f"border-radius:{t_.radius_md}px; padding:9px 24px; font-weight:600;"
            f" min-width:100px;")
        self._setting_row(lay, "edit", "主题颜色",
                          "自定义应用主色调，选择后自动更新。",
                          self.btn_color)

        self._sep(lay)

        # 2c. 背景海报
        self._bg_path = self.settings_dao.get("app_background", "")
        self.lbl_bg = QLabel(os.path.basename(self._bg_path) if self._bg_path else "未设置")
        self.lbl_bg.setObjectName("muted")
        self.lbl_bg.setStyleSheet(f"color:{t_.text_muted}; font-size:13px;")
        row_bg = QHBoxLayout()
        row_bg.addWidget(self.lbl_bg, 1)
        row_bg.addWidget(ghost_button("选择图片", on_click=self._pick_background))
        self._setting_row(lay, "image", "背景海报",
                          "为专注页面选择一张背景图片。",
                          row_bg)

    # ================================================================
    #  分区 3：专注计时设置
    # ================================================================
    def _build_focus(self, lay):
        # 3a. 学霸模式开关
        self.cb_focus_guard = self._switch_row(
            lay, "shield", "学霸模式",
            "专注时屏蔽非白名单应用，保持沉浸状态。",
            "enable_focus_guard")

        # 白名单管理（学霸模式下展开）
        self.wl_container = QWidget()
        wl_lay = QVBoxLayout(self.wl_container)
        wl_lay.setContentsMargins(38, 0, 0, 0)
        wl_lay.setSpacing(8)
        self.list_wl = QListWidget()
        self.list_wl.setMaximumHeight(120)
        wl_lay.addWidget(self.list_wl)
        wl_row = QHBoxLayout()
        wl_row.addWidget(primary_button("添加白名单", on_click=self._add_wl))
        wl_row.addWidget(ghost_button("删除选中", on_click=self._del_wl))
        wl_lay.addLayout(wl_row)
        lay.addWidget(self.wl_container)
        # 必须在 addWidget（reparent）之后再 setVisible，
        # 否则容器作为无父 widget 会以顶层窗口闪现
        self.wl_container.setVisible(
            self.settings_dao.get("enable_focus_guard", "true").lower() == "true")
        self.cb_focus_guard.toggled.connect(
            lambda v: self.wl_container.setVisible(v))

        self._sep(lay)

        # 3b. 严格模式
        self._switch_row(lay, "shield", "严格模式",
                         "学霸模式下，触碰白名单外应用直接结束专注。",
                         "strict_mode", indent=True)

        self._sep(lay)

        # 3c. 倒计时自动转正计时
        self._switch_row(lay, "stopwatch", "倒计时自动转正计时",
                         "倒计时归零后自动切换为正计时继续记录。",
                         "auto_switch_stopwatch")

        self._sep(lay)

        # 3d. 自定义番茄钟格言
        motto_val = self.settings_dao.get("focus_motto", "专注是成功的基石")
        self.ed_motto = line_edit(value=motto_val)
        self.ed_motto.editingFinished.connect(
            lambda: self.settings_dao.set("focus_motto", self.ed_motto.text() or "专注是成功的基石"))
        self._setting_row(lay, "edit", "番茄钟格言",
                          "专注时显示在计时器下方的激励文字。",
                          self.ed_motto)

        self._sep(lay)

        # 3e. 自定义休息时间
        break_secs = int(self.settings_dao.get("default_break_duration", "300"))
        self.sp_break = PlusMinusSpinBox()
        self.sp_break.setRange(1, 120)
        self.sp_break.setValue(break_secs // 60)
        self.sp_break.setSuffix(" 分钟")
        self.sp_break.setFixedWidth(130)
        self.sp_break.valueChanged.connect(
            lambda v: self.settings_dao.set("default_break_duration", str(v * 60)))
        self._setting_row(lay, "clock", "自定义休息时间",
                          "每次专注完成后的默认休息时长。",
                          self.sp_break)

        self._sep(lay)

        # 3f. 自定义暂停时间上限
        max_pause = float(self.settings_dao.get("max_pause_minutes", "3"))
        self.sp_pause = PlusMinusSpinBox()
        self.sp_pause.setRange(0, 60)
        self.sp_pause.setValue(int(max_pause))
        self.sp_pause.setSuffix(" 分钟")
        self.sp_pause.setFixedWidth(130)
        self.sp_pause.valueChanged.connect(
            lambda v: self.settings_dao.set("max_pause_minutes", str(v)))
        self._setting_row(lay, "clock", "暂停时间上限",
                          "暂停超过此时长自动放弃本次专注（0 为不限制）。",
                          self.sp_pause)

        self._sep(lay)

        # 3g. 计时完成后提示音
        sound_val = self.settings_dao.get("focus_complete_sound", "default")
        self.cb_sound = combo_box(
            [("default", "系统默认"), ("none", "无")],
            value=sound_val, on_change=self._on_sound_change, min_w=200)
        self._setting_row(lay, "bell", "计时完成提示音",
                          "专注 / 休息计时结束后的声音提醒。",
                          self.cb_sound)

        self._sep(lay)

        # 3h. 白噪音（背景音乐）
        music_path = self.settings_dao.get("background_music_path", "")
        noise_items = [("0", "无")]
        try:
            for n in self.wn_dao.list():
                noise_items.append((str(n["id"]), n["name"]))
        except Exception:
            pass
        # 如果设置中保存的是数字 ID，用它做默认值；否则用 "0"
        noise_val = music_path if music_path.isdigit() else "0"
        self.cb_noise = combo_box(
            noise_items, value=noise_val,
            on_change=self._on_bg_music_change, min_w=200)
        self._setting_row(lay, "habit", "白噪音（背景音乐）",
                          "专注时播放环境音，帮助进入心流状态。",
                          self.cb_noise)

        # 3h-2. 计时开始自动播放白噪音
        self._switch_row(lay, "play", "计时开始自动播放",
                         "开始专注计时时自动播放所选白噪音。",
                         "auto_play_on_start")

        self._sep(lay)

        # 3i. 进入休息计时前询问
        self._switch_row(lay, "bell", "进入休息前询问",
                         "休息开始前弹出确认，可选择跳过休息。",
                         "ask_before_break")

    # ================================================================
    #  分区 4：待办显示设置
    # ================================================================
    def _build_todo_display(self, lay):
        self._switch_row(lay, "history", "午夜模式",
                         "凌晨 0-4 点的记录归属前一天，符合自然作息。",
                         "midnight_shift")
        self._sep(lay)
        self._switch_row(lay, "sort", "固定排序",
                         "待办按优先级固定排序，新添加不置顶。",
                         "fixed_sort")
        self._sep(lay)
        self._switch_row(lay, "checklist", "不划完成线",
                         "完成待办后不在名称上显示删除线。",
                         "no_strikethrough")
        self._sep(lay)
        self._switch_row(lay, "chevron", "记住待办集展开状态",
                         "下次打开时恢复上次各分组的展开 / 折叠。",
                         "remember_list_expand")
        self._sep(lay)
        self._switch_row(lay, "edit", "待办较多时可下拉搜索",
                         "待办数量超过一定阈值时显示搜索框。",
                         "enable_search")

    # ================================================================
    #  分区 5：习惯提醒
    # ================================================================
    def _build_habit_reminder(self, lay):
        reminder_time = self.settings_dao.get("habit_reminder_time", "20:00")
        try:
            h, m = map(int, reminder_time.split(":"))
        except Exception:
            h, m = 20, 0
        from PyQt6.QtCore import QTime
        self.te_reminder = PlusMinusTimeEdit()
        self.te_reminder.setTime(QTime(h, m))
        self.te_reminder.timeChanged.connect(
            lambda t: self.settings_dao.set("habit_reminder_time",
                                            t.toString("HH:mm")))
        self._setting_row(lay, "bell", "习惯未完成提醒时间",
                          "每天在此时间提醒尚未打卡的习惯。",
                          self.te_reminder)

    # ================================================================
    #  分区 6：系统集成
    # ================================================================
    def _build_system(self, lay):
        # 6a. 开机自启
        # 初始状态以注册表实际值为准（settings_dao 可能与注册表不同步）
        auto_start = self._read_auto_start_from_registry()
        self.cb_auto_start = ToggleSwitch(checked=auto_start)
        # 同步 settings_dao 与注册表实际状态
        self.settings_dao.set("auto_start", "true" if auto_start else "false")
        self.cb_auto_start.toggled.connect(self._on_auto_start_toggle)
        self._setting_row(lay, "loop", "开机自启",
                          "系统启动后自动运行青柠待办。",
                          self.cb_auto_start)

        self._sep(lay)

        # 6a-2. 关闭窗口时确认（提醒窗口）
        # 开启：点击叉号弹出退出提醒窗口；关闭：点击叉号直接退出程序。
        # 默认开启（与退出提醒窗口的「不再提醒」联动：勾选后此开关自动置为关闭）。
        confirm_val = self.settings_dao.get("confirm_on_close", "true").lower()
        self.cb_confirm_close = ToggleSwitch(checked=(confirm_val == "true"))
        self.cb_confirm_close.toggled.connect(
            lambda checked: self.settings_dao.set(
                "confirm_on_close", "true" if checked else "false"))
        self._setting_row(lay, "close", "关闭窗口时确认",
                          "点击叉号时弹出提醒，可选择退出或最小化到托盘；关闭则直接退出。",
                          self.cb_confirm_close)

        self._sep(lay)

        # 6b. 全局快捷键
        shortcut_val = self.settings_dao.get("shortcut_key", "Ctrl+Shift+A")
        self.lbl_shortcut = QLabel(shortcut_val)
        self.lbl_shortcut.setStyleSheet(
            f"font-size:13px; color:{self._t.primary}; "
            f"background:{self._t.surface_variant}; "
            f"border:1px solid {self._t.border}; "
            f"border-radius:{self._t.radius_sm}px; padding:6px 14px;")
        self.btn_edit_shortcut = ghost_button("修改", on_click=self._edit_shortcut)
        row_sc = QHBoxLayout()
        row_sc.setSpacing(8)
        row_sc.addWidget(self.lbl_shortcut)
        row_sc.addWidget(self.btn_edit_shortcut)
        self._setting_row(lay, "link", "全局快捷键",
                          "快速唤起青柠待办（全局热键已生效）。",
                          row_sc)

    # ================================================================
    #  分区 7：习惯养成
    # ================================================================
    def _build_goal(self, lay):
        self.sp_daily = line_edit("分钟/天", value="0")
        self.sp_weekly = line_edit("分钟/周", value="0")
        self.sp_monthly = line_edit("分钟/月", value="0")
        t_ = self._t
        for label_text, widget in [("每日目标：", self.sp_daily),
                                   ("每周目标：", self.sp_weekly),
                                   ("每月目标：", self.sp_monthly)]:
            r = QHBoxLayout()
            lab = QLabel(label_text)
            lab.setStyleSheet(f"color:{t_.text_muted};")
            lab.setFixedWidth(90)
            r.addWidget(lab)
            r.addWidget(widget)
            lay.addLayout(r)
        lay.addWidget(primary_button("保存目标", on_click=self._save_goals))

    # ================================================================
    #  分区 8：定时锁屏
    # ================================================================
    def _build_lock(self, lay):
        self.ed_lock_start = line_edit("开始 (HH:MM)", value="23:00")
        self.ed_lock_end = line_edit("结束 (HH:MM)", value="07:00")
        self.list_lock = QListWidget()
        self.list_lock.setMaximumHeight(100)
        row = QHBoxLayout()
        row.addWidget(self.ed_lock_start)
        row.addWidget(self.ed_lock_end)
        row.addWidget(primary_button("添加时段", on_click=self._add_lock))
        row.addWidget(ghost_button("删除选中", on_click=self._del_lock))
        lay.addLayout(row)
        lay.addWidget(self.list_lock)

    # ================================================================
    #  分区 9：本地数据
    # ================================================================
    def _build_data(self, lay):
        row = QHBoxLayout()
        row.addWidget(primary_button("导出备份 (JSON)", on_click=self._export))
        row.addWidget(ghost_button("修改数据库连接", on_click=self._change_db))
        lay.addLayout(row)
        self.lbl_db = QLabel("")
        self.lbl_db.setObjectName("muted")
        lay.addWidget(self.lbl_db)

        self._sep(lay)

        # 清除缓存
        lay.addWidget(primary_button("清除缓存", on_click=self._clear_cache))

        self._sep(lay)

        # 清除所有数据
        lay.addWidget(ghost_button("清除所有数据", on_click=self._clear_all_data))

    # ================================================================
    #  分区 10：关于 | 帮助
    # ================================================================
    def _build_about(self, lay):
        t_ = self._t
        row = QHBoxLayout()
        ico_lbl = QLabel()
        ico_lbl.setPixmap(icon("leaf", t_.primary, 24).pixmap(40, 40))
        ico_lbl.setFixedSize(40, 40)
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(ico_lbl)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel("青柠待办")
        name.setStyleSheet(f"font-size:18px; font-weight:700; color:{t_.text};")
        ver = QLabel("v1.0.0")
        ver.setObjectName("muted")
        ver.setStyleSheet(f"font-size:13px; color:{t_.text_muted};")
        col.addWidget(name)
        col.addWidget(ver)
        row.addLayout(col, 1)
        lay.addLayout(row)

        self._sep(lay)

        lay.addWidget(primary_button("帮助文档", on_click=self._open_help))

    # ================================================================
    #  刷新（从 DAO 加载最新数据）
    # ================================================================
    def refresh(self):
        user = self.user_dao.get()
        if user:
            self.ed_nick.setText(user.get("nickname", ""))
        for g in self.goal_dao.list():
            if g["title"] is None and g["target_duration"] is not None:
                mins = g["target_duration"] // 60
                if g["goal_type"] == 0:
                    self.sp_daily.setText(str(mins))
                elif g["goal_type"] == 1:
                    self.sp_weekly.setText(str(mins))
                elif g["goal_type"] == 2:
                    self.sp_monthly.setText(str(mins))
        self._reload_wl()
        self._reload_lock()
        # 同步「关闭窗口时确认」开关（对话框内勾选"不再提醒"后会改变此配置）
        if hasattr(self, "cb_confirm_close"):
            confirm_val = self.settings_dao.get("confirm_on_close", "true").lower()
            self.cb_confirm_close.blockSignals(True)
            self.cb_confirm_close.setChecked(confirm_val == "true")
            self.cb_confirm_close.blockSignals(False)
        cfg = self.state.app_config.load()
        backend = self.state.app_config.db_backend
        if backend == "mysql" and cfg:
            self.lbl_db.setText(
                f"当前连接：{cfg.user}@{cfg.host}:{cfg.port}/{cfg.database}")
        else:
            self.lbl_db.setText("当前连接：SQLite（本地存储）")
        self.lbl_db.setStyleSheet(
            f"color:{self._t.text_muted}; font-size:13px;")

    def _reload_wl(self):
        self.list_wl.clear()
        for w in self.wl_dao.list():
            self.list_wl.addItem(QListWidgetItem(
                f"{w['app_name']} ({w['process_name']}) #{w['id']}"))

    def _reload_lock(self):
        self.list_lock.clear()
        for l in self.lock_dao.list():
            en = "启用" if l["enabled"] else "停用"
            self.list_lock.addItem(QListWidgetItem(
                f"{l['start_time']} - {l['end_time']} [{en}] #{l['id']}"))

    # ================================================================
    #  动作 / 回调
    # ================================================================
    def _save_nick(self):
        name = self.ed_nick.text().strip()
        if name:
            self.user_dao.update_nickname(name)
            self._toast("昵称已保存")

    def _on_theme_change(self):
        name = self.cb_theme.currentData()
        self.state.set_theme(name)
        self.settings_dao.set("theme", name)

    def _pick_theme_color(self):
        color = QColorDialog.getColor(
            QColor(self.settings_dao.get("theme_color", "#8CC44A")),
            self, "选择主题颜色")
        if color.isValid():
            self.settings_dao.set("theme_color", color.name())
            # 全局换肤：广播给所有订阅者（含本页与侧栏），主色及联动色立即生效
            self.state.apply_theme_color(color.name())
            t_ = self._t
            self.btn_color.setStyleSheet(
                f"background:{color.name()}; color:#fff; border:none;"
                f"border-radius:{t_.radius_md}px; padding:9px 24px; font-weight:600;"
                f" min-width:100px;")
            self._toast(f"主题颜色已更新为 {color.name()}")

    def _pick_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景海报", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.settings_dao.set("app_background", path)
            self.lbl_bg.setText(os.path.basename(path))
            # 通知专注页即时刷新背景
            try:
                self.state.notify_background_change()
            except Exception:
                pass
            self._toast("背景海报已设置")

    def _on_sound_change(self):
        self.settings_dao.set("focus_complete_sound", self.cb_sound.currentData())

    def _on_bg_music_change(self):
        val = self.cb_noise.currentData()
        self.settings_dao.set("background_music_path", val)
        # 联动：让「专注开始自动播放」使用设置页选定的白噪音，
        # 与 WhiteNoiseDialog 共用 last_noise_id（实际播放链路读取的键）
        if val and val != "0":
            self.settings_dao.set("last_noise_id", val)

    def _save_goals(self):
        try:
            self.goal_dao.upsert_duration_goal(0, int(self.sp_daily.text() or 0) * 60)
            self.goal_dao.upsert_duration_goal(1, int(self.sp_weekly.text() or 0) * 60)
            self.goal_dao.upsert_duration_goal(2, int(self.sp_monthly.text() or 0) * 60)
            self._toast("专注目标已保存")
        except (ValueError, TypeError):
            self._toast("请输入有效的数字")

    def _add_wl(self):
        name, ok = QInputDialog.getText(self, "添加白名单", "应用名称：")
        if ok and name:
            proc, ok2 = QInputDialog.getText(
                self, "添加白名单", "进程名 (如 chrome.exe)：", text=name)
            if not ok2:
                proc = name
            self.wl_dao.add(name.strip(), proc.strip() or name.strip())
            self._reload_wl()

    def _del_wl(self):
        items = self.list_wl.selectedItems()
        if items:
            wid = int(items[0].text().rsplit("#", 1)[-1])
            self.wl_dao.delete(wid)
            self._reload_wl()

    def _add_lock(self):
        import re
        start = self.ed_lock_start.text().strip()
        end = self.ed_lock_end.text().strip()
        if not re.match(r'^\d{1,2}:\d{2}$', start) or not re.match(r'^\d{1,2}:\d{2}$', end):
            self._toast("请输入正确的时间格式（如 23:00）")
            return
        self.lock_dao.create(
            start_time=start + ":00",
            end_time=end + ":00")
        self._reload_lock()

    def _del_lock(self):
        items = self.list_lock.selectedItems()
        if items:
            lid = int(items[0].text().rsplit("#", 1)[-1])
            self.lock_dao.delete(lid)
            self._reload_lock()

    def _read_auto_start_from_registry(self) -> bool:
        """从注册表读取开机自启的实际状态。

        以注册表为准（而非 settings_dao），避免用户手动删除注册表项后
        UI 仍显示「已启用」但实际不自启的不一致问题。
        """
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, key_path, 0,
                    winreg.KEY_READ) as key:
                try:
                    winreg.QueryValueEx(key, "QingNingTodo")
                    return True
                except FileNotFoundError:
                    return False
        except ImportError:
            # 非 Windows 平台：回退到 settings_dao
            return self.settings_dao.get("auto_start", "false").lower() == "true"
        except OSError:
            return False

    def _on_auto_start_toggle(self, checked):
        self.settings_dao.set("auto_start", "true" if checked else "false")
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "QingNingTodo"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0,
                winreg.KEY_SET_VALUE)
            try:
                if checked:
                    if getattr(sys, 'frozen', False):
                        # 打包后的 exe：直接运行
                        cmd = f'"{sys.executable}"'
                    else:
                        # 开发环境：用 pythonw.exe（无控制台）运行 main.py
                        pythonw = os.path.join(
                            os.path.dirname(sys.executable), 'pythonw.exe')
                        if not os.path.exists(pythonw):
                            pythonw = sys.executable
                        # settings_page.py 在 src/ui_qt/pages/ 下，
                        # 上溯 3 级 dirname 到达 src/，main.py 就在此目录
                        src_dir = os.path.dirname(
                            os.path.dirname(
                                os.path.dirname(os.path.abspath(__file__))))
                        main_py = os.path.join(src_dir, 'main.py')
                        if not os.path.exists(main_py):
                            self._toast(f"未找到入口文件：{main_py}")
                            # 回滚 UI 状态
                            self.cb_auto_start.blockSignals(True)
                            self.cb_auto_start.setChecked(False)
                            self.cb_auto_start.blockSignals(False)
                            self.settings_dao.set("auto_start", "false")
                            return
                        cmd = f'"{pythonw}" "{main_py}"'
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
        except ImportError:
            self._toast("当前平台不支持开机自启设置")
            # 回滚 UI 状态
            self.cb_auto_start.blockSignals(True)
            self.cb_auto_start.setChecked(not checked)
            self.cb_auto_start.blockSignals(False)
            self.settings_dao.set("auto_start", "true" if not checked else "false")
        except OSError as e:
            self._toast(f"设置开机自启失败：{e}")
            # 回滚 UI 状态
            self.cb_auto_start.blockSignals(True)
            self.cb_auto_start.setChecked(not checked)
            self.cb_auto_start.blockSignals(False)
            self.settings_dao.set("auto_start", "true" if not checked else "false")

    def _edit_shortcut(self):
        text, ok = QInputDialog.getText(
            self, "修改快捷键", "请输入快捷键组合（如 Ctrl+Shift+A）：",
            text=self.settings_dao.get("shortcut_key", "Ctrl+Shift+A"))
        if ok and text.strip():
            self._apply_shortcut(text.strip())

    def _apply_shortcut(self, combo: str):
        """保存快捷键并立即重新注册全局热键（若平台支持）。"""
        combo = (combo or "").strip()
        if not combo:
            return
        self.settings_dao.set("shortcut_key", combo)
        if hasattr(self, "lbl_shortcut"):
            self.lbl_shortcut.setText(combo)
        # 立即重新注册全局热键（若平台支持）
        cb = getattr(self.state, "on_shortcut_change", None)
        if callable(cb):
            try:
                cb(combo)
            except Exception:
                pass
        self._toast("快捷键已保存并全局生效")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出备份", "qingning_backup.json", "JSON (*.json)")
        if not path:
            return
        try:
            tables = ["user", "todo_group", "todo", "focus_record", "goal",
                      "future_plan", "checkin_record", "achievement",
                      "focus_whitelist", "lock_schedule", "settings"]
            dump = {tb: self.state.db.query_all(f"SELECT * FROM `{tb}`")
                    for tb in tables}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, default=str, indent=2)
            self._toast(f"已导出到：{path}")
        except Exception as ex:
            self._toast(f"导出失败：{ex}")

    def _change_db(self):
        """修改数据库后端：支持 SQLite/MySQL 切换，切换时清空历史数据。"""
        t = self._t
        current_backend = self.state.app_config.db_backend

        # 选择后端（使用主题样式）
        items = ["SQLite（本地，免安装）", "MySQL（需配置连接）"]
        current_idx = 1 if current_backend == "mysql" else 0
        choice, ok = QInputDialog.getItem(
            self, "切换数据库",
            "选择数据库后端：",
            items, current_idx, False)
        if not ok:
            return

        # 判断是否实际切换
        want_mysql = "MySQL" in choice
        is_same = (want_mysql and current_backend == "mysql") or \
                  (not want_mysql and current_backend == "sqlite")
        if is_same:
            self._toast("数据库后端未变更。")
            return

        # 二次确认（仅在实际切换时）
        ret = QMessageBox.question(
            None, "确认切换",
            f"切换到 {'MySQL' if want_mysql else 'SQLite'} 将清空所有历史数据"
            f"（待办、专注记录、设置等）。\n\n确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        if want_mysql:
            # MySQL 模式：弹出配置对话框
            from src.ui_qt.dialogs import DBConfigDialog
            from src.config import DBConfig
            existing_cfg = self.state.app_config.load() or DBConfig()
            saved_cfg = [None]

            def on_result(cfg):
                saved_cfg[0] = cfg

            dlg = DBConfigDialog(db_config=existing_cfg, on_result=on_result, parent=self)
            if dlg.exec() and saved_cfg[0]:
                self.state.app_config.save(saved_cfg[0], backend="mysql")
            else:
                return
        else:
            # SQLite 模式
            self.state.app_config.save_backend("sqlite")

        # 清空当前数据库数据
        try:
            db = self.state.db
            tables = ["focus_record", "interrupt_details", "todo", "todo_group",
                      "habit_checkins", "achievement", "settings", "future_plan",
                      "goal", "focus_whitelist", "lock_schedule", "white_noise"]
            for tb in tables:
                try:
                    db.execute(f"DELETE FROM `{tb}`")
                except Exception:
                    pass
            # 重新写入种子数据
            if hasattr(db, '_seed_data'):
                db._seed_data()
        except Exception as ex:
            QMessageBox.warning(None, "数据清理", f"清理历史数据时出错：{ex}")

        self._toast("数据库已切换，请重启应用以使用新的数据库后端。")

    def _clear_cache(self):
        """清除应用缓存（临时文件等）。"""
        reply = QMessageBox.question(
            self, "清除缓存",
            "确定要清除所有缓存数据吗？\n不会影响数据库中的待办和设置。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cache_dir = os.path.join(os.path.expanduser("~"), ".qingning_cache")
                if os.path.isdir(cache_dir):
                    import shutil
                    shutil.rmtree(cache_dir, ignore_errors=True)
                self._toast("缓存已清除")
            except Exception as ex:
                self._toast(f"清除缓存失败：{ex}")

    def _clear_all_data(self):
        """清除所有数据（需二次确认）。"""
        reply1 = QMessageBox.warning(
            self, "危险操作",
            "此操作将清除所有数据（待办、专注记录、设置等），不可恢复！\n\n"
            "确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply1 != QMessageBox.StandardButton.Yes:
            return
        text, ok = QInputDialog.getText(
            self, "最终确认",
            "此操作不可恢复！请输入 DELETE 以确认：")
        if not ok or text.strip() != "DELETE":
            return
        try:
            tables = ["achievement", "checkin_record", "focus_record",
                      "interrupt_details", "todo", "todo_group",
                      "future_plan", "goal", "habit_checkins",
                      "focus_whitelist", "lock_schedule", "settings",
                      "white_noise"]
            for tb in tables:
                try:
                    self.state.db.execute(f"DELETE FROM `{tb}`")
                except Exception:
                    pass
            # 保留 user 表（重置用户信息）
            self.state.db.execute(
                "UPDATE `user` SET nickname='用户' WHERE id=1")
            # 重新播种默认设置，确保应用功能正常
            self.state.db._seed_data()
            self._toast("所有数据已清除，请重启应用")
        except Exception as ex:
            self._toast(f"清除失败：{ex}")

    def _resolve_help_path(self):
        """解析用户版帮助文档（使用说明书.md）的本地路径。

        单文件帮助文档：优先用户版使用说明书，其次技术版 README；
        优先打包资源目录，其次项目根目录。
        """
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        # settings_page.py 位于 src/ui_qt/pages/，向上 3 层到项目根
        project_root = os.path.dirname(os.path.dirname(
            os.path.dirname(here)))
        base = getattr(sys, "_MEIPASS", None)
        candidates = []
        if base:
            # 打包后文档位于独立的 help/ 子目录
            candidates.append(os.path.join(base, "help", "使用说明书.md"))
            candidates.append(os.path.join(base, "help", "README.md"))
        candidates.append(os.path.join(project_root, "使用说明书.md"))
        candidates.append(os.path.join(project_root, "README.md"))
        return next((p for p in candidates if os.path.exists(p) and
                     os.path.isfile(p)), None)

    def _open_help(self):
        """打开帮助文档（本地用户版使用说明书，单文件即帮助文档）。"""
        help_path = self._resolve_help_path()
        if help_path:
            try:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(help_path))
                return
            except Exception:
                pass
        # 兜底：帮助文档缺失时给出简要帮助
        QMessageBox.information(
            self, "帮助",
            "青柠待办 - 专注 · 致远\n\n"
            "待办清单：管理日常任务（双击进入专注计时）\n"
            "专注计时：番茄钟 / 正计时 / 倒计时\n"
            "数据统计：查看专注数据可视化\n"
            "未来计划：规划中长期目标\n\n"
            "详细使用说明见项目根目录 README.md。")

    def _toast(self, msg):
        """P0 修复: 统一调用 src.ui_qt.toast.show_toast,
        使用全局右下角滑出通知 (避免与应用主色调撞色, 与其他页面一致).
        """
        from src.ui_qt.toast import show_toast
        show_toast("提示", msg, duration=2500)
