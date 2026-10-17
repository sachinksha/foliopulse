from foliopulse.config import APP_CONFIG
from foliopulse.ui.theme import dashboard_css


def test_css_scales_font_sizes_with_font_scale():
    css = dashboard_css(2.0)
    assert "font-size: 1.70rem" in css   # 0.85 * 2.0 for stat labels
    assert "font-size: 2.90rem" in css   # 1.45 * 2.0 for stat values


def test_css_uses_palette_colors():
    css = dashboard_css(1.0)
    assert APP_CONFIG["COLORS"]["BG_DARK"] in css

