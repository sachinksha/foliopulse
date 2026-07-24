import json
import os
import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# --- PAGE SETUP ---
st.set_page_config(page_title="Indian Stock Portfolio Tracker", layout="wide")

# --- CONFIG MANAGEMENT ---
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "refresh_seconds": 10,
    "watchlist": [
        {"symbol": "RELIANCE.NS", "avg_buy_price": 2400.0, "quantity": 10},
        {"symbol": "TCS.NS", "avg_buy_price": 3800.0, "quantity": 5},
        {"symbol": "INFY.NS", "avg_buy_price": 1450.0, "quantity": 15},
    ],
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


config_data = load_config()

# --- SIDEBAR: AUTO-REFRESH & CONFIG CONTROL ---
st.sidebar.header("⚙️ Settings")

refresh_rate = st.sidebar.slider(
    "Auto-Refresh Interval (seconds)",
    min_value=5,
    max_value=60,
    value=config_data.get("refresh_seconds", 10),
)

# Trigger auto-refresh
count = st_autorefresh(
    interval=refresh_rate * 1000, key="stock_refresh"
)

# --- DATA FETCHING ENGINE ---
@st.cache_data(ttl=2)  # Cache briefly to prevent rate limits
def get_portfolio_metrics(watchlist):
    tickers = [item["symbol"] for item in watchlist]
    data = yf.Tickers(" ".join(tickers))

    rows = []
    total_investment = 0.0
    total_current_value = 0.0

    for item in watchlist:
        sym = item["symbol"]
        buy_price = item["avg_buy_price"]
        qty = item["quantity"]

        try:
            info = data.tickers[sym].fast_info
            ltp = round(info.last_price, 2)
        except Exception:
            ltp = 0.0

        invested = buy_price * qty
        current = ltp * qty
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

        total_investment += invested
        total_current_value += current

        rows.append(
            {
                "Symbol": sym.replace(".NS", ""),
                "Qty": qty,
                "Avg Buy (₹)": buy_price,
                "LTP (₹)": ltp,
                "Invested (₹)": round(invested, 2),
                "Current Val (₹)": round(current, 2),
                "P&L (₹)": round(pnl, 2),
                "P&L (%)": round(pnl_pct, 2),
            }
        )

    df = pd.DataFrame(rows)
    total_pnl = total_current_value - total_investment
    total_pnl_pct = (
        (total_pnl / total_investment * 100) if total_investment > 0 else 0.0
    )

    summary = {
        "invested": round(total_investment, 2),
        "current": round(total_current_value, 2),
        "pnl": round(total_pnl, 2),
        "pnl_pct": round(total_pnl_pct, 2),
    }

    return df, summary


# Fetch fresh data
df, summary = get_portfolio_metrics(config_data["watchlist"])

# --- HEADER METRICS SUMMARY ---
st.title("📈 Live Indian Stock Monitor")
st.caption(f"Last updated loop count: {count} | Refresh rate: {refresh_rate}s")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Invested", f"₹{summary['invested']:,}")
col2.metric("Current Value", f"₹{summary['current']:,}")
col3.metric(
    "Total P&L (₹)",
    f"₹{summary['pnl']:,}",
    delta=f"₹{summary['pnl']:,}",
    delta_color="normal",
)
col4.metric(
    "Total Return (%)",
    f"{summary['pnl_pct']}%",
    delta=f"{summary['pnl_pct']}%",
    delta_color="normal",
)

st.divider()

# --- TABLE VIEW WITH CONDITIONAL COLORING ---
st.subheader("📋 Stock Breakdown")


# Color helper for pandas table styling
def color_pnl(val):
    if val > 0:
        return "color: #00CC96; font-weight: bold;"
    elif val < 0:
        return "color: #FF2B2B; font-weight: bold;"
    return ""


styled_df = df.style.map(color_pnl, subset=["P&L (₹)", "P&L (%)"]).format(
    {
        "Avg Buy (₹)": "{:.2f}",
        "LTP (₹)": "{:.2f}",
        "Invested (₹)": "{:,.2f}",
        "Current Val (₹)": "{:,.2f}",
        "P&L (₹)": "{:,.2f}",
        "P&L (%)": "{:+.2f}%",
    }
)

st.dataframe(styled_df, use_container_width=True, hide_index=True)