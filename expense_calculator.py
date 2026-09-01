import math


def _round_nearest_rupee(value: float) -> float:
    return float(round(value))


def _round_two_decimals(value: float) -> float:
    return round(value + 1e-9, 2)


def compute_trade_expenses_detailed(
    qty: int, buy_price: float, sell_price: float, trade_type: str = "DELIVERY"
) -> dict:
    if qty <= 0 or buy_price <= 0:
        return {
            "brokerage": 0.0,
            "stamp_duty": 0.0,
            "stt": 0.0,
            "sebi_fee": 0.0,
            "txn_charges": 0.0,
            "gst": 0.0,
            "contract_note_charges": 0.0,
            "dp_charges": 0.0,
            "total_expenses": 0.0,
            "breakeven_price": round(buy_price, 2),
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
        }

    qty = abs(int(qty))
    buy_price = float(buy_price)
    sell_price = float(sell_price)
    is_intraday = trade_type.upper().strip() == "INTRADAY"

    buy_turnover = round(qty * buy_price, 2)
    sell_turnover = round(qty * sell_price, 2)

    # --- BUY LEG ---
    if is_intraday:
        b_buy = min(20.0, buy_turnover * 0.0003)
        stamp_duty_buy = _round_nearest_rupee(buy_turnover * 0.00003)
        stt_buy = 0.0
    else:  # DELIVERY
        b_buy = 0.0
        stamp_duty_buy = _round_nearest_rupee(buy_turnover * 0.00015)
        stt_buy = _round_nearest_rupee(buy_turnover * 0.001)

    sebi_buy = buy_turnover * 0.000001
    txn_buy = buy_turnover * 0.0000307
    gst_buy = (b_buy + txn_buy + sebi_buy) * 0.18

    # --- SELL LEG ---
    if is_intraday:
        b_sell = min(20.0, sell_turnover * 0.0003)
        stamp_duty_sell = 0.0
        stt_sell = _round_nearest_rupee(sell_turnover * 0.00025)
    else:  # DELIVERY
        b_sell = 0.0
        stamp_duty_sell = 0.0
        stt_sell = _round_nearest_rupee(sell_turnover * 0.001)

    sebi_sell = sell_turnover * 0.000001
    txn_sell = sell_turnover * 0.0000307
    gst_sell = (b_sell + txn_sell + sebi_sell) * 0.18

    # Aggregations
    brokerage = b_buy + b_sell
    stamp_duty = stamp_duty_buy + stamp_duty_sell
    stt = stt_buy + stt_sell
    sebi_fee = sebi_buy + sebi_sell
    txn_charges = txn_buy + txn_sell
    gst = gst_buy + gst_sell

    contract_note_charges = brokerage + stamp_duty + stt + sebi_fee + txn_charges + gst
    dp_charges = 0.0 if is_intraday else 15.34
    total_expenses = contract_note_charges + dp_charges

    gross_pnl = sell_turnover - buy_turnover
    net_pnl = gross_pnl - total_expenses

    # Compute exact dynamic breakeven price matching target_pct=0 solver
    be_price = buy_price
    for _ in range(5):
        s_turn = qty * be_price
        if is_intraday:
            b_s = min(20.0, s_turn * 0.0003)
            stt_s = _round_nearest_rupee(s_turn * 0.00025)
        else:
            b_s = 0.0
            stt_s = _round_nearest_rupee(s_turn * 0.001)
        sebi_s = s_turn * 0.000001
        txn_s = s_turn * 0.0000307
        gst_s = (b_s + txn_s + sebi_s) * 0.18
        tot_exp_be = (b_buy + stamp_duty_buy + sebi_buy + stt_buy + txn_buy + gst_buy) + \
                     (b_s + stt_s + sebi_s + txn_s + gst_s) + dp_charges
        be_price = buy_price + (tot_exp_be / qty)

    return {
        "brokerage": _round_two_decimals(brokerage),
        "stamp_duty": _round_two_decimals(stamp_duty),
        "stt": _round_two_decimals(stt),
        "sebi_fee": _round_two_decimals(sebi_fee),
        "txn_charges": _round_two_decimals(txn_charges),
        "gst": _round_two_decimals(gst),
        "contract_note_charges": _round_two_decimals(contract_note_charges),
        "dp_charges": _round_two_decimals(dp_charges),
        "total_expenses": _round_two_decimals(total_expenses),
        "breakeven_price": _round_two_decimals(be_price),
        "gross_pnl": _round_two_decimals(gross_pnl),
        "net_pnl": _round_two_decimals(net_pnl),
    }

def price_for_target_net_pnl_pct(
    qty: int,
    buy_price: float,
    target_net_pct: float = 0.0,
    trade_type: str = "DELIVERY",
    **kwargs
) -> float:
    """Calculates target sell price required to achieve a desired net P&L percentage after trade expenses."""
    if "target_pct" in kwargs:
        target_net_pct = float(kwargs["target_pct"])

    if qty <= 0 or buy_price <= 0:
        return round(buy_price, 2)

    sell_price = buy_price * (1.0 + (target_net_pct / 100.0))

    # Iterative convergence for exact target price inclusive of expenses
    for _ in range(10):
        exp = compute_trade_expenses_detailed(qty, buy_price, sell_price, trade_type)
        gross_pnl = (sell_price - buy_price) * qty
        current_net_pct = ((gross_pnl - exp["total_expenses"]) / (buy_price * qty)) * 100.0
        diff = target_net_pct - current_net_pct

        if abs(diff) < 1e-4:
            break

        sell_price += (diff / 100.0) * buy_price

    return round(sell_price, 2)