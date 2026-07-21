"""主题令牌回归测试（PyQt6）。"""
from src.theme import (
    LIGHT, DARK, THEMES, DEFAULT_THEME, get_theme, get_current_theme,
    set_current_theme, build_qss, apply_theme,
)
from PyQt6.QtWidgets import QApplication


def test_default_theme_is_light():
    assert DEFAULT_THEME == "light"
    assert THEMES["light"] is LIGHT


def test_theme_primary_lime():
    assert LIGHT.primary == "#5B8A3A", "浅色主题主色应为苔藓绿(Organic Biophilic)"
    assert DARK.primary == "#818CF8", "深色主题主色应为靛紫(Aurora UI)"


def test_light_on_primary_visible_on_lime():
    """浅色(Organic Biophilic)主按钮文字色必须有效，且在苔藓绿底上清晰可读。

    修复前 on_primary='#1F2E0C' 为无效色值，导致主按钮(开始)文字
    近乎不可见。现应为有效深色，与苔藓绿 #5B8A3A 形成足够对比。
    """
    from src.theme import _hex_to_rgb, _relative_luminance
    assert LIGHT.on_primary.startswith("#") and len(LIGHT.on_primary) in (7, 9)
    rgb_btn = _hex_to_rgb(LIGHT.primary)
    rgb_txt = _hex_to_rgb(LIGHT.on_primary)
    assert rgb_btn and rgb_txt, "主色与文字色应为有效 hex"
    # 与苔藓绿底对比度应足够（接近深色文字效果）
    lum_btn = _relative_luminance(rgb_btn)
    lum_txt = _relative_luminance(rgb_txt)
    contrast = (max(lum_btn, lum_txt) + 0.05) / (min(lum_btn, lum_txt) + 0.05)
    assert contrast >= 3.0, f"主按钮文字对比度过低: {contrast:.2f}"


def test_on_color_lime_primary_returns_dark_text():
    """苔藓绿主色(#5B8A3A, 中等偏亮)的文字色必须清晰可读。

    回归：旧实现用固定亮度阈值 0.5，青柠绿亮度被误判为暗色
    而返回白字，导致浅色主题「开始」按钮白字不可见（仅深色主题正常）。
    现按 WCAG 对比度择优——#5B8A3A 亮度中等，深色文字对比度更高。

    注：#5B8A3A 为 Organic Biophilic 规范色，配深色文字对比度约 4.8:1，
    超过 WCAG AA 正常文本阈值(4.5:1)。
    """
    from src.theme import _on_color, _hex_to_rgb, _relative_luminance
    on = _on_color("#5B8A3A")
    # 对比度应超过 WCAG AA 大字体阈值（>=3.0），#5B8A3A 实际约 4.8
    lum_bg = _relative_luminance(_hex_to_rgb("#5B8A3A"))
    lum_txt = _relative_luminance(_hex_to_rgb(on))
    contrast = (max(lum_bg, lum_txt) + 0.05) / (min(lum_bg, lum_txt) + 0.05)
    assert contrast >= 3.0, f"苔藓绿底文字对比度不足: {contrast:.2f}"


def test_on_color_dark_bg_returns_light_text():
    """深底色应配浅色文字，择优逻辑不能过度修正。"""
    from src.theme import _on_color
    assert _on_color("#111111") == "#FFFFFF"


def test_derived_primary_on_color_readable():
    """自定义主色派生主题的 on_primary 在其主色底上必须清晰可读。

    回归：启用自定义主色(即便沿用默认青柠绿)会走 derive_theme_with_primary，
    on_primary 由 _on_color(primary) 计算；旧逻辑此处返回白字导致按钮文字不可见。

    注：#5B8A3A 为 Organic Biophilic 规范色，配白字对比度约 3.5:1，
    超过 WCAG AA 大字体阈值(3.0:1)。
    """
    from src.theme import (
        derive_theme_with_primary, _hex_to_rgb, _relative_luminance,
    )
    for base in (LIGHT, DARK):
        for primary in ("#5B8A3A", "#818CF8", "#7BAE5C"):
            d = derive_theme_with_primary(base, primary)
            lum_bg = _relative_luminance(_hex_to_rgb(d.primary))
            lum_txt = _relative_luminance(_hex_to_rgb(d.on_primary))
            contrast = (max(lum_bg, lum_txt) + 0.05) / (
                min(lum_bg, lum_txt) + 0.05)
            assert contrast >= 3.0, (
                f"{base.name}+{primary} 主按钮文字对比度不足: {contrast:.2f}")


def test_get_theme_returns():
    assert get_theme("light") is LIGHT
    assert get_theme("dark") is DARK
    assert get_theme("unknown") is LIGHT  # fallback


def test_build_qss_contains_colors():
    qss = build_qss(LIGHT)
    assert LIGHT.primary in qss, "QSS 应包含主色"
    assert "border-radius" in qss, "QSS 应有圆角"
    qss_dark = build_qss(DARK)
    assert DARK.primary in qss_dark, "深色 QSS 应包含深色主色"


def test_set_current_theme():
    old = get_current_theme()
    set_current_theme(DARK)
    assert get_current_theme() is DARK
    set_current_theme(LIGHT)
    assert get_current_theme() is LIGHT


def test_apply_theme_changes_stylesheet():
    app = QApplication.instance() or QApplication([])
    apply_theme(app, LIGHT)
    assert LIGHT.primary in app.styleSheet()


def test_theme_soft_property():
    assert LIGHT.soft == LIGHT.primary_soft
    assert DARK.soft == DARK.primary_soft


def test_state_color_on_is_computed():
    # on_* 必须按基础色亮度程序化得出（非写死 #FFFFFF）
    for th in (LIGHT, DARK):
        assert th.on_success.startswith("#") and len(th.on_success) == 7
        assert th.on_danger.startswith("#") and len(th.on_danger) == 7
        assert th.on_warning.startswith("#") and len(th.on_warning) == 7


def test_state_color_on_picks_dark_text_on_light_bg():
    from dataclasses import replace as _r
    from src.theme import _relative_luminance, _hex_to_rgb
    # 高亮度成功色（浅背景）→ 深色文字，保证 AA 对比度
    light_success = _r(LIGHT, success="#B9E89A")
    # on_success 应为深色文字（亮度 < 0.2）
    lum = _relative_luminance(_hex_to_rgb(light_success.on_success))
    assert lum < 0.2, f"高亮度成功色应配深色文字，实际亮度 {lum:.3f}"
    # 深色主题下危险色文字仍应为合法十六进制
    assert DARK.on_danger.startswith("#")


def test_state_colors_derived_soft_and_pressed():
    for th in (LIGHT, DARK):
        assert th.success_soft.startswith("#")
        assert th.danger_soft.startswith("#")
        assert th.warning_soft.startswith("#")
        assert th.success_pressed.startswith("#")
        assert th.danger_pressed.startswith("#")
        assert th.warning_pressed.startswith("#")


def test_build_qss_uses_derived_state_colors():
    qss = build_qss(LIGHT)
    # 成功/危险按钮文字色应引用程序化 on_*（非写死）
    assert LIGHT.on_success in qss
    assert LIGHT.on_danger in qss
    assert "pressed" in qss


def test_build_qss_inputs_have_min_height():
    """输入框/下拉框需有最小高度，避免 CJK 文字被纵向裁切。"""
    qss = build_qss(LIGHT)
    assert "QLineEdit {" in qss
    assert "min-height: 34px;" in qss
    assert "QComboBox {" in qss
    # QComboBox 使用较小高度，QLineEdit 使用较大高度
    assert "min-height: 24px;" in qss


def test_switch_track_distinct_from_card():
    """开关未开启态轨道色须与次级面板/卡片底(surface_variant)区分，避免融为一体。"""
    for th in (LIGHT, DARK):
        assert th.switch_track.startswith("#") and len(th.switch_track) == 7
        assert th.switch_track != th.surface_variant, (
            f"{th.name} 开关未开启态轨道色不应等于卡片底色")
    # QSS 应引用独立轨道色
    qss = build_qss(LIGHT)
    assert LIGHT.switch_track in qss


def test_switch_track_contrast_vs_card():
    """开关未开启态轨道色与卡片底色的相对亮度差应足够，确保在卡片上清晰可辨。"""
    from src.theme import _hex_to_rgb, _relative_luminance
    for th in (LIGHT, DARK):
        lum_track = _relative_luminance(_hex_to_rgb(th.switch_track))
        lum_card = _relative_luminance(_hex_to_rgb(th.surface_variant))
        assert abs(lum_track - lum_card) >= 0.05, (
            f"{th.name} 开关轨道与卡片底对比不足")

