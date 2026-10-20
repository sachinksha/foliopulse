from foliopulse.expenses import INSTRUMENT_EQUITY, INSTRUMENT_MUTUAL_FUND, INSTRUMENT_SIF
from foliopulse.models import Holding, instrument_from_quote_type, instrument_index


def test_from_dict_applies_defaults_for_older_entries():
    h = Holding.from_dict({"symbol": "LT.NS", "avg_buy_price": 2400, "quantity": 10})
    assert h.trade_type == "DELIVERY"
    assert h.instrument_type == INSTRUMENT_EQUITY
    assert h.stop_loss == 0.0
    assert h.manual_ltp == 0.0


def test_from_dict_normalises_case_and_types():
    h = Holding.from_dict({
        "symbol": "X", "avg_buy_price": "100.5", "quantity": "3",
        "trade_type": " intraday ", "instrument_type": "mutual_fund",
    })
    assert h.avg_buy_price == 100.5
    assert h.quantity == 3
    assert h.trade_type == "INTRADAY"
    assert h.instrument_type == INSTRUMENT_MUTUAL_FUND


def test_to_dict_round_trips():
    original = {
        "symbol": "TITAN.NS", "avg_buy_price": 3400.0, "quantity": 15,
        "trade_type": "DELIVERY", "instrument_type": INSTRUMENT_SIF,
        "stop_loss": 3200.0, "trailing_sl": 3300.0, "target_1": 4800.0,
        "target_2": 4900.0, "manual_ltp": 3500.0,
    }
    assert Holding.from_dict(original).to_dict() == original


def test_holding_is_immutable():
    h = Holding(symbol="X", avg_buy_price=1.0, quantity=1)
    try:
        h.quantity = 5
    except Exception:
        return
    raise AssertionError("Holding should be frozen")


def test_instrument_from_quote_type():
    assert instrument_from_quote_type("MUTUALFUND") == INSTRUMENT_MUTUAL_FUND
    assert instrument_from_quote_type("mutualfund") == INSTRUMENT_MUTUAL_FUND
    assert instrument_from_quote_type("EQUITY") == INSTRUMENT_EQUITY
    assert instrument_from_quote_type("ETF") == INSTRUMENT_EQUITY
    assert instrument_from_quote_type(None) == INSTRUMENT_EQUITY


def test_instrument_index():
    assert instrument_index(INSTRUMENT_SIF) == 2
    assert instrument_index("NOT_A_TYPE") == 0
