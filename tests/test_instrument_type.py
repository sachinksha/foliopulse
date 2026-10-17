import pytest
from foliopulse.expenses import (
    INSTRUMENT_EQUITY,
    INSTRUMENT_MUTUAL_FUND,
    INSTRUMENT_SIF,
    compute_trade_expenses_detailed,
    price_for_target_net_pnl_pct,
)


@pytest.mark.parametrize("instrument", [INSTRUMENT_MUTUAL_FUND, INSTRUMENT_SIF])
def test_non_equity_instruments_have_no_charges(instrument):
    res = compute_trade_expenses_detailed(100, 50.0, 55.0, "DELIVERY", instrument)
    assert res["total_expenses"] == 0.0
    assert res["stt"] == 0.0
    assert res["dp_charges"] == 0.0
    assert res["breakeven_price"] == 50.0
    assert res["gross_pnl"] == 500.0
    assert res["net_pnl"] == 500.0


def test_equity_default_unchanged_when_instrument_omitted():
    explicit = compute_trade_expenses_detailed(270, 2857.56, 2695.02, "DELIVERY", INSTRUMENT_EQUITY)
    default = compute_trade_expenses_detailed(270, 2857.56, 2695.02, "DELIVERY")
    assert explicit == default
    assert default["total_expenses"] == pytest.approx(1687.42, abs=0.01)


def test_target_price_for_mutual_fund_has_no_charge_drag():
    # With no charges, +5% net should be exactly +5% gross.
    assert price_for_target_net_pnl_pct(10, 100.0, 5, "DELIVERY", INSTRUMENT_MUTUAL_FUND) == 105.0


def test_unknown_instrument_falls_back_to_equity():
    res = compute_trade_expenses_detailed(270, 2857.56, 2695.02, "DELIVERY", "SOMETHING_ELSE")
    assert res["total_expenses"] > 0
