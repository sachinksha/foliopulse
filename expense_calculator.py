import math

DELIVERY_CONFIG = {
    "brokerageFlat": 0.01,
    "brokeragePercentage": 0,
    "brokerageMax": 0,
    "sttPercentage": 0.001,
    "txnChargePercentage": 0.0000307,
    "sebiChargePercentage": 0.000001,
    "stampDutyPercentage": 0.00015,
    "gstPercentage": 0.18,
    "dpCharge": 15.34,
}

INTRADAY_CONFIG = {
    "brokerageFlat": 0,
    "brokeragePercentage": 0.0003,
    "brokerageMax": 20,
    "sttPercentage": 0.00025,
    "txnChargePercentage": 0.0000307,
    "sebiChargePercentage": 0.000001,
    "stampDutyPercentage": 0.00003,
    "gstPercentage": 0.18,
    "dpCharge": 0,
}


def _round_nearest_rupee(value: float) -> int:
    return math.floor(value + 0.5)


def _round_two_decimals(value: float) -> float:
    return round(value + 1e-9, 2)


def _calculate_leg_expenses(value: float, config: dict, is_buy: bool, is_intraday: bool) -> float:
    if is_intraday:
        brokerage = min(config["brokerageMax"], value * config["brokeragePercentage"])
    else:
        brokerage = config["brokerageFlat"] if is_buy else 0

    stamp_duty = _round_nearest_rupee(value * config["stampDutyPercentage"]) if is_buy else 0
    sebi = value * config["sebiChargePercentage"]

    if is_intraday:
        stt = _round_nearest_rupee(value * config["sttPercentage"]) if not is_buy else 0
    else:
        stt = _round_nearest_rupee(value * config["sttPercentage"])

    txn = value * config["txnChargePercentage"]
    gst = (brokerage + txn + sebi) * config["gstPercentage"]
    return brokerage + stamp_duty + sebi + stt + txn + gst


def compute_trade_expenses_detailed(qty: int, buy_price: float, sell_price: float, trade_type: str = "DELIVERY") -> dict:
    if qty <= 0 or buy_price <= 0:
        return {
            "contract_note_charges": 0.0,
            "dp_charges": 0.0,
            "total_expenses": 0.0,
            "breakeven_price": round(buy_price, 2)
        }

    config = INTRADAY_CONFIG if trade_type.upper().strip() == "INTRADAY" else DELIVERY_CONFIG
    buy_value = qty * buy_price
    sell_value = qty * sell_price

    buy_expenses = _calculate_leg_expenses(buy_value, config, is_buy=True, is_intraday=(trade_type.upper().strip() == "INTRADAY"))
    sell_expenses = _calculate_leg_expenses(sell_value, config, is_buy=False, is_intraday=(trade_type.upper().strip() == "INTRADAY"))

    contract_note_levies = buy_expenses + sell_expenses
    dp_charges = 0.0 if trade_type.upper().strip() == "INTRADAY" else config["dpCharge"]
    # Delivery DP charge applies only on the sell leg and is already GST-inclusive (₹13 + 18% GST = ₹15.34).
    total_expenses = contract_note_levies + dp_charges
    breakeven_price = buy_price + (total_expenses / qty)

    return {
        "contract_note_charges": _round_two_decimals(contract_note_levies),
        "dp_charges": _round_two_decimals(dp_charges),
        "total_expenses": _round_two_decimals(total_expenses),
        "breakeven_price": _round_two_decimals(breakeven_price),
    }


def price_for_target_net_pnl_pct(qty: int, buy_price: float, target_pct: float, trade_type: str = "DELIVERY") -> float:
    """
    Returns the sell price at which net P&L (after all expenses) would equal
    `target_pct` percent of the invested capital (qty * buy_price).

    Pass a negative target_pct for a stop-loss price (e.g. -2 for a 2% net
    loss) and a positive target_pct for a target price (e.g. 5 for a 5% net
    gain).

    Sell-side expenses depend on the sell price itself, so this estimates
    them once using a naive price guess (buy_price shifted by target_pct)
    rather than solving iteratively -- the same approximation
    compute_trade_expenses_detailed's own breakeven_price already relies on.
    The resulting error is negligible (a few paise) for stop-loss/target
    style price bands, since sell-side charges are a small percentage of
    trade value. At target_pct=0 this returns exactly the same price as
    breakeven_price.
    """
    if qty <= 0 or buy_price <= 0:
        return round(buy_price, 2)

    invested = qty * buy_price
    naive_price = buy_price * (1 + target_pct / 100)
    exp = compute_trade_expenses_detailed(qty, buy_price, naive_price, trade_type)

    target_net_pnl = (target_pct / 100) * invested
    price = buy_price + (target_net_pnl + exp["total_expenses"]) / qty
    return _round_two_decimals(price)
