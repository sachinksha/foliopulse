import pandas as pd
import pytest

from foliopulse.expenses import INSTRUMENT_EQUITY, INSTRUMENT_MUTUAL_FUND, INSTRUMENT_SIF
from foliopulse.models import (
    Holding,
    default_show_chart,
    preserved_chart_flag,
    resolve_show_chart,
    set_chart_visibility,
)
from foliopulse.portfolio import build_portfolio


# ---------- defaults ----------

def test_equity_charts_shown_by_default():
    assert default_show_chart(INSTRUMENT_EQUITY) is True
    assert Holding(symbol="TITAN.NS", avg_buy_price=1, quantity=1).chart_visible is True


@pytest.mark.parametrize("instrument", [INSTRUMENT_MUTUAL_FUND, INSTRUMENT_SIF])
def test_fund_and_sif_charts_hidden_by_default(instrument):
    assert default_show_chart(instrument) is False
    h = Holding(symbol="0P0000XVAA.BO", avg_buy_price=1, quantity=1, instrument_type=instrument)
    assert h.chart_visible is False


def test_explicit_choice_overrides_default_both_ways():
    assert resolve_show_chart(True, INSTRUMENT_MUTUAL_FUND) is True
    assert resolve_show_chart(False, INSTRUMENT_EQUITY) is False
    assert resolve_show_chart(None, INSTRUMENT_EQUITY) is True


def test_unknown_instrument_defaults_to_hidden_only_when_not_equity():
    # Unknown values are treated as non-equity, so charts start hidden.
    assert default_show_chart("SOMETHING_ELSE") is False


# ---------- JSON round trip ----------

def test_old_items_without_flag_keep_no_show_chart_key():
    raw = {"symbol": "LT.NS", "avg_buy_price": 2400.0, "quantity": 10}
    h = Holding.from_dict(raw)
    assert h.show_chart is None
    assert "show_chart" not in h.to_dict()


def test_explicit_flag_is_written_to_dict_and_read_back():
    raw = {"symbol": "X", "avg_buy_price": 1.0, "quantity": 1, "instrument_type": "MUTUAL_FUND",
           "show_chart": True}
    h = Holding.from_dict(raw)
    assert h.chart_visible is True
    assert h.to_dict()["show_chart"] is True


def test_string_flag_from_hand_edited_json_is_parsed():
    assert Holding.from_dict({"symbol": "X", "avg_buy_price": 1, "quantity": 1,
                              "show_chart": "false"}).show_chart is False
    assert Holding.from_dict({"symbol": "X", "avg_buy_price": 1, "quantity": 1,
                              "show_chart": "true"}).show_chart is True


# ---------- saving a choice ----------

def test_set_chart_visibility_records_choice_and_reports_change():
    watchlist = [{"symbol": "A.NS"}, {"symbol": "B.NS"}]
    assert set_chart_visibility(watchlist, "B.NS", False) is True
    assert watchlist[1]["show_chart"] is False
    assert "show_chart" not in watchlist[0]


def test_set_chart_visibility_is_noop_when_unchanged():
    watchlist = [{"symbol": "A.NS", "show_chart": True}]
    assert set_chart_visibility(watchlist, "A.NS", True) is False


def test_set_chart_visibility_unknown_symbol_changes_nothing():
    watchlist = [{"symbol": "A.NS"}]
    assert set_chart_visibility(watchlist, "ZZZ.NS", True) is False
    assert watchlist == [{"symbol": "A.NS"}]


# ---------- preserving through edits ----------

def test_preserved_flag_carries_explicit_choice_only():
    assert preserved_chart_flag({"symbol": "A", "show_chart": False}) == {"show_chart": False}
    assert preserved_chart_flag({"symbol": "A"}) == {}


def test_edit_that_rewrites_row_keeps_chart_choice():
    old = {"symbol": "A.NS", "avg_buy_price": 1, "quantity": 1, "show_chart": False}
    rewritten = {"symbol": "A.NS", "avg_buy_price": 2, "quantity": 5, **preserved_chart_flag(old)}
    assert Holding.from_dict(rewritten).chart_visible is False


# ---------- portfolio table ----------

def test_portfolio_row_reports_resolved_chart_visibility():
    holdings = [
        Holding(symbol="TITAN.NS", avg_buy_price=100, quantity=1),
        Holding(symbol="0P0000XVAA.BO", avg_buy_price=100, quantity=1,
                instrument_type=INSTRUMENT_MUTUAL_FUND),
        Holding(symbol="SIFX.BO", avg_buy_price=100, quantity=1,
                instrument_type=INSTRUMENT_SIF, show_chart=True),
    ]

    def fn(sym):
        return 105.0, 100.0, pd.DataFrame()

    df, _ = build_portfolio(holdings, fn, {}, False)
    assert list(df["Show Chart"]) == [True, False, True]
