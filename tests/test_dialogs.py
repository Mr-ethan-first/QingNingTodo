"""对话框回归测试（PyQt6 offscreen）。

重点覆盖「更多待办设置」对话框：
- 构造不报错，且不再设置 background:transparent 导致底部按钮 QSS 失效（历史 BUG）；
- 底部「关闭 / 保存」按钮存在并使用与全局一致的 primary/ghost 样式；
- 保存逻辑正确回写 values（含自定义休息时长换算）。
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QPushButton, QDialog

from src.theme import get_current_theme
from src.ui_qt.dialogs import MoreTodoSettingsDialog, WhiteNoiseDialog
from src.ui_qt.widgets import TweenSlider


# 进程级唯一的 QApplication（offscreen），测试期间持续保活，避免控件被提前销毁
_APP = QApplication.instance() or QApplication([])


def _make_dialog(init_values=None):
    theme = get_current_theme()
    return MoreTodoSettingsDialog(theme, init_values, parent=None)


def _find_button(dlg, name):
    return dlg.findChild(QPushButton, name)


def test_more_settings_constructs():
    dlg = _make_dialog()
    assert dlg is not None
    assert dlg.windowTitle() == "更多待办设置"


def test_more_settings_no_transparent_stylesheet():
    """回归：根因是 self.setStyleSheet('background:transparent') 破坏了
    QPushButton#primary/#ghost 的 QSS 层叠，使底部保存按钮不可见。"""
    dlg = _make_dialog()
    assert "background:transparent" not in dlg.styleSheet()
    # 继承 _CardDialog，通过卡片容器呈现圆角背景，而非窗口级透明样式
    assert dlg.findChild(QPushButton, "primary") is not None
    assert dlg.findChild(QPushButton, "ghost") is not None


def test_more_settings_bottom_buttons_styled_consistently():
    """底部「关闭 / 保存」按钮使用全局 ghost/primary 样式且文本正确。"""
    dlg = _make_dialog()
    save_btn = _find_button(dlg, "primary")
    close_btn = _find_button(dlg, "ghost")
    assert save_btn is not None and save_btn.text() == "保存"
    assert close_btn is not None and close_btn.text() == "关闭"


def test_more_settings_save_roundtrip():
    """保存按钮回写 values：复选框与自定义休息时长（分钟→秒）换算正确。"""
    dlg = _make_dialog()
    dlg.sw_hide_after.setChecked(True)
    dlg.sw_exempt_amway.setChecked(True)
    dlg.sw_loop.setChecked(True)

    # 启用自定义休息时长并设为 10 分钟
    dlg._cb_custom_break.setChecked(True)
    dlg.sp_custom_break.setValue(10)

    dlg._on_confirm()
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.values["hide_after_complete"] == 1
    assert dlg.values["is_amway_mode_exempted"] == 1
    assert dlg.values["loop_enabled"] == 1
    assert dlg.values["custom_break_duration"] == 10 * 60


def test_more_settings_custom_break_defaults_off():
    """未设置自定义休息时长时，cb 默认不勾选且值保持 None。"""
    dlg = _make_dialog()
    dlg._on_confirm()
    assert dlg.values["custom_break_duration"] is None


def test_more_settings_init_custom_break_restored():
    """传入既有 custom_break_duration 时，复选框应勾选且滑块/输入框还原分钟数。"""
    dlg = _make_dialog({"custom_break_duration": 15 * 60})
    assert dlg._cb_custom_break.isChecked() is True
    assert dlg.sp_custom_break.value() == 15
    assert dlg.sp_custom_break.isEnabled() is True
    assert dlg._slider_break.isEnabled() is True


def test_more_settings_slider_is_tween():
    # 休息时长滑块应升级为带补间动画的 TweenSlider
    dlg = _make_dialog()
    assert isinstance(dlg._slider_break, TweenSlider)


def test_more_settings_slider_sync_on_init():
    # 构造期（窗口不可见）TweenSlider 走同步 setValue，初值应等于数字框，
    # 保证程序化取值断言不受补间动画影响
    dlg = _make_dialog({"custom_break_duration": 15 * 60})
    assert dlg._slider_break.value() == dlg.sp_custom_break.value() == 15


def _make_todo_dialog(db, todo=None):
    """构造待办对话框（需真实 state）。"""
    from src.config import AppConfig
    from src.theme import DEFAULT_THEME
    from src.ui_qt.state import AppState
    from src.ui_qt.dialogs import TodoDialog
    state = AppState(db, AppConfig(), DEFAULT_THEME)
    return TodoDialog(state, todo=todo, parent=None)


def test_todo_dialog_bg_picker_buttons_content_sized(db):
    """背景图「选择图片/清除」按钮按内容自适应宽度。

    修复前用 setMinimumWidth 固定最小宽度，行宽不足时文字被截断、
    且与相邻按钮视觉重叠；改为 Minimum 尺寸策略后恰好包裹文字+图标，
    多余空间由文件名标签吸收，互不遮挡。
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QSizePolicy
    dlg = _make_todo_dialog(db)
    btns = [b for b in dlg.findChildren(QPushButton)
            if b.text() in ("选择图片", "清除")]
    assert len(btns) == 2
    for b in btns:
        assert b.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Minimum
        assert b.minimumWidth() <= 0  # 未写死最小宽度


# ==================== 待办对话框：标签/字段对齐与铺满（修复 Issue 1-3） ====================

def _label_font_rule(lbl):
    """从样式表中解析 font-size 数值（px）。"""
    ss = lbl.styleSheet()
    import re
    m = re.search(r"font-size:\s*(\d+)px", ss)
    return int(m.group(1)) if m else None


def test_todo_dialog_field_labels_consistent(db):
    """字段标签字号与下拉框文本(基础字号14px)一致，且左对齐。"""
    from PyQt6.QtCore import Qt
    from src.tokens import type_scale
    dlg = _make_todo_dialog(db)
    base = type_scale.base  # 全局输入框/下拉框文本字号
    # 定目标面板：目标类型 / 计时模式
    dlg._switch_tab(2)
    type_row = dlg._goal_panel.layout().itemAt(1).layout()
    timer_row = dlg._goal_panel.layout().itemAt(3).layout()
    lbl_type = type_row.itemAt(0).widget()
    lbl_timer = timer_row.itemAt(0).widget()
    assert _label_font_rule(lbl_type) == base
    assert _label_font_rule(lbl_timer) == base
    assert lbl_type.alignment() & Qt.AlignmentFlag.AlignLeft
    # 养习惯面板：频率 / 目标量 / 计时模式
    dlg._switch_tab(1)
    freq_row = dlg._habit_panel.layout().itemAt(1).layout()
    amt_row = dlg._habit_panel.layout().itemAt(2).layout()
    lbl_freq = freq_row.itemAt(0).widget()
    lbl_amt = amt_row.itemAt(0).widget()
    assert _label_font_rule(lbl_freq) == base
    assert _label_font_rule(lbl_amt) == base
    assert lbl_amt.text() == "目标量"  # 目标量已移到标签位置


def test_todo_dialog_num_label_matches_combobox(db):
    """_num 配置标签(专注时长/目标时长)字号与上方下拉框(未分类)一致。"""
    from src.tokens import type_scale
    dlg = _make_todo_dialog(db)
    base = type_scale.base
    # 普通面板：专注时长 _num 标签（应与上方「未分类」下拉框文本同为基准字号）
    dlg._switch_tab(0)
    dur_row = dlg._normal_panel.layout().itemAt(2).widget().layout()
    lbl_dur = dur_row.itemAt(0).widget()
    assert _label_font_rule(lbl_dur) == base
    # 定目标面板：目标时长 _num 标签（应与上方「目标类型」标签同为基准字号）
    dlg._switch_tab(2)
    goal_dur_row = dlg._goal_panel.layout().itemAt(2).widget().layout()
    lbl_goal_dur = goal_dur_row.itemAt(0).widget()
    assert _label_font_rule(lbl_goal_dur) == base


def test_todo_dialog_comboboxes_fill_width(db):
    """字段下拉框/输入框铺满编辑框宽度（stretch=1，无固定最小宽）。"""
    from PyQt6.QtWidgets import QSizePolicy, QComboBox
    dlg = _make_todo_dialog(db)
    dlg._switch_tab(0)
    # 普通面板：分组 + 计时模式 同行各占半宽
    row1 = dlg._normal_panel.layout().itemAt(1).layout()
    assert row1.stretch(row1.indexOf(dlg.cb_group)) == 1
    assert row1.stretch(row1.indexOf(dlg.cb_timer)) == 1
    assert dlg.cb_group.minimumWidth() == 0  # 不再写死 min_w=200
    # 定目标面板：目标类型铺满
    dlg._switch_tab(2)
    type_row = dlg._goal_panel.layout().itemAt(1).layout()
    assert type_row.stretch(type_row.indexOf(dlg.cb_goal_type)) == 1


def test_todo_dialog_num_labels_left_aligned(db):
    """专注时长/休息时长/循环次数/目标时长标签左对齐（即便同行是滑块/输入框）。"""
    from PyQt6.QtCore import Qt
    dlg = _make_todo_dialog(db)
    dlg._switch_tab(0)
    normal = dlg._normal_panel.layout()
    # 普通面板：专注时长 / 休息时长 / 循环次数（_num 容器位于 itemAt 2/3/4）
    for idx in (2, 3, 4):
        row = normal.itemAt(idx).widget().layout()
        lbl = row.itemAt(0).widget()
        assert lbl.alignment() & Qt.AlignmentFlag.AlignLeft, \
            f"普通面板第 {idx} 行标签未左对齐"
    # 定目标面板：目标时长（_num 容器位于 itemAt(2)）
    dlg._switch_tab(2)
    goal = dlg._goal_panel.layout()
    goal_dur_row = goal.itemAt(2).widget().layout()
    lbl_goal = goal_dur_row.itemAt(0).widget()
    assert lbl_goal.alignment() & Qt.AlignmentFlag.AlignLeft, \
        "定目标面板目标时长标签未左对齐"



# ==================== 白噪音弹窗对齐（修复：末尾噪音/自定义按钮与上方不等宽） ====================

def _fake_noise_dao(items):
    """返回仅实现 list() 的伪造白噪音 DAO。"""
    class _F:
        def list(self):
            return items
    return _F()


def _fake_settings(values=None):
    v = values or {}

    class _S:
        def get(self, k, d=""):
            return v.get(k, d)
    return _S()


def _stretch_of(dlg, btn):
    """查找 btn 所在子布局中它的水平 stretch（用于校验等宽）。"""
    lay = dlg._items_lay
    for i in range(lay.count()):
        sub = lay.itemAt(i).layout()
        if sub is None:
            continue
        idx = sub.indexOf(btn)
        if idx != -1:
            return sub.stretch(idx)
    return None


def test_white_noise_last_odd_button_half_width():
    """奇数个音源时，末位单独成行的噪音按钮应与上方 2 列芯片等宽。"""
    noises = [
        {"id": 1, "name": "雨声", "file_path": "p1", "category": "自然音"},
        {"id": 2, "name": "风声", "file_path": "p2", "category": "自然音"},
    ]
    dlg = WhiteNoiseDialog(_fake_noise_dao(noises), _fake_settings(), None, None)
    last = [b for b in dlg.findChildren(QPushButton) if b.text() == "风声"][0]
    # 末位单独成行：与上方 2 列芯片同占半列（stretch=1）
    assert _stretch_of(dlg, last) == 1


def test_white_noise_custom_button_half_width():
    """自定义上传按钮应与上方芯片等宽（半列），不再被压缩成内容宽度。"""
    noises = [
        {"id": 1, "name": "雨声", "file_path": "p1", "category": "自然音"},
        {"id": 2, "name": "风声", "file_path": "p2", "category": "自然音"},
    ]
    dlg = WhiteNoiseDialog(_fake_noise_dao(noises), _fake_settings(), None, None)
    upload = dlg.findChild(QPushButton, "chipDashed")
    assert upload is not None
    assert _stretch_of(dlg, upload) == 1

