"""Presentation rules for the main portfolio table. No Streamlit imports."""

from __future__ import annotations

from numbers import Real

import pandas as pd

from foliopulse.config import APP_CONFIG

FOCUS_VIEW = "🔍 Main Focus View"
DETAIL_VIEW = "📋 Full Detail View"
TOGGLE_HEADER = "📈 Chart"

TYPE_BADGE_VALUES = ("DELIVERY", "INTRADAY")
PNL_COLUMNS = ("Gross P&L (₹)", "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)")
INTEGER_COLUMNS = ("Invested (₹)", "Current Val (₹)", "Expenses (₹)")


def price_columns(labels: dict | None = None) -> tuple:
    labels = labels or APP_CONFIG["LABELS"]
    return ("Avg Buy (₹)", "LTP (₹)", labels["SL"], labels["TSL"], labels["T1"], labels["T2"])


def view_columns(preset: str, labels: dict | None = None) -> list[str]:
    """Columns shown for a table preset, in display order."""
    labels = labels or APP_CONFIG["LABELS"]
    if preset == FOCUS_VIEW:
        return ["Symbol", "Qty", "Avg Buy (₹)", "LTP (₹)", "Net P&L (₹)", "Net P&L (%)"]
    return [
        "Symbol", "Type", "Qty", "Avg Buy (₹)", "Invested (₹)", "LTP (₹)", "Current Val (₹)",
        "Weight (%)", labels["SL"], labels["TSL"], labels["T1"], labels["T2"],
        "Expenses (₹)", "Gross P&L (₹)", "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)",
    ]


def _is_number(value) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def format_cell(col: str, value, labels: dict | None = None) -> tuple[str, str]:
    """Return (html_text, css_style) for one table cell."""
    colors = APP_CONFIG["COLORS"]

    if _is_missing(value):
        return "-", ""

    if col == "Type" and value in TYPE_BADGE_VALUES:
        badge = (
            "<span style='font-size:0.8em; padding:2px 5px; border-radius:3px; "
            "background-color:#1E293B; color:#A1A1AA;'>" + str(value) + "</span>"
        )
        return badge, ""

    if col in PNL_COLUMNS and _is_number(value):
        color = colors["PROFIT_GREEN"] if value >= 0 else colors["LOSS_RED"]
        sign = "+" if value >= 0 else ""
        if "₹" in col:
            text = f"{sign}₹{abs(round(value)):,}" if value >= 0 else f"-₹{abs(round(value)):,}"
        else:
            text = f"{value:+.2f}%"
        return text, f"color: {color}; font-weight: bold;"

    if col in price_columns(labels):
        return (f"₹{value:,.2f}" if _is_number(value) else "-"), ""

    if col in INTEGER_COLUMNS:
        return (f"₹{round(value):,}" if _is_number(value) else "-"), ""

    if col == "Weight (%)":
        return (f"{value:.1f}%" if _is_number(value) else "-"), ""

    return str(value), ""
