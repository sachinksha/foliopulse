from datetime import datetime

import pytz

from foliopulse.market_hours import is_market_open

IST = pytz.timezone("Asia/Kolkata")


def at(*args):
    return IST.localize(datetime(*args))


def test_open_during_session():
    # Monday 2026-10-19 10:00 IST
    assert is_market_open(at(2026, 10, 19, 10, 0)) == (True, "Market Open")


def test_session_boundaries_are_inclusive():
    assert is_market_open(at(2026, 10, 19, 9, 15))[0] is True
    assert is_market_open(at(2026, 10, 19, 15, 30))[0] is True


def test_pre_market():
    open_, reason = is_market_open(at(2026, 10, 19, 9, 14))
    assert open_ is False and reason.startswith("Pre-Market")


def test_post_market():
    open_, reason = is_market_open(at(2026, 10, 19, 15, 31))
    assert open_ is False and reason.startswith("Post-Market")


def test_weekend_is_closed():
    # Saturday 2026-10-17
    assert is_market_open(at(2026, 10, 17, 11, 0)) == (False, "Weekend (Market Closed)")


def test_listed_holiday_is_closed():
    # Tuesday 2026-10-20 is in NSE_HOLIDAYS_2026
    assert is_market_open(at(2026, 10, 20, 11, 0)) == (False, "NSE Trading Holiday")


def test_defaults_to_current_time_when_no_argument():
    open_, reason = is_market_open()
    assert isinstance(open_, bool) and isinstance(reason, str)
