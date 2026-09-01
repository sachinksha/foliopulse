import json
import pytest
from expense_calculator import compute_trade_expenses_detailed

def load_fixtures():
    with open("tests/fixtures/trades.json") as f:
        return json.load(f)

@pytest.mark.parametrize("trade", load_fixtures())
def test_gas_python_parity(trade):
    res = compute_trade_expenses_detailed(
        qty=trade["qty"],
        buy_price=trade["buy_price"],
        sell_price=trade["sell_price"],
        trade_type=trade["trade_type"]
    )
    
    exp = trade["expected"]
    for key, expected_val in exp.items():
        assert res[key] == pytest.approx(expected_val, abs=0.01), (
            f"Mismatch in '{trade['name']}' for '{key}': "
            f"Python returned {res[key]}, expected {expected_val}"
        )