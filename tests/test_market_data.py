from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
import pytz

from foliopulse.market_data import fetch_index_quotes, get_history, search_symbols

IST = pytz.timezone("Asia/Kolkata")


class FakeTicker:
    """Stands in for yfinance.Ticker."""

    def __init__(self, symbol, daily=None, last=110.0, prev=100.0, fail_fast=False):
        self.symbol = symbol
        self._daily = daily
        self._last = last
        self._prev = prev
        self._fail_fast = fail_fast

    @property
    def fast_info(self):
        if self._fail_fast:
            raise RuntimeError("no fast info")
        return SimpleNamespace(last_price=self._last, previous_close=self._prev)

    def history(self, period, interval):
        if interval == "5m":
            return pd.DataFrame()  # no intraday patch in these tests
        return self._daily


def daily_frame(days, closes=None):
    closes = closes or [100 + i for i in range(len(days))]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes],
            "Close": closes,
            "Volume": [1000] * len(days),
        },
        index=pd.DatetimeIndex(pd.to_datetime(days)),
    )


# ---------- get_history ----------

def test_get_history_returns_ltp_prev_close_and_last_10_days():
    days = [f"2026-10-{d:02d}" for d in range(1, 15)]  # 14 weekdays/weekends, fine for the test
    frame = daily_frame(days)
    now = IST.localize(datetime(2026, 10, 16, 10, 0))  # before 16:00 -> target is 15 Oct

    ltp, prev, df = get_history(
        "TITAN.NS",
        ticker_factory=lambda s: FakeTicker(s, daily=frame, last=111.0, prev=108.0),
        now=now,
    )
    assert ltp == 111.0
    assert prev == 108.0
    assert len(df) == 10
    assert list(df.index)[-1] == "2026-10-14"


def test_get_history_falls_back_to_last_close_when_fast_info_fails():
    frame = daily_frame(["2026-10-12", "2026-10-13"], closes=[200.0, 205.0])
    now = IST.localize(datetime(2026, 10, 16, 10, 0))
    ltp, prev, _ = get_history(
        "X.NS",
        ticker_factory=lambda s: FakeTicker(s, daily=frame, fail_fast=True),
        now=now,
    )
    assert ltp == 205.0
    assert prev == 200.0


def test_get_history_raises_on_empty_history():
    now = IST.localize(datetime(2026, 10, 16, 10, 0))
    with pytest.raises(ValueError, match="empty history"):
        get_history(
            "X.NS",
            ticker_factory=lambda s: FakeTicker(s, daily=pd.DataFrame()),
            now=now,
        )


# ---------- search_symbols ----------

class FakeSearch:
    def __init__(self, quotes):
        self._quotes = quotes

    def __call__(self, query, max_results):
        return SimpleNamespace(quotes=self._quotes)


def test_search_formats_display_and_skips_missing_symbols():
    quotes = [
        {"symbol": "TITAN.NS", "shortname": "Titan Company", "exchDisp": "NSE", "quoteType": "EQUITY"},
        {"symbol": "", "shortname": "ghost"},
        {"symbol": "0P0000XVAA.BO", "longname": "Some Fund", "exchange": "BSE", "quoteType": "MUTUALFUND"},
    ]
    results = search_symbols("titan", search=FakeSearch(quotes))
    assert [r["symbol"] for r in results] == ["TITAN.NS", "0P0000XVAA.BO"]
    assert results[0]["display"] == "Titan Company (TITAN.NS) — NSE"
    assert results[1]["quote_type"] == "MUTUALFUND"


def test_search_ignores_short_queries():
    assert search_symbols("a", search=FakeSearch([{"symbol": "X"}])) == []
    assert search_symbols("", search=FakeSearch([{"symbol": "X"}])) == []


def test_search_returns_empty_on_error():
    def boom(query, max_results):
        raise RuntimeError("network down")

    assert search_symbols("titan", search=boom) == []


# ---------- fetch_index_quotes ----------

def test_index_quotes_compute_change_and_zero_on_failure():
    def factory(symbol):
        if symbol == "^NSEBANK":
            raise RuntimeError("unavailable")
        return FakeTicker(symbol, last=110.0, prev=100.0)

    indices = {"Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
    result = fetch_index_quotes(indices, ticker_factory=factory)

    assert result["Sensex"]["val"] == 110.0
    assert result["Sensex"]["chg"] == pytest.approx(10.0)
    assert result["Sensex"]["pct"] == pytest.approx(10.0)
    assert result["Bank Nifty"] == {"val": 0.0, "chg": 0.0, "pct": 0.0}
