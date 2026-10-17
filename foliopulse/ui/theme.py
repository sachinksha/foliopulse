"""Dashboard CSS, parameterised by the chart/UI font scale."""


from foliopulse.config import APP_CONFIG


def dashboard_css(font_scale: float) -> str:
    """Return the <style> block used across the dashboard."""
    return f"""
    <style>
        header[data-testid="stHeader"] {{
            opacity: 0;
            transition: opacity 0.25s ease-in-out;
            z-index: 999999;
        }}
        header[data-testid="stHeader"]:hover {{
            opacity: 1;
        }}

        .block-container {{
            padding-top: 0.4rem !important;
            padding-bottom: 0.4rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            max-width: 100% !important;
        }}

        div[data-testid="stVerticalBlock"] {{
            gap: 0.25rem !important;
        }}

        div[data-testid="stExpanderDetails"] {{
            padding: 0rem 0.2rem 0.2rem 0.2rem !important;
        }}

        .stat-card {{
            background-color: {APP_CONFIG["COLORS"]["BG_DARK"]};
            padding: 0.4rem 0.6rem;
            border-radius: 6px;
            border-width: 2px;
            border-style: solid;
            text-align: left;
            margin-bottom: 0.2rem;
        }}
        .stat-label {{
            font-size: {0.85 * font_scale:.2f}rem;
            color: {APP_CONFIG["COLORS"]["TEXT_MUTED"]};
            font-weight: 700;
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: {1.45 * font_scale:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
            margin-top: 0.05rem;
            white-space: nowrap;
        }}

        .index-card {{
            background-color: {APP_CONFIG["COLORS"]["BG_CARD"]};
            padding: 0.4rem 0.6rem;
            border-radius: 6px;
            border: 1px solid {APP_CONFIG["COLORS"]["BORDER_CARD"]};
            text-align: right;
            margin-bottom: 0.2rem;
        }}
        .index-label {{
            font-size: {0.85 * font_scale:.2f}rem;
            color: #A3B8CC;
            font-weight: 700;
        }}
        .index-val {{
            font-size: {1.25 * font_scale:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
            white-space: nowrap;
        }}
        .index-chg {{
            font-size: {0.9 * font_scale:.2f}rem;
            font-weight: 700;
            white-space: nowrap;
        }}
    </style>
"""
