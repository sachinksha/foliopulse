import pandas as pd
import pytest

from foliopulse.config import APP_CONFIG
from foliopulse.expenses import INSTRUMENT_MUTUAL_FUND
from foliopulse.models import Holding
from foliopulse.portfolio import build_portfolio, portfolio_columns

LBL = APP_CONFIG["LABELS"]


def holding(symbol="TITAN.NS", buy=100.0, qty=10, **kw):
    return Holding(symbol=symbol, avg_buy_price=buy, quantity=qty, **kw)


def live(ltp=110.0, prev=105.0, df=None):
    df = df if df is not None else pd.DataFrame({"Close": [prev, ltp]}, index=["d1", "d2"])

    def fn(sym):
        return ltp, prev, df

    return fn


def failing(message="rate limited"):
    def fn(sym):
        raise RuntimeError(message)

    return fn


def test_empty_watchlist_gives_empty_table_with_columns():
    df, errors = build_portfolio([], live(), {}, False)
    assert df.empty
    assert list(df.columns) == portfolio_columns()
    assert errors == []


def test_live_row_values_and_cache_update():
    cache = {}
    df, errors = build_portfolio([holding()], live(ltp=110.0, prev=105.0), cache, False)

    row = df.iloc[0]
    assert errors == []
    assert row["Status"] == "🟢 Live"
    assert row["Symbol"] == "TITAN"          # .NS stripped for display
    assert row["RawSymbol"] == "TITAN.NS"
    assert row["Raw_Invested"] == pytest.approx(1000.0)
    assert row["Raw_Current"] == pytest.approx(1100.0)
    assert row["Raw_PnL"] == pytest.approx(100.0)
    assert row["Raw_DayPnL"] == pytest.approx(50.0)     # (110-105)*10
    assert row["Raw_NetPnL"] < row["Raw_PnL"]            # equity charges reduce net P&L
    assert row["Raw_Expenses"] > 0
    assert cache["TITAN.NS"]["ltp"] == 110.0


def test_weight_is_share_of_total_invested():
    holdings = [holding("A.NS", buy=100.0, qty=10), holding("B.NS", buy=100.0, qty=10)]
    df, _ = build_portfolio(holdings, live(), {}, False)
    assert list(df["Weight (%)"]) == [50.0, 50.0]


def test_failed_fetch_uses_cache_and_marks_stale():
    cache = {"TITAN.NS": {"ltp": 120.0, "prev_close": 118.0, "df_10d": pd.DataFrame()}}
    df, errors = build_portfolio([holding()], failing("rate limited"), cache, False)

    row = df.iloc[0]
    assert row["Status"] == "🔴 Stale"
    assert row["LTP (₹)"] == 120.0
    assert errors == ["**TITAN.NS**: rate limited"]


def test_failed_fetch_without_cache_falls_back_to_buy_price():
    df, errors = build_portfolio([holding(buy=100.0)], failing(), {}, False)
    row = df.iloc[0]
    assert row["Status"] == "🔴 Stale"
    assert row["LTP (₹)"] == 100.0
    assert row["Raw_PnL"] == 0.0
    assert len(errors) == 1


def test_manual_override_uses_manual_ltp_without_fetching():
    calls = []

    def fn(sym):
        calls.append(sym)
        return 0.0, 0.0, pd.DataFrame()

    h = holding(manual_ltp=130.0)
    df, errors = build_portfolio([h], fn, {}, True)

    assert calls == []
    assert df.iloc[0]["Status"] == "🟡 Manual"
    assert df.iloc[0]["LTP (₹)"] == 130.0
    assert errors == []


def test_manual_override_without_manual_ltp_falls_through_to_live():
    df, _ = build_portfolio([holding(manual_ltp=0.0)], live(ltp=111.0), {}, True)
    assert df.iloc[0]["Status"] == "🟢 Live"


def test_mutual_fund_has_no_charges_and_gross_equals_net():
    h = holding(instrument_type=INSTRUMENT_MUTUAL_FUND)
    df, _ = build_portfolio([h], live(ltp=110.0), {}, False)
    row = df.iloc[0]
    assert row["Raw_Expenses"] == 0.0
    assert row["Raw_NetPnL"] == row["Raw_PnL"] == pytest.approx(100.0)
    assert row["Instrument"] == INSTRUMENT_MUTUAL_FUND


def test_row_keys_match_table_columns():
    df, _ = build_portfolio([holding()], live(), {}, False)
    assert set(df.columns) == set(portfolio_columns())
    assert LBL["SL"] in df.columns and LBL["T2"] in df.columns
