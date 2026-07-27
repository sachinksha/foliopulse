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
from streamlit_local_storage import LocalStorage

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

# Initialize Separate Font & View Scaling States
if "table_font_scale" not in st.session_state:
    st.session_state.table_font_scale = 1.20  # Base scale for main table

if "chart_font_scale" not in st.session_state:
    st.session_state.chart_font_scale = 1.10  # Base scale for charts & top stats

if "table_view_preset" not in st.session_state:
    st.session_state.table_view_preset = "🔍 Main Focus View"

fs_table = st.session_state.table_font_scale
fs_chart = st.session_state.chart_font_scale

# --- INJECT DYNAMIC CSS ---
st.markdown(
    f"""
    <style>
        header[data-testid="stHeader"]::before {{
            content: "📈 FolioPulse — Live Portfolio & Risk Monitor";
            position: absolute;
            left: 3.5rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: {1.3 * fs_chart:.2f}rem;
            font-weight: 700;
            color: inherit;
            white-space: nowrap;
            z-index: 999999;
            font-family: Source Sans Pro, sans-serif;
        }}

        .block-container {{
            padding-top: 2.8rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }}

        div[data-testid="stVerticalBlock"] {{
            gap: 0.4rem !important;
        }}

        .section-subhdr {{
            font-size: {1.35 * fs_chart:.2f}rem !important;
            font-weight: 700;
            margin-top: 0.4rem !important;
            margin-bottom: 0.4rem !important;
        }}

        /* Stat Card Formatting */
        .stat-card {{
            background-color: #0E1117;
            padding: 0.65rem 0.85rem;
            border-radius: 8px;
            border-width: 2px;
            border-style: solid;
            text-align: left;
            margin-bottom: 0.5rem;
        }}
        .stat-label {{
            font-size: {0.9 * fs_chart:.2f}rem;
            color: #94A3B8;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: {1.6 * fs_chart:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
            margin-top: 0.1rem;
        }}

        /* Index Card Formatting */
        .index-card {{
            background-color: #161B22;
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            border: 1px solid #30363D;
            text-align: right;
            margin-bottom: 0.5rem;
        }}
        .index-label {{
            font-size: {0.9 * fs_chart:.2f}rem;
            color: #A3B8CC;
            font-weight: 600;
        }}
        .index-val {{
            font-size: {1.35 * fs_chart:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
        }}
        .index-chg {{
            font-size: {0.95 * fs_chart:.2f}rem;
            font-weight: 700;
        }}
    </style>
""",
    unsafe_allow_html=True,
)

local_storage = LocalStorage()

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
    ],
}


# --- PER-USER SESSION INITIALIZATION ---
def init_user_config():
    if "config" not in st.session_state:
        saved_browser_config = local_storage.getItem("foliopulse_user_config")
        if saved_browser_config:
            try:
                st.session_state.config = json.loads(saved_browser_config)
            except Exception:
                st.session_state.config = json.loads(json.dumps(DEFAULT_CONFIG))
        else:
            st.session_state.config = json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(config_dict):
    st.session_state.config = config_dict
    local_storage.setItem("foliopulse_user_config", json.dumps(config_dict))


init_user_config()

if "stock_cache" not in st.session_state:
    st.session_state.stock_cache = {}


# --- SMART INDIAN MARKET HOURS DETECTOR ---
NSE_HOLIDAYS_2026 = {
    "2026-01-26",
    "2026-03-03",
    "2026-03-26",
    "2026-03-31",
    "2026-04-03",
    "2026-04-14",
    "2026-05-01",
    "2026-05-28",
    "2026-06-26",
    "2026-08-26",
    "2026-09-14",
    "2026-10-02",
    "2026-10-20",
    "2026-11-10",
    "2026-11-24",
    "2026-12-25",
}


def is_market_open():
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


# --- AUTO-COMPLETE SEARCH ENGINE VIA YFINANCE ---
@st.cache_data(ttl=300)
def search_ticker_symbols(query):
    if not query or len(query.strip()) < 2:
        return []
    try:
        search_res = yf.Search(query, max_results=8)
        quotes = search_res.quotes
        results = []
        for q in quotes:
            symbol = q.get("symbol", "")
            shortname = q.get("shortname") or q.get("longname") or symbol
            exch = q.get("exchDisp") or q.get("exchange") or ""
            if symbol:
                results.append(
                    {
                        "symbol": symbol,
                        "display": f"{shortname} ({symbol}) — {exch}",
                    }
                )
        return results
    except Exception as e:
        logging.error(f"yfinance search failed: {e}")
        return []


# --- FETCH MARKET INDICES ---
@st.cache_data(ttl=10)
def fetch_market_indices():
    indices = {
        "Sensex": "^BSESN",
        "Nifty 50": "^NSEI",
        "Bank Nifty": "^NSEBANK",
    }
    results = {}
    for name, ticker in indices.items():
        try:
            t = yf.Ticker(ticker)
            fast_info = t.fast_info
            curr_price = float(fast_info.last_price)
            prev_close = float(fast_info.previous_close)
            chg = curr_price - prev_close
            chg_pct = (chg / prev_close) * 100
            results[name] = {
                "val": curr_price,
                "chg": chg,
                "pct": chg_pct,
            }
        except Exception:
            results[name] = {"val": 0.0, "chg": 0.0, "pct": 0.0}
    return results


# --- MODAL POPUP DIALOG FOR WATCHLIST CONFIG MANAGEMENT ---
@st.dialog("🛠️ Watchlist & Script Sequence Manager", width="large")
def open_watchlist_manager():
    st.markdown("Upload/download configs, reorder scripts using grabbers, or edit rows inline.")

    watchlist = st.session_state.config.get("watchlist", [])

    if "editing_row_idx" not in st.session_state:
        st.session_state.editing_row_idx = None

    d_col, u_col = st.columns(2)

    with d_col:
        config_json_str = json.dumps(st.session_state.config, indent=2)
        st.download_button(
            label="📥 Download Config JSON",
            data=config_json_str,
            file_name="foliopulse_config.json",
            mime="application/json",
            use_container_width=True,
        )

    with u_col:
        uploaded_file = st.file_uploader(
            "📤 Upload Config JSON", type=["json"], label_visibility="collapsed"
        )
        if uploaded_file is not None:
            try:
                parsed_config = json.load(uploaded_file)
                if "watchlist" in parsed_config:
                    st.session_state.config = parsed_config
                    save_config(parsed_config)
                    st.success("Config uploaded and applied!")
                    st.rerun()
                else:
                    st.error("Invalid JSON format: missing 'watchlist' key.")
            except Exception as err:
                st.error(f"JSON Parse Error: {err}")

    st.divider()
    st.subheader("📋 Current Watchlist Sequence")

    if not watchlist:
        st.info("Watchlist is empty. Add scripts below!")
    else:
        for i, item in enumerate(watchlist):
            c_grab, c_sym, c_buy, c_qty, c_risk, c_act, c_del = st.columns(
                [0.8, 1.8, 1.3, 1.0, 2.2, 1.2, 0.8]
            )

            is_editing = st.session_state.editing_row_idx == i

            with c_grab:
                g1, g2 = st.columns(2)
                if i > 0 and g1.button("⣿⬆", key=f"grab_up_{i}"):
                    watchlist[i], watchlist[i - 1] = watchlist[i - 1], watchlist[i]
                    st.session_state.config["watchlist"] = watchlist
                    save_config(st.session_state.config)
                    st.rerun()
                if i < len(watchlist) - 1 and g2.button("⣿⬇", key=f"grab_dn_{i}"):
                    watchlist[i], watchlist[i + 1] = watchlist[i + 1], watchlist[i]
                    st.session_state.config["watchlist"] = watchlist
                    save_config(st.session_state.config)
                    st.rerun()

            if is_editing:
                edit_sym = c_sym.text_input("Symbol", value=item["symbol"], key=f"edit_sym_{i}")
                edit_buy = c_buy.number_input("Buy", value=float(item["avg_buy_price"]), step=1.0, key=f"edit_buy_{i}")
                edit_qty = c_qty.number_input("Qty", value=int(item["quantity"]), step=1, key=f"edit_qty_{i}")

                with c_risk:
                    r1, r2 = st.columns(2)
                    edit_sl = r1.number_input("SL", value=float(item.get("stop_loss", 0.0)), step=1.0, key=f"edit_sl_{i}")
                    edit_tsl = r2.number_input("TSL", value=float(item.get("trailing_sl", 0.0)), step=1.0, key=f"edit_tsl_{i}")
                    r3, r4 = st.columns(2)
                    edit_t1 = r3.number_input("T1", value=float(item.get("target_1", 0.0)), step=1.0, key=f"edit_t1_{i}")
                    edit_t2 = r4.number_input("T2", value=float(item.get("target_2", 0.0)), step=1.0, key=f"edit_t2_{i}")

                with c_act:
                    b_save, b_cancel = st.columns(2)
                    if b_save.button("💾", key=f"save_btn_{i}"):
                        watchlist[i] = {
                            "symbol": edit_sym.upper().strip(),
                            "avg_buy_price": float(edit_buy),
                            "quantity": int(edit_qty),
                            "stop_loss": float(edit_sl),
                            "trailing_sl": float(edit_tsl),
                            "target_1": float(edit_t1),
                            "target_2": float(edit_t2),
                            "manual_ltp": float(item.get("manual_ltp", edit_buy)),
                        }
                        st.session_state.config["watchlist"] = watchlist
                        save_config(st.session_state.config)
                        st.session_state.editing_row_idx = None
                        st.rerun()

                    if b_cancel.button("❌", key=f"cancel_btn_{i}"):
                        st.session_state.editing_row_idx = None
                        st.rerun()
            else:
                sym_clean = item["symbol"].replace(".NS", "")
                c_sym.markdown(f"**{i+1}. {sym_clean}**")
                c_buy.markdown(f"₹{item['avg_buy_price']:,.2f}")
                c_qty.markdown(f"{item['quantity']}")
                c_risk.markdown(
                    f"<small>SL: ₹{item.get('stop_loss',0)} | TSL: ₹{item.get('trailing_sl',0)}<br>"
                    f"T1: ₹{item.get('target_1',0)} | T2: ₹{item.get('target_2',0)}</small>",
                    unsafe_allow_html=True,
                )

                if c_act.button("✏️", key=f"pencil_btn_{i}"):
                    st.session_state.editing_row_idx = i
                    st.rerun()

            if c_del.button("🗑️", key=f"del_{i}"):
                watchlist.pop(i)
                st.session_state.config["watchlist"] = watchlist
                save_config(st.session_state.config)
                st.rerun()

    st.divider()
    st.subheader("➕ Add New Script (Auto-Complete Search)")

    search_query = st.text_input(
        "Search Symbol or Company Name (e.g., Reliance, Tata, INFY, AAPL)",
        key="script_search_input",
    )

    selected_symbol = ""
    if search_query:
        search_results = search_ticker_symbols(search_query)
        if search_results:
            options_dict = {item["display"]: item["symbol"] for item in search_results}
            selected_display = st.selectbox(
                "Select matching script from Yahoo Finance:",
                options=list(options_dict.keys()),
            )
            selected_symbol = options_dict[selected_display]
        else:
            st.warning("No ticker results found. Enter ticker manually below.")
            selected_symbol = search_query.upper().strip()

    with st.form("add_script_form"):
        add_sym = st.text_input("Ticker Symbol", value=selected_symbol)
        ac1, ac2 = st.columns(2)
        add_buy = ac1.number_input("Avg Buy Price (₹)", min_value=0.0, step=1.0)
        add_qty = ac2.number_input("Quantity", min_value=1, value=10, step=1)

        rc1, rc2, rc3, rc4 = st.columns(4)
        add_sl = rc1.number_input("Stop Loss (₹)", min_value=0.0, step=1.0)
        add_tsl = rc2.number_input("Trailing SL (₹)", min_value=0.0, step=1.0)
        add_t1 = rc3.number_input("Target 1 (₹)", min_value=0.0, step=1.0)
        add_t2 = rc4.number_input("Target 2 (₹)", min_value=0.0, step=1.0)

        submitted = st.form_submit_button("➕ Add Script to Watchlist", type="primary")
        if submitted and add_sym:
            new_item = {
                "symbol": add_sym.upper().strip(),
                "avg_buy_price": float(add_buy),
                "quantity": int(add_qty),
                "stop_loss": float(add_sl),
                "trailing_sl": float(add_tsl),
                "target_1": float(add_t1),
                "target_2": float(add_t2),
                "manual_ltp": float(add_buy),
            }
            st.session_state.config["watchlist"].append(new_item)
            save_config(st.session_state.config)
            st.success(f"Added {add_sym} to watchlist!")
            st.rerun()


# --- SIDEBAR CONTROLS ---
st.sidebar.title("⚙️ Controls")

if st.sidebar.button("⚙️ Manage Watchlist & Reorder", type="primary", use_container_width=True):
    open_watchlist_manager()

st.sidebar.divider()

# --- TABLE PRESET VIEW CONTROL ---
st.sidebar.subheader("👁️ Table Preset View")
view_preset = st.sidebar.radio(
    "Select Display Preset:",
    options=["🔍 Main Focus View", "📋 Full Detail View"],
    index=0 if st.session_state.table_view_preset == "🔍 Main Focus View" else 1,
)
st.session_state.table_view_preset = view_preset

st.sidebar.divider()

# --- INDEPENDENT FONT CONTROLLERS ---
st.sidebar.subheader("📋 Main Table Font Size")
t_col1, t_col2, t_col3 = st.sidebar.columns([1, 1, 1])

if t_col1.button("🔍 A-", key="tbl_f_dn", use_container_width=True, help="Decrease Main Table Font"):
    st.session_state.table_font_scale = max(0.8, round(st.session_state.table_font_scale - 0.1, 2))
    st.rerun()

t_col2.markdown(
    f"<div style='text-align:center; font-weight:bold; padding-top:0.3rem;'>{st.session_state.table_font_scale:.1f}x</div>",
    unsafe_allow_html=True,
)

if t_col3.button("🔍 A+", key="tbl_f_up", use_container_width=True, help="Increase Main Table Font"):
    st.session_state.table_font_scale = min(2.5, round(st.session_state.table_font_scale + 0.1, 2))
    st.rerun()


st.sidebar.subheader("📊 Charts & UI Font Size")
c_col1, c_col2, c_col3 = st.sidebar.columns([1, 1, 1])

if c_col1.button("🔍 A-", key="crt_f_dn", use_container_width=True, help="Decrease Charts Font"):
    st.session_state.chart_font_scale = max(0.8, round(st.session_state.chart_font_scale - 0.1, 2))
    st.rerun()

c_col2.markdown(
    f"<div style='text-align:center; font-weight:bold; padding-top:0.3rem;'>{st.session_state.chart_font_scale:.1f}x</div>",
    unsafe_allow_html=True,
)

if c_col3.button("🔍 A+", key="crt_f_up", use_container_width=True, help="Increase Charts Font"):
    st.session_state.chart_font_scale = min(2.2, round(st.session_state.chart_font_scale + 0.1, 2))
    st.rerun()

st.sidebar.divider()

manual_override_active = st.sidebar.toggle("🟡 Manual Override", value=False)
market_is_open, market_reason = is_market_open()

refresh_rate = st.sidebar.slider("Refresh Interval (s)", min_value=5, max_value=60, value=10)

chart_cols_per_row = st.sidebar.select_slider("Grid Columns", options=[1, 2, 3], value=2)
auto_zoom_risk_range = st.sidebar.toggle("🔍 Auto-Zoom Range", value=True)

if not manual_override_active and market_is_open:
    st_autorefresh(interval=refresh_rate * 1000, key="portfolio_autorefresh")


# --- FETCH 10-DAY HISTORY ENGINE ---
def get_10day_history(sym):
    ticker_obj = yf.Ticker(sym)
    df_daily = ticker_obj.history(period="15d", interval="1d")

    if df_daily.empty:
        raise ValueError("Empty history dataframe")

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
    rows = []
    fetch_errors = []

    total_invested = sum(item["avg_buy_price"] * item["quantity"] for item in watchlist)

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

        if use_manual_override and manual_ltp > 0:
            ltp = manual_ltp
            status = "🟡 Manual"
            cached = st.session_state.stock_cache.get(sym, {})
            df_10d = cached.get("df_10d", pd.DataFrame())
        else:
            try:
                ltp, df_10d, _ = get_10day_history(sym)
                status = "🟢 Live"
                st.session_state.stock_cache[sym] = {"ltp": ltp, "df_10d": df_10d}
            except Exception as err:
                cached = st.session_state.stock_cache.get(sym, {})
                ltp = cached.get("ltp", buy_price)
                df_10d = cached.get("df_10d", pd.DataFrame())
                status = "🔴 Stale"
                fetch_errors.append(f"**{sym}**: {err}")

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

    return pd.DataFrame(rows), fetch_errors


df, error_logs = fetch_portfolio_data(st.session_state.config["watchlist"], manual_override_active)

# --- TOP STATS & MARKET INDICES HEADER ROW ---
tot_invested = df["Raw_Invested"].sum()
tot_current = df["Raw_Current"].sum()
tot_pnl = tot_current - tot_invested
tot_pnl_pct = (tot_pnl / tot_invested * 100) if tot_invested > 0 else 0.0

border_color = "#00CC96" if tot_pnl >= 0 else "#FF2B2B"
pnl_sign = "+" if tot_pnl >= 0 else ""

index_data = fetch_market_indices()

top_col1, top_col2 = st.columns([1.6, 1.0])

with top_col1:
    s1, s2, s3, s4 = st.columns(4)
    s1.markdown(
        f"""
        <div class="stat-card" style="border-color: {border_color};">
            <div class="stat-label">Net P&L (₹)</div>
            <div class="stat-value" style="color:{border_color};">{pnl_sign}₹{abs(tot_pnl):,.2f}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )
    s2.markdown(
        f"""
        <div class="stat-card" style="border-color: {border_color};">
            <div class="stat-label">Total Return</div>
            <div class="stat-value" style="color:{border_color};">{tot_pnl_pct:+.2f}%</div>
        </div>
    """,
        unsafe_allow_html=True,
    )
    s3.markdown(
        f"""
        <div class="stat-card" style="border-color: {border_color};">
            <div class="stat-label">Total Invested</div>
            <div class="stat-value">₹{tot_invested:,.0f}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )
    s4.markdown(
        f"""
        <div class="stat-card" style="border-color: {border_color};">
            <div class="stat-label">Current Value</div>
            <div class="stat-value">₹{tot_current:,.0f}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with top_col2:
    i1, i2, i3 = st.columns(3)
    for idx_col, name in zip([i1, i2, i3], ["Sensex", "Nifty 50", "Bank Nifty"]):
        data = index_data.get(name, {"val": 0.0, "chg": 0.0, "pct": 0.0})
        idx_color = "#00CC96" if data["chg"] >= 0 else "#FF2B2B"
        idx_sign = "+" if data["chg"] >= 0 else ""

        idx_col.markdown(
            f"""
            <div class="index-card">
                <div class="index-label">{name}</div>
                <div class="index-val">{data['val']:,.2f}</div>
                <div class="index-chg" style="color:{idx_color};">{idx_sign}{data['chg']:,.2f} ({idx_sign}{data['pct']:.2f}%)</div>
            </div>
        """,
            unsafe_allow_html=True,
        )


# --- CONSTRUCT MAIN TABLE ---
winning_df = df[df["Raw_PnL"] > 0]
losing_df = df[df["Raw_PnL"] < 0]

totals_rows = [
    {
        "Symbol": "🟢 TOTAL PROFITS",
        "Status": "Summary",
        "Qty": winning_df["Qty"].sum(),
        "Avg Buy (₹)": None,
        "LTP (₹)": None,
        "P&L (₹)": winning_df["Raw_PnL"].sum(),
        "P&L (%)": (winning_df["Raw_PnL"].sum() / winning_df["Raw_Invested"].sum() * 100)
        if winning_df["Raw_Invested"].sum() > 0
        else 0,
        "Stop Loss": None,
        "SL P&L (₹)": "-",
        "Trailing SL": None,
        "TSL P&L (₹)": "-",
        "Target 1": None,
        "T1 P&L (₹)": "-",
        "Target 2": None,
        "T2 P&L (₹)": "-",
        "Invested (₹)": winning_df["Raw_Invested"].sum(),
        "Current Val (₹)": winning_df["Raw_Current"].sum(),
        "Weight (%)": round(
            (winning_df["Raw_Invested"].sum() / tot_invested * 100) if tot_invested > 0 else 0, 2
        ),
    },
    {
        "Symbol": "🔴 TOTAL LOSSES",
        "Status": "Summary",
        "Qty": losing_df["Qty"].sum(),
        "Avg Buy (₹)": None,
        "LTP (₹)": None,
        "P&L (₹)": losing_df["Raw_PnL"].sum(),
        "P&L (%)": (losing_df["Raw_PnL"].sum() / losing_df["Raw_Invested"].sum() * 100)
        if losing_df["Raw_Invested"].sum() > 0
        else 0,
        "Stop Loss": None,
        "SL P&L (₹)": "-",
        "Trailing SL": None,
        "TSL P&L (₹)": "-",
        "Target 1": None,
        "T1 P&L (₹)": "-",
        "Target 2": None,
        "T2 P&L (₹)": "-",
        "Invested (₹)": losing_df["Raw_Invested"].sum(),
        "Current Val (₹)": losing_df["Raw_Current"].sum(),
        "Weight (%)": round(
            (losing_df["Raw_Invested"].sum() / tot_invested * 100) if tot_invested > 0 else 0, 2
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

# REAL HTML TABLE ENGINE
if view_preset == "🔍 Main Focus View":
    display_cols = [
        "Symbol",
        "Status",
        "Qty",
        "Avg Buy (₹)",
        "LTP (₹)",
        "P&L (₹)",
        "P&L (%)",
        "Stop Loss",
    ]
else:
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

render_df = df_table[display_cols].copy()

currency_cols = [
    "Avg Buy (₹)",
    "LTP (₹)",
    "Stop Loss",
    "Trailing SL",
    "Target 1",
    "Target 2",
    "Invested (₹)",
    "Current Val (₹)",
]
for col in currency_cols:
    if col in render_df.columns:
        render_df[col] = render_df[col].apply(
            lambda x: f"₹{x:,.2f}" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
        )

if "Weight (%)" in render_df.columns:
    render_df["Weight (%)"] = render_df["Weight (%)"].apply(
        lambda x: f"{x:.1f}%" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
    )

tbl_font_rem = round(1.0 * fs_table, 2)
tbl_header_rem = round(1.1 * fs_table, 2)
padding_v = round(0.5 * fs_table, 2)

html_rows = []
header_cells = "".join([f"<th>{col}</th>" for col in display_cols])
html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")

html_rows.append("<tbody>")
for _, row in render_df.iterrows():
    row_cells = []
    is_summary = row.get("Status") == "Summary"
    row_bg = "background-color: #161B22; font-weight: bold;" if is_summary else ""

    for col in display_cols:
        val = row[col]
        cell_style = ""

        if col in ["P&L (₹)", "P&L (%)"] and isinstance(val, (int, float)):
            color = "#00CC96" if val >= 0 else "#FF2B2B"
            sign = "+" if val >= 0 else ""
            val = f"{sign}₹{val:,.2f}" if col == "P&L (₹)" else f"{val:+.2f}%"
            cell_style = f"color: {color}; font-weight: bold;"
        elif val is None:
            val = "-"

        row_cells.append(f"<td style='{cell_style}'>{val}</td>")

    html_rows.append(f"<tr style='{row_bg}'>{''.join(row_cells)}</tr>")

html_rows.append("</tbody>")

full_html_table = f"""
<style>
    .tv-portfolio-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1rem;
        background-color: #0E1117;
        color: #FFFFFF;
        font-family: Source Sans Pro, sans-serif;
    }}
    .tv-portfolio-table th {{
        background-color: #1F2937;
        color: #9CA3AF;
        font-size: {tbl_header_rem}rem !important;
        font-weight: 800;
        padding: {padding_v}rem 0.6rem;
        text-align: left;
        border-bottom: 2px solid #374151;
        white-space: nowrap;
    }}
    .tv-portfolio-table td {{
        font-size: {tbl_font_rem}rem !important;
        padding: {padding_v}rem 0.6rem;
        border-bottom: 1px solid #1F2937;
        white-space: nowrap;
    }}
    .tv-portfolio-table tr:hover {{
        background-color: #1F2937;
    }}
</style>
<div style="overflow-x: auto; width: 100%;">
    <table class="tv-portfolio-table">
        {"".join(html_rows)}
    </table>
</div>
"""

st.markdown(full_html_table, unsafe_allow_html=True)


# --- SIDEBAR JOURNAL EXPORT ---
st.sidebar.divider()
st.sidebar.subheader("📥 Journal Export")

journal_df = df_table[display_cols].copy()
journal_df["Journal Comments"] = ""

today_stamp = datetime.now().strftime("%Y-%m-%d")
csv_data = journal_df.to_csv(index=False).encode("utf-8")

st.sidebar.download_button(
    label=f"📥 Export EOD Journal ({today_stamp})",
    data=csv_data,
    file_name=f"foliopulse_journal_{today_stamp}.csv",
    mime="text/csv",
    use_container_width=True,
)


# --- 10-DAY CANDLESTICK CHART ENGINE ---
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

    t1_val = float(row.get("Target 1", 0.0))
    t2_val = float(row.get("Target 2", 0.0))

    raw_levels = [
        {"name": "SL", "val": sl_val, "color": "#FF872B", "dash": "dash", "width": 1.5},
        {"name": "TSL", "val": tsl_val, "color": "#77671F", "dash": "dash", "width": 1.5},
        {"name": "BUY", "val": buy_val, "color": "#1F77B4", "dash": "solid", "width": 2.0},
        {"name": "LTP", "val": ltp_val, "color": "#FF0000", "dash": "dot", "width": 2.0},
        {"name": "TARGET 1", "val": t1_val, "color": "#00CC96", "dash": "dash", "width": 1.5},
        {"name": "TARGET 2", "val": t2_val, "color": "#00FF7F", "dash": "dash", "width": 1.5},
    ]

    horizontal_levels = []
    for item in raw_levels:
        if item["val"] <= 0:
            continue
        if item["name"] == "TSL" and sl_val > 0 and abs(tsl_val - sl_val) < 0.01:
            continue
        # DEDUPLICATE TARGET 2 IF IDENTICAL TO TARGET 1
        if item["name"] == "TARGET 2" and t1_val > 0 and abs(t2_val - t1_val) < 0.01:
            continue
        horizontal_levels.append(item)

    mid_idx = len(dates) // 2
    align_date = dates[mid_idx]
    ltp_align_date = dates[min(mid_idx + 2, len(dates) - 1)]

    c_title_size = int(18 * fs_chart)
    c_badge_size = int(13 * fs_chart)
    c_axis_size = int(13 * fs_chart)

    for item in horizontal_levels:
        fig.add_trace(
            go.Scatter(
                x=[dates[0], dates[-1]],
                y=[item["val"], item["val"]],
                mode="lines",
                line=dict(color=item["color"], width=item["width"], dash=item["dash"]),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        if item["name"] != "BUY":
            badge_x = ltp_align_date if item["name"] == "LTP" else align_date
            badge_text = f" <b>{item['name']}</b> "

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
                font=dict(color=item["color"], size=c_badge_size),
                bgcolor="#FFFFFF",
                bordercolor=item["color"],
                borderwidth=1.5,
                borderpad=4,
                yanchor="middle",
                xanchor="center",
            )

        # Right Y-Axis Price Badge
        fig.add_annotation(
            xref="paper",
            x=1.002,
            y=item["val"],
            text=f" <b>{item['val']:,.2f}</b> ",
            showarrow=False,
            font=dict(color="#FFFFFF", size=c_badge_size),
            bgcolor=item["color"],
            xanchor="left",
            yanchor="middle",
        )

    # BUY Entry P&L Badge
    if buy_val > 0 and qty > 0:
        fig.add_annotation(
            x=align_date,
            y=buy_val,
            text=f" <span style='color:#1F77B4;'><b>{qty}</b></span> | <span style='color:{pnl_color};'><b>{pnl_sign}₹{pnl:,.2f} ({pnl_pct:+.1f}%)</b></span> ",
            showarrow=False,
            font=dict(size=int(14 * fs_chart)),
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
            font=dict(size=c_title_size),
        ),
        xaxis=dict(
            type="category",
            rangeslider=dict(visible=False),
            tickfont=dict(size=c_axis_size),
            showline=True,
            linewidth=1.5,
            linecolor="#64748B",
            mirror=True,
        ),
        yaxis=dict(
            title=dict(text="Price (₹)", font=dict(size=c_axis_size)),
            tickfont=dict(size=c_axis_size),
            range=[min_bound, max_bound],
            showgrid=True,
            gridcolor="rgba(200,200,200,0.12)",
            side="right",
            showline=True,
            linewidth=1.5,
            linecolor="#64748B",
            mirror=True,
        ),
        height=int(440 * fs_chart),
        showlegend=False,
        margin=dict(l=15, r=85, t=40, b=25),
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