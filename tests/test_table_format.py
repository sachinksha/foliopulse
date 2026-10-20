import math

import pandas as pd
import pytest

from foliopulse.config import APP_CONFIG
from foliopulse.table_format import (
    DETAIL_VIEW,
    FOCUS_VIEW,
    format_cell,
    price_columns,
    view_columns,
)

LBL = APP_CONFIG["LABELS"]
GREEN = APP_CONFIG["COLORS"]["PROFIT_GREEN"]
RED = APP_CONFIG["COLORS"]["LOSS_RED"]


# ---------- column sets ----------

def test_focus_view_has_seven_day_to_day_columns_without_chart_switch():
    cols = view_columns(FOCUS_VIEW)
    assert cols == ["Symbol", "Qty", "Avg Buy (₹)", "LTP (₹)", "Net P&L (₹)", "Net P&L (%)"]


def test_detail_view_includes_risk_levels_and_type():
    cols = view_columns(DETAIL_VIEW)
    assert "Type" in cols
    assert LBL["SL"] in cols and LBL["T2"] in cols
    assert len(cols) == 17


def test_price_columns_follow_labels():
    assert LBL["SL"] in price_columns() and LBL["T1"] in price_columns()


# ---------- missing values ----------

@pytest.mark.parametrize("value", [None, float("nan"), pd.NA])
def test_missing_values_show_dash(value):
    assert format_cell("LTP (₹)", value) == ("-", "")


# ---------- prices, integers, percentages ----------

def test_price_two_decimals_with_grouping():
    assert format_cell("LTP (₹)", 3500)[0] == "₹3,500.00"
    assert format_cell("Avg Buy (₹)", 2400.5)[0] == "₹2,400.50"


def test_price_column_non_number_shows_dash():
    assert format_cell("LTP (₹)", "abc") == ("-", "")


def test_integer_totals_rounded():
    assert format_cell("Invested (₹)", 1000.4)[0] == "₹1,000"
    assert format_cell("Expenses (₹)", 1687.6)[0] == "₹1,688"


def test_weight_one_decimal_percent():
    assert format_cell("Weight (%)", 33.333)[0] == "33.3%"


def test_plain_columns_stringified():
    assert format_cell("Qty", 10) == ("10", "")
    assert format_cell("Symbol", "TITAN") == ("TITAN", "")


# ---------- P&L colouring ----------

def test_positive_rupee_pnl_is_green_with_plus_sign():
    text, style = format_cell("Net P&L (₹)", 1234.4)
    assert text == "+₹1,234"
    assert GREEN in style and "bold" in style


def test_negative_rupee_pnl_is_red_with_minus_sign():
    text, style = format_cell("Net P&L (₹)", -1234.6)
    assert text == "-₹1,235"
    assert RED in style


def test_percent_pnl_shows_sign_and_two_decimals():
    assert format_cell("Net P&L (%)", 2.5)[0] == "+2.50%"
    assert format_cell("Net P&L (%)", -0.456)[0] == "-0.46%"


def test_zero_pnl_counts_as_profit_colour():
    assert GREEN in format_cell("Gross P&L (₹)", 0.0)[1]


def test_numpy_numbers_format_like_python_numbers():
    import numpy as np

    assert format_cell("Net P&L (₹)", np.int64(500))[0] == "+₹500"
    assert format_cell("LTP (₹)", np.float64(10.5))[0] == "₹10.50"


# ---------- type badge ----------

def test_delivery_and_intraday_get_badge():
    text, _ = format_cell("Type", "DELIVERY")
    assert "DELIVERY" in text and "<span" in text


def test_summary_type_dash_is_plain():
    assert format_cell("Type", "-") == ("-", "")
