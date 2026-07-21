"""不依赖 GUI 渲染, 验证主题 QSS 是否完整覆盖原型 1:1 还原的关键视觉点."""
import sys
import os

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.theme import (
    LIGHT, DARK, build_qss, get_current_theme, set_current_theme,
    _build_calendar_qss, _apply_calendar_qss, _ensure_calendar_icon,
    hex_rgba,
)


def assert_in(text: str, needle: str, label: str):
    if needle not in text:
        raise AssertionError(f"[{label}] 缺少关键视觉点: {needle!r}")
    print(f"  ✓ {label}")


def verify_light():
    print("=" * 60)
    print("浅色主题 (Organic Biophilic) 1:1 还原验证")
    print("=" * 60)

    set_current_theme(LIGHT)
    qss = build_qss(LIGHT)

    # ── 核心色值 ──
    assert_in(qss, "#F2F5EE", "1. body 底色 #F2F5EE")
    assert_in(qss, "#5B8A3A", "2. 苔藓绿主色 #5B8A3A")
    assert_in(qss, "#7BAE5C", "3. 翡翠绿 secondary #7BAE5C")
    assert_in(qss, "#C97B3F", "4. 大地橙 accent #C97B3F")
    assert_in(qss, "#2A3A1F", "5. 深森林绿文字 #2A3A1F")
    assert_in(qss, "#6B7A5A", "6. 文字 muted #6B7A5A")

    # ── 圆角 ──
    assert_in(qss, "border-radius: 10px", "7. 圆角 sm=10 (--r-sm)")
    assert_in(qss, "border-radius: 16px", "8. 圆角 md=16 (--r)")
    # 卡片不对称圆角 (light: 24px 8px 24px 8px)
    assert_in(qss, "24px 8px 24px 8px", "9. 卡片不对称圆角 (Organic)")

    # ── 字体 ──
    assert_in(qss, "Fraunces", "10. 标题字体 Fraunces")
    assert_in(qss, "Nunito Sans", "11. 正文字体 Nunito Sans")

    # ── 背景渐变 ──
    assert_in(qss, "qradialgradient", "12. 右上角 radial-gradient 绿色光晕")

    # ── 按钮 ──
    assert_in(qss, "QPushButton#primary", "13. .btn-primary 样式")
    assert_in(qss, "QPushButton#ghost", "14. .btn 幽灵按钮")
    assert_in(qss, "QPushButton#success", "15. .btn-success 成功按钮")
    assert_in(qss, "QPushButton#danger", "16. .btn-danger 危险按钮")
    assert_in(qss, "QPushButton#danger_ghost", "17. .btn-danger.ghost 危险幽灵")

    # ── 表单控件 ──
    assert_in(qss, "QCheckBox::indicator", "18. .chk-box 复选框")
    assert_in(qss, "QRadioButton::indicator", "19. .rad-dot 单选")
    assert_in(qss, "QCheckBox#switch::indicator", "20. .switch 开关 (40x22px)")
    assert_in(qss, "QSlider::groove:horizontal", "21. .slider-track 滑块")
    assert_in(qss, "QSlider::handle:horizontal", "22. .slider-knob 滑块手柄")
    assert_in(qss, "QProgressBar::chunk", "23. .progress 进度条渐变")
    assert_in(qss, "QDateEdit::down-arrow", "24. QDateEdit 嵌入日历图标")

    # ── 表格/列表/树 ──
    assert_in(qss, "QTableWidget", "25. .table 表格")
    assert_in(qss, "QHeaderView::section", "26. .th 表头")
    assert_in(qss, "QListWidget", "27. .list 列表")
    assert_in(qss, "QTreeWidget", "28. 树")

    # ── 导航 ──
    assert_in(qss, "QPushButton#navBtn", "29. 侧栏 navBtn")
    assert_in(qss, "border-left: 3px solid", "30. 选中态左侧指示条")

    # ── Hero ──
    assert_in(qss, "QFrame#heroBanner", "31. .hero 横幅")
    assert_in(qss, "QLabel#heroTitle", "32. .hero 标题")

    # ── 装饰 ──
    assert_in(qss, "QFrame#card", "33. .component-card 卡片")
    assert_in(qss, "QPushButton#chip", "34. .chip 选择芯片")
    assert_in(qss, "QPushButton#chipMuted", "35. .chip-muted")
    assert_in(qss, "QPushButton#chipDashed", "36. .chip-dashed 虚线添加")
    assert_in(qss, "QPushButton#segTab", "37. .tab-bar 分段")
    assert_in(qss, "QLabel#avatar", "38. .avatar 头像")
    assert_in(qss, "QLabel#chipPill", "39. .pill 胶囊徽章")
    assert_in(qss, "QLabel#chipSuccess", "40. .tag-success 成功徽章")
    assert_in(qss, "QLabel#chipWarning", "41. .tag-warning 警告徽章")
    assert_in(qss, "QLabel#chipDanger", "42. .tag-danger 危险徽章")

    # ── 滚动条 ──
    assert_in(qss, "QScrollBar::handle:vertical", "43. ::-webkit-scrollbar 竖向")
    assert_in(qss, "QScrollBar::handle:horizontal", "44. ::-webkit-scrollbar 横向")

    # ── 透明背景 ──
    assert_in(qss, "QMainWindow {", "45. QMainWindow 选择器")
    assert_in(qss, "QWidget#appContent", "46. #appContent 透明背景")

    # ── 日历 ──
    cal_qss = _build_calendar_qss()
    assert_in(cal_qss, "QCalendarWidget", "47. 日历 QSS")
    assert_in(cal_qss, "qt_calendar_navigationbar", "48. 日历导航栏")
    assert_in(cal_qss, "qt_calendar_prevmonth", "49. 日历上一个月按钮")
    # 日历短星期 (一/二/三) 由 QSS 宽度/字号控制 (10-12px)
    assert_in(cal_qss, "font-size: 11px", "50. 短星期字体小号")

    # 日历图标 SVG
    cal_icon = _ensure_calendar_icon(LIGHT)
    assert os.path.exists(cal_icon), f"51. 日历图标 SVG 文件已生成: {cal_icon}"
    print(f"  ✓ 51. 日历图标 SVG: {cal_icon}")

    # 日历图标颜色应使用文字色
    with open(cal_icon, "r", encoding="utf-8") as f:
        svg = f.read()
    assert "#2A3A1F" in svg, "52. 日历图标使用主题文字色 #2A3A1F"
    print("  ✓ 52. 日历图标颜色自适应主题")

    # ── 主背景透出 ──
    assert_in(qss, "background-color: " + LIGHT.bg, "53. body 主背景 = --c-bg")

    print(f"\n  QSS 总长度: {len(qss):,} 字符")
    print(f"  日历 QSS 长度: {len(cal_qss):,} 字符")


def verify_dark():
    print("=" * 60)
    print("深色主题 (Aurora UI) 1:1 还原验证")
    print("=" * 60)

    set_current_theme(DARK)
    qss = build_qss(DARK)

    # ── 核心色值 ──
    assert_in(qss, "#0B1026", "1. body 底色 #0B1026 (深蓝夜空)")
    assert_in(qss, "#818CF8", "2. 靛紫主色 #818CF8")
    assert_in(qss, "#34D399", "3. 翡翠绿 secondary #34D399")
    assert_in(qss, "#F472B6", "4. 霓粉 accent #F472B6")
    assert_in(qss, "#E0E7FF", "5. 月光白文字 #E0E7FF")

    # ── 圆角 ──
    assert_in(qss, "border-radius: 28px", "6. 圆角 lg=28 (Aurora 28px 统一)")

    # ── 字体 ──
    assert_in(qss, "Outfit", "7. 标题字体 Outfit")
    assert_in(qss, "Inter", "8. 正文字体 Inter")

    # ── 极光背景 ──
    assert_in(qss, "qconicalgradient", "9. conic-gradient 极光")
    assert_in(qss, "stop:0.5 " + DARK.secondary, "10. 极光中段 secondary")

    # ── 玻璃卡片 ──
    assert_in(qss, "QFrame#glassCard", "11. 玻璃卡片样式")
    assert_in(qss, "backdrop-blur", "(注释) 玻璃模糊")  # 在注释中

    # ── 状态色 ──
    assert_in(qss, DARK.danger, "12. 霓粉 danger")

    # ── 极光图标 ──
    cal_icon = _ensure_calendar_icon(DARK)
    with open(cal_icon, "r", encoding="utf-8") as f:
        svg = f.read()
    assert "#E0E7FF" in svg, "13. 日历图标使用深色主题文字色 #E0E7FF"
    print("  ✓ 13. 日历图标颜色自适应深色主题")

    # ── 玻璃卡片用半透明 ──
    # #161E40 = rgba(22, 30, 64, ...) —— surface 的 RGB
    assert ("rgba(22" in qss and "0.85" in qss), "14. 玻璃卡片半透明 surface 85%"
    print("  ✓ 14. 玻璃卡片用 surface 85% 透明")

    print(f"\n  QSS 总长度: {len(qss):,} 字符")


def main():
    verify_light()
    print()
    verify_dark()
    print()
    print("=" * 60)
    print("✓ 全部关键视觉点验证通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
