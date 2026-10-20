"""Pure portfolio computation: turns holdings plus market data into table rows.

No Streamlit imports here. The caller supplies the market-data function and a
mutable cache dict (in the app, ``st.session_state.stock_cache``).
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from foliopulse.config import APP_CONFIG
from foliopulse.expenses import compute_trade_expenses_detailed
from foliopulse.models import Holding

HistoryFn = Callable[[str], tuple]  # sym -> (ltp, prev_close, df_10d)


def portfolio_columns() -> list[str]:
    labels = APP_CONFIG["LABELS"]
    return [
        "Symbol", "RawSymbol", "Type", "Instrument", "Status", "Qty", "Avg Buy (₹)", "Invested (₹)",
        "LTP (₹)", "Current Val (₹)", "Weight (%)", labels["SL"], labels["TSL"], labels["T1"], labels["T2"],
        "Day's Gain/Loss", "Day's Gain/Loss (%)", "Expenses (₹)", "Gross P&L (₹)",
        "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)", "Raw_DayPnL", "Raw_PnL",
        "Raw_NetPnL", "Raw_Expenses", "Raw_Invested", "Raw_Current", "df_10d", "Show Chart",
    ]


def build_row(
    holding: Holding,
    ltp: float,
    prev_close: float,
    df_10d: pd.DataFrame,
    status: str,
    total_invested: float,
) -> dict:
    """One table row for a holding at a given price. Pure arithmetic, no I/O."""
    labels = APP_CONFIG["LABELS"]
    qty = holding.quantity
    buy_price = holding.avg_buy_price
    sym = holding.symbol

    invested = buy_price * qty
    exp = compute_trade_expenses_detailed(
        qty, buy_price, ltp, holding.trade_type, holding.instrument_type
    )
    total_exp = exp["total_expenses"]

    day_pnl = (ltp - prev_close) * qty if prev_close > 0 else 0.0
    day_pnl_pct = ((ltp - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

    current = ltp * qty
    gross_pnl = current - invested
    gross_pnl_pct = (gross_pnl / invested * 100) if invested > 0 else 0.0

    net_pnl = gross_pnl - total_exp
    net_pnl_pct = (net_pnl / invested * 100) if invested > 0 else 0.0

    weight_pct = (invested / total_invested * 100) if total_invested > 0 else 0.0

    return {
        "Symbol": sym.replace(".NS", ""),
        "RawSymbol": sym,
        "Type": holding.trade_type,
        "Instrument": holding.instrument_type,
        "Status": status,
        "Qty": qty,
        "Avg Buy (₹)": buy_price,
        "Invested (₹)": round(invested),
        "LTP (₹)": ltp,
        "Current Val (₹)": round(current),
        "Weight (%)": round(weight_pct, 2),
        labels["SL"]: holding.stop_loss,
        labels["TSL"]: holding.trailing_sl,
        labels["T1"]: holding.target_1,
        labels["T2"]: holding.target_2,
        "Day's Gain/Loss": round(day_pnl),
        "Day's Gain/Loss (%)": round(day_pnl_pct, 2),
        "Expenses (₹)": round(total_exp),
        "Gross P&L (₹)": round(gross_pnl),
        "Gross P&L (%)": round(gross_pnl_pct, 2),
        "Net P&L (₹)": round(net_pnl),
        "Net P&L (%)": round(net_pnl_pct, 2),
        "Raw_DayPnL": day_pnl,
        "Raw_PnL": gross_pnl,
        "Raw_NetPnL": net_pnl,
        "Raw_Expenses": total_exp,
        "Raw_Invested": invested,
        "Raw_Current": current,
        "df_10d": df_10d,
        "Show Chart": holding.chart_visible,
    }


def build_portfolio(
    holdings: list[Holding],
    history_fn: HistoryFn,
    cache: dict,
    use_manual_override: bool,
) -> tuple[pd.DataFrame, list[str]]:
    """Build the portfolio table.

    - Manual override: uses ``manual_ltp`` where set, with prices from the cache.
    - Live: calls ``history_fn``; on success the cache is updated.
    - On failure: falls back to the cached values and marks the row Stale.

    Returns the table and a list of error messages for the UI to show.
    """
    if not holdings:
        return pd.DataFrame(columns=portfolio_columns()), []

    total_invested = sum(h.avg_buy_price * h.quantity for h in holdings)
    rows: list[dict] = []
    errors: list[str] = []

    for h in holdings:
        sym = h.symbol
        buy_price = h.avg_buy_price

        if use_manual_override and h.manual_ltp > 0:
            ltp = h.manual_ltp
            status = "🟡 Manual"
            cached = cache.get(sym, {})
            prev_close = cached.get("prev_close", buy_price) or 0.0
            df_10d = cached.get("df_10d", pd.DataFrame())
        else:
            try:
                ltp, prev_close, df_10d = history_fn(sym)
                prev_close = prev_close or 0.0
                status = "🟢 Live"
                cache[sym] = {"ltp": ltp, "prev_close": prev_close, "df_10d": df_10d}
            except Exception as err:  # noqa: BLE001 - any fetch failure marks the row stale
                cached = cache.get(sym, {})
                ltp = cached.get("ltp", buy_price)
                prev_close = cached.get("prev_close", buy_price) or 0.0
                df_10d = cached.get("df_10d", pd.DataFrame())
                status = "🔴 Stale"
                errors.append(f"**{sym}**: {err}")

        rows.append(build_row(h, ltp, prev_close, df_10d, status, total_invested))

    return pd.DataFrame(rows), errors
