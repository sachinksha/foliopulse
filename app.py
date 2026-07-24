from datetime import datetime
import json
import logging
import os
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- PAGE SETUP ---
st.set_page_config(
    page_title="FolioPulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- INJECT CUSTOM CSS FOR TOP HEADER TITLE, CARD BORDERS, & COMPACT LAYOUT ---
st.markdown(
    """
    <style>
        header[data-testid="stHeader"]::before {
            content: "📈 FolioPulse — Live Portfolio & Risk Monitor";
            position: absolute;
            left: 3.5rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.15rem;
            font-weight: 700;
            color: inherit;
            white-space: nowrap;
            z-index: 999999;
            font-family: Source Sans Pro, sans-serif;
        }

        .block-container {
            padding-top: 2.8rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.3rem !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }

        div[data-testid="stDataFrame"] {
            width: 100% !important;
            overflow-x: auto !important;
        }

        .section-subhdr {
            font-size: 1.05rem !important;
            font-weight: 600;
            margin-top: 0.2rem !important;
            margin-bottom: 0.2rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "refresh_seconds": 10,
    "watchlist": [
        {
            "symbol": "M&MFIN.NS",
            "avg_buy_price": 280.00,
            "quantity": 100,
            "stop_loss": 260.00,
            "trailing_sl": 270.00,
            "target_1": 310.00,
            "target_2": 330.00,
            "manual_ltp": 0.0,
        },
        {
            "symbol": "TITAN.NS",
            "avg_buy_price": 3400.00,
            "quantity": 15,
            "stop_loss": 3200.00,
            "trailing_sl": 3300.00,
            "target_1": 3700.00,
            "target_2": 3900.00,
            "manual_ltp": 3450.00,
        },
        {
            "symbol": "ABB.NS",
            "avg_buy_price": 7800.00,
            "quantity": 5,
            "stop_loss": 7300.00,
            "trailing_sl": 7500.00,
            "target_1": 8400.00,
            "target_2": 8800.00,
            "manual_ltp": 0.0,
        },
        {
            "symbol": "NESTLEIND.NS",
            "avg_buy_price": 2450.00,
            "quantity": 20,
            "stop_loss": 2300.00,
            "trailing_sl": 2380.00,
            "target_1": 2650.00,
            "target_2": 2800.00,
            "manual_ltp": 0.0,
        },
        {
            "symbol": "HCLTECH.NS",
            "avg_buy_price": 1500.00,
            "quantity": 30,
            "stop_loss": 1400.00,
            "trailing_sl": 1450.00,
            "target_1": 1650.00,
            "target_2": 1750.00,
            "manual_ltp": 0.0,
        },
    ],
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config.json: {e}")
        return DEFAULT_CONFIG


def save_config(config_dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_dict, f, indent=2)


if "config" not in st.session_state:
    st.session_state.config = load_config()

if "stock_cache" not in st.session_state:
    st.session_state.stock_cache = {}


# --- SMART INDIAN MARKET HOURS DETECTOR ---
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31", 
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", 
    "2026-06-26", "2026-08-26", "2026-09-14", "2026-10-02", 
    "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25"
}


def is_market_open():
    """Checks if current time in Asia/Kolkata falls within NSE/BSE trading hours."""
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    if now.weekday() in (5, 6):
        return False, "Weekend (Market Closed)"

    date_str = now.strftime("%Y-%m-%d")
    if date_str in NSE_HOLIDAYS_2026:
        return False, "NSE Trading Holiday"

    time_minutes = now.hour * 60 + now.minute
    open_minutes = 9 * 60 + 15
    close_minutes = 15 * 60 + 30

    if open_minutes <= time_minutes <= close_minutes:
        return True, "Market Open"
    elif time_minutes < open_minutes:
        return False, "Pre-Market (Opens 09:15 AM)"
    else:
        return False, "Post-Market (Closed 03:30 PM)"


# --- SIDEBAR CONTROLS & MANAGEMENT ---
st.sidebar.title("⚙️ Controls")

# Master Switch: Manual Override
manual_override_active = st.sidebar.toggle(
    "🟡 Enable Manual Price Override",
    value=False,
    help="When ON, live polling is paused and user-fed prices take total priority.",
)

market_is_open, market_reason = is_market_open()

refresh_rate = st.sidebar.slider(
    "Refresh Interval (s)",
    min_value=5,
    max_value=60,
    value=10,
    disabled=manual_override_active,
)

# Auto-pause logic: Paused if Manual Override is ON OR Market is Closed
if manual_override_active:
    market_paused = True
    pause_reason = "MANUAL OVERRIDE ACTIVE"
else:
    market_paused = st.sidebar.toggle(
        "⏸️ Pause Polling (Market Closed)",
        value=(not market_is_open),
        help=f"Detected Status: {market_reason}",
    )
    pause_reason = market_reason.upper()

st.sidebar.divider()
st.sidebar.subheader("📊 Chart Format")

chart_cols_per_row = st.sidebar.select_slider(
    "Grid Columns",
    options=[1, 2, 3],
    value=2,
)

auto_zoom_risk_range = st.sidebar.toggle(
    "🔍 Auto-Zoom Range (SL to Target 2)",
    value=True,
)

st.sidebar.divider()
st.sidebar.subheader("🛠️ Management & Overrides")

# Sidebar Accordion 1: Quick Manual Price Override Inputs
with st.sidebar.expander("✏️ Quick Manual Price Inputs", expanded=manual_override_active):
    st.caption("Feed custom prices. Pre-filled with API values when auto-polling runs.")
    for idx, item in enumerate(st.session_state.config["watchlist"]):
        sym_clean = item["symbol"].replace(".NS", "")
        curr_manual = float(item.get("manual_ltp", 0.0))
        new_val = st.number_input(
            f"{sym_clean} Manual LTP (₹)",
            min_value=0.0,
            value=curr_manual,
            step=0.5,
            key=f"manual_{sym_clean}",
        )
        if new_val != curr_manual:
            st.session_state.config["watchlist"][idx]["manual_ltp"] = new_val
            save_config(st.session_state.config)
            st.rerun()

# Sidebar Accordion 2: Config JSON Editor
with st.sidebar.expander("⚙️ Watchlist JSON Editor", expanded=False):
    config_str = st.text_area(
        "Config JSON",
        value=json.dumps(st.session_state.config, indent=2),
        height=180,
    )
    if st.button("💾 Save Config JSON", type="primary"):
        try:
            parsed = json.loads(config_str)
            st.session_state.config = parsed
            save_config(parsed)
            st.success("Config saved!")
            st.rerun()
        except Exception as err:
            st.error(f"JSON Error: {err}")


# Trigger auto-refresh only when NOT paused
if not market_paused:
    count = st_autorefresh(interval=refresh_rate * 1000, key="portfolio_autorefresh")
else:
    count = 0

# Status Banner Callout
if manual_override_active:
    st.warning(
        "🟡 **MANUAL OVERRIDE ACTIVE**: Automatic API polling is **TOTAL PAUSED**. Portfolio & charts are using user-fed prices."
    )
elif market_paused:
    st.error(
        f"🛑 **LIVE UPDATES PAUSED ({pause_reason})**: Polling is suspended to rest API. Will auto-resume when market opens."
    )


# --- FETCH 10-DAY DAILY CANDLESTICK HISTORY ---
def get_10day_history(sym):
    ticker_obj = yf.Ticker(sym)
    df_daily = ticker_obj.history(period="15d", interval="1d")

    if df_daily.empty:
        raise ValueError("Empty history dataframe returned")

    df_daily.index = df_daily.index.strftime("%Y-%m-%d")
    df_10d = df_daily.tail(10)

    try:
        fast_info = ticker_obj.fast_info
        ltp = round(float(fast_info.last_price), 2)
        method = "fast_info"
    except Exception:
        ltp = round(float(df_10d["Close"].iloc[-1]), 2)
        method = "history_fallback"

    return ltp, df_10d, method


def fetch_portfolio_data(watchlist, use_manual_override):
    now_str = datetime.now().strftime("%H:%M:%S")
    rows = []
    fetch_errors = []
    config_updated = False

    total_invested = sum(
        item["avg_buy_price"] * item["quantity"] for item in watchlist
    )

    for idx, item in enumerate(watchlist):
        sym = item["symbol"]
        buy_price = float(item["avg_buy_price"])
        qty = int(item["quantity"])
        sl = float(item.get("stop_loss", 0.0))
        tsl = float(item.get("trailing_sl", 0.0))
        t1 = float(item.get("target_1", 0.0))
        t2 = float(item.get("target_2", 0.0))
        manual_ltp = float(item.get("manual_ltp", 0.0))

        invested = buy_price * qty

        # Priority Check: Is Manual Override Switch ON?
        if use_manual_override and manual_ltp > 0:
            ltp = manual_ltp
            status = "🟡 Manual"
            cached = st.session_state.stock_cache.get(sym, {})
            df_10d = cached.get("df_10d", pd.DataFrame())
        else:
            # API Mode Active: Fetch live data & pre-fill manual LTP
            try:
                ltp, df_10d, method = get_10day_history(sym)
                status = "🟢 Live"
                updated_time = now_str

                # Auto Pre-fill manual_ltp in session config with latest live API price
                if item.get("manual_ltp") != ltp:
                    st.session_state.config["watchlist"][idx]["manual_ltp"] = ltp
                    config_updated = True

                st.session_state.stock_cache[sym] = {
                    "ltp": ltp,
                    "df_10d": df_10d,
                    "updated_time": updated_time,
                }
            except Exception as err:
                df_10d = pd.DataFrame()
                if manual_ltp > 0:
                    ltp = manual_ltp
                    status = "🟡 Manual Fallback"
                else:
                    cached = st.session_state.stock_cache.get(sym, {})
                    ltp = cached.get("ltp", buy_price)
                    df_10d = cached.get("df_10d", df_10d)
                    status = "🔴 Stale"

                fetch_errors.append(
                    f"**{sym}**: Fetch failed ({err}). Showing LTP: ₹{ltp}"
                )

        current = ltp * qty
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        weight_pct = (invested / total_invested * 100) if total_invested > 0 else 0.0

        sl_pnl = (sl - buy_price) * qty if sl > 0 else 0.0
        sl_pnl_pct = ((sl - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

        tsl_pnl = (tsl - buy_price) * qty if tsl > 0 else 0.0
        tsl_pnl_pct = ((tsl - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

        t1_pnl = (t1 - buy_price) * qty if t1 > 0 else 0.0
        t1_pnl_pct = ((t1 - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

        t2_pnl = (t2 - buy_price) * qty if t2 > 0 else 0.0
        t2_pnl_pct = ((t2 - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

        rows.append(
            {
                "Symbol": sym.replace(".NS", ""),
                "RawSymbol": sym,
                "Status": status,
                "Qty": qty,
                "Avg Buy (₹)": buy_price,
                "LTP (₹)": ltp,
                "P&L (₹)": round(pnl, 2),
                "P&L (%)": round(pnl_pct, 2),
                "Stop Loss": sl,
                "SL P&L (₹)": f"₹{sl_pnl:,.2f} ({sl_pnl_pct:+.1f}%)",
                "Trailing SL": tsl,
                "TSL P&L (₹)": f"₹{tsl_pnl:,.2f} ({tsl_pnl_pct:+.1f}%)",
                "Target 1": t1,
                "T1 P&L (₹)": f"₹{t1_pnl:,.2f} ({t1_pnl_pct:+.1f}%)",
                "Target 2": t2,
                "T2 P&L (₹)": f"₹{t2_pnl:,.2f} ({t2_pnl_pct:+.1f}%)",
                "Invested (₹)": round(invested, 2),
                "Current Val (₹)": round(current, 2),
                "Weight (%)": round(weight_pct, 2),
                "Raw_PnL": pnl,
                "Raw_Invested": invested,
                "Raw_Current": current,
                "df_10d": df_10d,
            }
        )

    # Save auto pre-filled values to disk
    if config_updated and not use_manual_override:
        save_config(st.session_state.config)

    return pd.DataFrame(rows), fetch_errors


df, error_logs = fetch_portfolio_data(
    st.session_state.config["watchlist"], manual_override_active
)

if error_logs:
    with st.expander("⚠️ System Logs", expanded=False):
        for log in error_logs:
            st.markdown(f"- {log}")

# --- TOP SUMMARY METRICS ---
tot_invested = df["Raw_Invested"].sum()
tot_current = df["Raw_Current"].sum()
tot_pnl = tot_current - tot_invested
tot_pnl_pct = (tot_pnl / tot_invested * 100) if tot_invested > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Invested", f"₹{tot_invested:,.2f}")
m2.metric("Current Value", f"₹{tot_current:,.2f}")

pnl_symbol = "+" if tot_pnl >= 0 else "-"
m3.metric(
    "Net P&L (₹)",
    f"₹{tot_pnl:,.2f}",
    delta=f"{pnl_symbol}₹{abs(tot_pnl):,.2f}",
    delta_color="normal",
)
m4.metric(
    "Total Return",
    f"{tot_pnl_pct:.2f}%",
    delta=f"{tot_pnl_pct:.2f}%",
    delta_color="normal",
)

# --- APPEND TOTALS ROWS ---
winning_df = df[df["Raw_PnL"] > 0]
losing_df = df[df["Raw_PnL"] < 0]

tot_profits = winning_df["Raw_PnL"].sum()
tot_losses = losing_df["Raw_PnL"].sum()

prof_invested = winning_df["Raw_Invested"].sum()
loss_invested = losing_df["Raw_Invested"].sum()

prof_pct = (tot_profits / prof_invested * 100) if prof_invested > 0 else 0.0
loss_pct = (tot_losses / loss_invested * 100) if loss_invested > 0 else 0.0

totals_rows = [
    {
        "Symbol": "🟢 TOTAL PROFITS",
        "Status": "Summary",
        "Qty": winning_df["Qty"].sum(),
        "Avg Buy (₹)": None,
        "LTP (₹)": None,
        "P&L (₹)": tot_profits,
        "P&L (%)": prof_pct,
        "Stop Loss": None,
        "SL P&L (₹)": "-",
        "Trailing SL": None,
        "TSL P&L (₹)": "-",
        "Target 1": None,
        "T1 P&L (₹)": "-",
        "Target 2": None,
        "T2 P&L (₹)": "-",
        "Invested (₹)": prof_invested,
        "Current Val (₹)": winning_df["Raw_Current"].sum(),
        "Weight (%)": round(
            (prof_invested / tot_invested * 100) if tot_invested > 0 else 0, 2
        ),
    },
    {
        "Symbol": "🔴 TOTAL LOSSES",
        "Status": "Summary",
        "Qty": losing_df["Qty"].sum(),
        "Avg Buy (₹)": None,
        "LTP (₹)": None,
        "P&L (₹)": tot_losses,
        "P&L (%)": loss_pct,
        "Stop Loss": None,
        "SL P&L (₹)": "-",
        "Trailing SL": None,
        "TSL P&L (₹)": "-",
        "Target 1": None,
        "T1 P&L (₹)": "-",
        "Target 2": None,
        "T2 P&L (₹)": "-",
        "Invested (₹)": loss_invested,
        "Current Val (₹)": losing_df["Raw_Current"].sum(),
        "Weight (%)": round(
            (loss_invested / tot_invested * 100) if tot_invested > 0 else 0, 2
        ),
    },
    {
        "Symbol": "💼 NET TOTAL",
        "Status": "Summary",
        "Qty": df["Qty"].sum(),
        "Avg Buy (₹)": None,
        "LTP (₹)": None,
        "P&L (₹)": tot_pnl,
        "P&L (%)": tot_pnl_pct,
        "Stop Loss": None,
        "SL P&L (₹)": "-",
        "Trailing SL": None,
        "TSL P&L (₹)": "-",
        "Target 1": None,
        "T1 P&L (₹)": "-",
        "Target 2": None,
        "T2 P&L (₹)": "-",
        "Invested (₹)": tot_invested,
        "Current Val (₹)": tot_current,
        "Weight (%)": 100.0,
    },
]

df_table = pd.concat([df, pd.DataFrame(totals_rows)], ignore_index=True)

display_cols = [
    "Symbol",
    "Status",
    "Qty",
    "Avg Buy (₹)",
    "LTP (₹)",
    "P&L (₹)",
    "P&L (%)",
    "Stop Loss",
    "SL P&L (₹)",
    "Trailing SL",
    "TSL P&L (₹)",
    "Target 1",
    "T1 P&L (₹)",
    "Target 2",
    "T2 P&L (₹)",
    "Invested (₹)",
    "Current Val (₹)",
    "Weight (%)",
]


def style_dataframe(val):
    if isinstance(val, (int, float)):
        if val > 0:
            return "color: #00CC96; font-weight: bold;"
        elif val < 0:
            return "color: #FF2B2B; font-weight: bold;"
    return ""


styled_df = df_table[display_cols].style.map(
    style_dataframe, subset=["P&L (₹)", "P&L (%)"]
).format(
    {
        "Avg Buy (₹)": "₹{:.2f}",
        "LTP (₹)": "₹{:.2f}",
        "Stop Loss": "₹{:.2f}",
        "Trailing SL": "₹{:.2f}",
        "Target 1": "₹{:.2f}",
        "Target 2": "₹{:.2f}",
        "Invested (₹)": "₹{:,.2f}",
        "Current Val (₹)": "₹{:,.2f}",
        "P&L (₹)": "₹{:,.2f}",
        "P&L (%)": "{:+.2f}%",
        "Weight (%)": "{:.1f}%",
    },
    na_rep="-",
)

st.dataframe(styled_df, use_container_width=True, hide_index=True)


# --- 10-DAY CANDLESTICK CHART ENGINE ---
# --- 10-DAY CANDLESTICK CHART ENGINE WITH SHIFTED LTP & LEVEL P&L CALLOUTS ---
def create_candlestick_chart(row):
    df_10d = row.get("df_10d")

    fig = go.Figure()

    if isinstance(df_10d, pd.DataFrame) and not df_10d.empty:
        fig.add_trace(
            go.Candlestick(
                x=list(df_10d.index),
                open=df_10d["Open"],
                high=df_10d["High"],
                low=df_10d["Low"],
                close=df_10d["Close"],
                name="10D Candles",
                increasing_line_color="#00CC96",
                decreasing_line_color="#FF2B2B",
            )
        )
        dates = list(df_10d.index)
    else:
        dates = [datetime.now().strftime("%Y-%m-%d")]

    sl_val = float(row.get("Stop Loss", 0.0))
    tsl_val = float(row.get("Trailing SL", 0.0))
    buy_val = float(row.get("Avg Buy (₹)", 0.0))
    ltp_val = float(row.get("LTP (₹)", 0.0))
    qty = int(row.get("Qty", 0))

    invested = buy_val * qty
    current = ltp_val * qty
    pnl = current - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
    pnl_color = "#00CC96" if pnl >= 0 else "#FF2B2B"
    pnl_sign = "+" if pnl >= 0 else ""

    raw_levels = [
        {"name": "SL", "val": sl_val, "color": "#FF872B", "dash": "dash", "width": 1.5},
        {"name": "TSL", "val": tsl_val, "color": "#77671F", "dash": "dash", "width": 1.5},
        {"name": "BUY", "val": buy_val, "color": "#1F77B4", "dash": "solid", "width": 2.0},
        {"name": "LTP", "val": ltp_val, "color": "#FF0000", "dash": "dot", "width": 2.0},
        {"name": "TARGET 1", "val": float(row.get("Target 1", 0.0)), "color": "#00CC96", "dash": "dash", "width": 1.5},
        {"name": "TARGET 2", "val": float(row.get("Target 2", 0.0)), "color": "#00FF7F", "dash": "dash", "width": 1.5},
    ]

    horizontal_levels = []
    for item in raw_levels:
        if item["val"] <= 0:
            continue
        if item["name"] == "TSL" and sl_val > 0 and abs(tsl_val - sl_val) < 0.01:
            continue
        horizontal_levels.append(item)

    # Standard Center Date Anchor for SL, TSL, Buy, and Target Badges
    mid_idx = len(dates) // 2
    align_date = dates[mid_idx]

    # Shifted Date Anchor for LTP Badge (2 candles to the right) to eliminate overlap
    ltp_align_date = dates[min(mid_idx + 2, len(dates) - 1)]

    for item in horizontal_levels:
        # 1. Full Horizontal Span Line
        fig.add_trace(
            go.Scatter(
                x=[dates[0], dates[-1]],
                y=[item["val"], item["val"]],
                mode="lines",
                line=dict(color=item["color"], width=item["width"], dash=item["dash"]),
                hoverinfo="text",
                hovertext=f"<b>{item['name']}</b>: ₹{item['val']:.2f}",
                showlegend=False,
            )
        )

        # 2. Crisp Opaque White Line Name Badge
        if item["name"] != "BUY":
            # Shift LTP label to the right relative to other badges
            badge_x = ltp_align_date if item["name"] == "LTP" else align_date

            # Default text
            badge_text = f" <b>{item['name']}</b> "

            # Calculate and display P/L and P/L % for Targets and Stop Losses
            if item["name"] in ["SL", "TSL", "TARGET 1", "TARGET 2"] and buy_val > 0 and qty > 0:
                lvl_pnl = (item["val"] - buy_val) * qty
                lvl_pct = ((item["val"] - buy_val) / buy_val) * 100
                lvl_color = "#00CC96" if lvl_pnl >= 0 else "#FF2B2B"
                lvl_sign = "+" if lvl_pnl >= 0 else ""
                badge_text = (
                    f" <b>{item['name']}</b> | "
                    f"<span style='color:{lvl_color};'><b>{lvl_sign}₹{lvl_pnl:,.2f} ({lvl_pct:+.1f}%)</b></span> "
                )

            fig.add_annotation(
                x=badge_x,
                y=item["val"],
                text=badge_text,
                showarrow=False,
                font=dict(color=item["color"], size=11),
                bgcolor="#FFFFFF",
                bordercolor=item["color"],
                borderwidth=1.5,
                borderpad=3,
                yanchor="middle",
                xanchor="center",
            )

        # 3. Y-Axis Price Tag
        fig.add_annotation(
            xref="paper",
            x=1.002,
            y=item["val"],
            text=f" <b>{item['val']:,.2f}</b> ",
            showarrow=False,
            font=dict(color="#FFFFFF", size=11),
            bgcolor=item["color"],
            xanchor="left",
            yanchor="middle",
        )

    # 4. BUY P&L Badge
    if buy_val > 0 and qty > 0:
        fig.add_annotation(
            x=align_date,
            y=buy_val,
            text=f" <span style='color:#1F77B4;'><b>{qty}</b></span> | <span style='color:{pnl_color};'><b>{pnl_sign}₹{pnl:,.2f} ({pnl_pct:+.1f}%)</b></span> ",
            showarrow=False,
            font=dict(size=12),
            bgcolor="#FFFFFF",
            bordercolor="#1F77B4",
            borderwidth=2,
            borderpad=4,
            yanchor="middle",
            xanchor="center",
        )

    if auto_zoom_risk_range and sl_val > 0 and row.get("Target 2", 0) > 0:
        min_bound = sl_val * 0.98
        max_bound = float(row["Target 2"]) * 1.02
    else:
        min_bound = (
            min(df_10d["Low"].min(), sl_val)
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else sl_val
        )
        max_bound = (
            max(df_10d["High"].max(), float(row.get("Target 2", 0)))
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else float(row.get("Target 2", 0))
        )

    fig.update_layout(
        title=dict(
            text=f"<b>{row['Symbol']}</b> ({row['Status']}) | Live LTP: <span style='color:#FF0000;'><b>₹{row['LTP (₹)']}</b></span>",
            font=dict(size=15),
        ),
        xaxis=dict(
            type="category",
            rangeslider=dict(visible=False),
            tickfont=dict(size=11),
            showline=True,
            linewidth=1.5,
            linecolor="#64748B",
            mirror=True,
        ),
        yaxis=dict(
            title=dict(text="Price (₹)", font=dict(size=11)),
            tickfont=dict(size=11),
            range=[min_bound, max_bound],
            showgrid=True,
            gridcolor="rgba(200,200,200,0.12)",
            side="right",
            showline=True,
            linewidth=1.5,
            linecolor="#64748B",
            mirror=True,
        ),
        height=360,
        showlegend=False,
        hoverlabel=dict(font_size=13),
        margin=dict(l=15, r=70, t=35, b=20),
    )

    return fig


# --- CHARTS RENDER SECTION ---
st.markdown(
    '<div class="section-subhdr">📊 10-Day Candlestick Charts & Risk Levels</div>',
    unsafe_allow_html=True,
)

stock_rows_only = df[df["Status"] != "Summary"]

num_cols = chart_cols_per_row
cols = st.columns(num_cols)
for idx, (_, row) in enumerate(stock_rows_only.iterrows()):
    col_idx = idx % num_cols
    with cols[col_idx]:
        st.plotly_chart(create_candlestick_chart(row), use_container_width=True)