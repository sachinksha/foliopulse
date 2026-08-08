from datetime import datetime
import json
import logging
import math
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

from expense_calculator import compute_trade_expenses_detailed

# =========================================================
# CENTRALIZED CONFIG: LABELS, COLORS, AND THEME CONSTANTS
# =========================================================
APP_CONFIG = {
    "LABELS": {
        "APP_TITLE": "FolioPulse",
        "APP_SUBTITLE": "Live Portfolio & Risk Monitor",
        "SL": "STOP-LOSS",
        "TSL": "TRAILING-SL",
        "BUY": "BUY PRICE",
        "LTP": "LIVE LTP",
        "T1": "TARGET 1",
        "T2": "TARGET 2",
        "SUMMARY_WIN": "🟢 TOTAL PROFITS",
        "SUMMARY_LOSS": "🔴 TOTAL LOSSES",
        "SUMMARY_NET": "💼 NET TOTAL",
    },
    "COLORS": {
        "PROFIT_GREEN": "#00CC96",
        "LOSS_RED": "#FF2B2B",
        "SL_ORANGE": "#FF872B",
        "TSL_YELLOW": "#77671F",
        "BUY_BLUE": "#1F77B4",
        "LTP_RED": "#FF0000",
        "BG_DARK": "#0E1117",
        "BG_CARD": "#161B22",
        "BORDER_CARD": "#30363D",
        "HEADER_BG": "#1F2937",
        "HEADER_BORDER": "#374151",
        "TEXT_MUTED": "#9CA3AF",
    },
    "UNITS": {
        "CURRENCY_SYMBOL": "₹",
        "CRORE": "Cr",
        "LAKH": "L",
        "THOUSAND": "K",
    },
}

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- PAGE SETUP ---
st.set_page_config(
    page_title=f"{APP_CONFIG['LABELS']['APP_TITLE']} — {APP_CONFIG['LABELS']['APP_SUBTITLE']}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- FIREBASE ADMIN SDK INITIALIZATION ---
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
        return firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()

init_firebase()
db = firestore.client()

# --- AUTHENTICATION CHECK ---
if not st.user.is_logged_in:
    st.sidebar.title(f"📈 {APP_CONFIG['LABELS']['APP_TITLE']}")
    st.sidebar.caption("Please log in to access your portfolio across devices.")
    
    st.markdown("### 🔐 Multi-Device Portfolio Sync Required")
    st.info("Log in with Google to view and sync your portfolio across mobile, tablet, and desktop.")
    
    if st.button("🔑 Log in with Google", type="primary"):
        st.login()
    st.stop()

user_email = st.user.email

# --- SESSION STATES ---
if "table_font_scale" not in st.session_state:
    st.session_state.table_font_scale = 1.00

if "chart_font_scale" not in st.session_state:
    st.session_state.chart_font_scale = 1.00

if "table_view_preset" not in st.session_state:
    st.session_state.table_view_preset = "🔍 Main Focus View"

if "is_modal_open" not in st.session_state:
    st.session_state.is_modal_open = False

if "show_table" not in st.session_state:
    st.session_state.show_table = True

# --- NET P&L PIP DETACH / DOCK QUERY PARAM HANDLER ---
if "is_pnl_detached" not in st.session_state:
    st.session_state.is_pnl_detached = False

if "toggle_pnl_float" in st.query_params:
    st.session_state.is_pnl_detached = True
    st.query_params.clear()
    st.rerun()

if "dock_pnl" in st.query_params:
    st.session_state.is_pnl_detached = False
    st.query_params.clear()
    st.rerun()

fs_table = st.session_state.table_font_scale
fs_chart = st.session_state.chart_font_scale

DEFAULT_CONFIG = {
    "refresh_seconds": 10,
    "watchlist": [
        {
            "symbol": "LT.NS",
            "avg_buy_price": 2400.00,
            "quantity": 10,
            "trade_type": "DELIVERY",
            "stop_loss": 2200.00,
            "trailing_sl": 2200.00,
            "target_1": 4800.00,
            "target_2": 4800.00,
            "manual_ltp": 3500.00,
        },
        {
            "symbol": "TITAN.NS",
            "avg_buy_price": 3400.00,
            "quantity": 15,
            "trade_type": "DELIVERY",
            "stop_loss": 3200.00,
            "trailing_sl": 3300.00,
            "target_1": 4800.00,
            "target_2": 4900.00,
            "manual_ltp": 3500.00,
        },
    ],
}

# --- CLOUD CONFIG SYNC FUNCTIONS ---
def load_user_config_from_cloud(email: str) -> dict:
    try:
        doc_ref = db.collection("user_configs").document(email)
        doc = doc_ref.get()
        if doc.exists:
            cfg = doc.to_dict()
            for item in cfg.get("watchlist", []):
                if "trade_type" not in item:
                    item["trade_type"] = "DELIVERY"
            return cfg
        else:
            doc_ref.set(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
    except Exception as e:
        logging.error(f"Firestore load failed: {e}")
        return DEFAULT_CONFIG

def save_config_to_cloud(email: str, config_dict: dict):
    st.session_state.config = config_dict
    try:
        doc_ref = db.collection("user_configs").document(email)
        doc_ref.set(config_dict, merge=True)
    except Exception as e:
        st.error(f"Failed to sync with cloud: {e}")

if "config" not in st.session_state:
    st.session_state.config = load_user_config_from_cloud(user_email)

def save_config(config_dict):
    save_config_to_cloud(user_email, config_dict)

if "stock_cache" not in st.session_state:
    st.session_state.stock_cache = {}

# --- ZERODHA EXPENSE ENGINE ---

# --- COMPACT INR FORMATTER ---
def format_compact_inr(val):
    if val is None or not isinstance(val, (int, float)):
        return "-"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    sym = APP_CONFIG["UNITS"]["CURRENCY_SYMBOL"]

    if abs_val >= 10_000_000:
        return f"{sign}{sym}{abs_val / 10_000_000:.2f}{APP_CONFIG['UNITS']['CRORE']}"
    elif abs_val >= 100_000:
        return f"{sign}{sym}{abs_val / 100_000:.2f}{APP_CONFIG['UNITS']['LAKH']}"
    elif abs_val >= 1_000:
        return f"{sign}{sym}{abs_val / 1_000:.1f}{APP_CONFIG['UNITS']['THOUSAND']}"
    else:
        return f"{sign}{sym}{abs_val:,.2f}"

# --- INJECT DYNAMIC CSS ---
st.markdown(
    f"""
    <style>
        header[data-testid="stHeader"] {{
            opacity: 0;
            transition: opacity 0.25s ease-in-out;
            z-index: 999999;
        }}
        header[data-testid="stHeader"]:hover {{
            opacity: 1;
        }}

        .block-container {{
            padding-top: 0.4rem !important;
            padding-bottom: 0.4rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            max-width: 100% !important;
        }}

        div[data-testid="stVerticalBlock"] {{
            gap: 0.25rem !important;
        }}

        div[data-testid="stExpanderDetails"] {{
            padding: 0rem 0.2rem 0.2rem 0.2rem !important;
        }}

        .stat-card {{
            background-color: {APP_CONFIG["COLORS"]["BG_DARK"]};
            padding: 0.4rem 0.6rem;
            border-radius: 6px;
            border-width: 2px;
            border-style: solid;
            text-align: left;
            margin-bottom: 0.2rem;
        }}
        .stat-label {{
            font-size: {0.85 * fs_chart:.2f}rem;
            color: {APP_CONFIG["COLORS"]["TEXT_MUTED"]};
            font-weight: 700;
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: {1.45 * fs_chart:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
            margin-top: 0.05rem;
            white-space: nowrap;
        }}

        .index-card {{
            background-color: {APP_CONFIG["COLORS"]["BG_CARD"]};
            padding: 0.4rem 0.6rem;
            border-radius: 6px;
            border: 1px solid {APP_CONFIG["COLORS"]["BORDER_CARD"]};
            text-align: right;
            margin-bottom: 0.2rem;
        }}
        .index-label {{
            font-size: {0.85 * fs_chart:.2f}rem;
            color: #A3B8CC;
            font-weight: 700;
        }}
        .index-val {{
            font-size: {1.25 * fs_chart:.2f}rem;
            font-weight: 800;
            color: #FFFFFF;
            white-space: nowrap;
        }}
        .index-chg {{
            font-size: {0.9 * fs_chart:.2f}rem;
            font-weight: 700;
            white-space: nowrap;
        }}
    </style>
""",
    unsafe_allow_html=True,
)

# --- SMART INDIAN MARKET HOURS DETECTOR ---
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-08-26", "2026-09-14", "2026-10-02",
    "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
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

# --- MODAL POPUP DIALOG ---
@st.dialog("🛠️ Watchlist & Script Sequence Manager", width="large")
def open_watchlist_manager():
    st.session_state.is_modal_open = True
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
                    st.success("Config uploaded and synced!")
                    st.rerun()
                else:
                    st.error("Invalid JSON format: missing 'watchlist' key.")
            except Exception as err:
                st.error(f"Config Upload / Cloud Sync Error: {err}")
                st.stop()

    st.divider()
    st.subheader("📋 Current Watchlist Sequence")

    if not watchlist:
        st.info("Watchlist is empty. Add scripts below!")
    else:
        for i, item in enumerate(watchlist):
            c_grab, c_sym, c_type, c_buy, c_qty, c_risk, c_act, c_del = st.columns(
                [0.6, 1.6, 1.2, 1.1, 0.9, 2.3, 1.0, 0.6]
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

            curr_trade_type = item.get("trade_type", "DELIVERY")

            if is_editing:
                edit_sym = c_sym.text_input("Symbol", value=item["symbol"], key=f"edit_sym_{i}")
                edit_type = c_type.selectbox(
                    "Type", options=["DELIVERY", "INTRADAY"], index=0 if curr_trade_type == "DELIVERY" else 1, key=f"edit_ttype_{i}"
                )
                edit_buy = c_buy.number_input("Buy", value=float(item["avg_buy_price"]), step=1.0, key=f"edit_buy_{i}")
                edit_qty = c_qty.number_input("Qty", value=int(item["quantity"]), step=1, key=f"edit_qty_{i}")

                with c_risk:
                    r1, r2, r3 = st.columns(3)
                    edit_sl = r1.number_input(APP_CONFIG["LABELS"]["SL"], value=float(item.get("stop_loss", 0.0)), step=1.0, key=f"edit_sl_{i}")
                    edit_tsl = r2.number_input(APP_CONFIG["LABELS"]["TSL"], value=float(item.get("trailing_sl", 0.0)), step=1.0, key=f"edit_tsl_{i}")
                    edit_manual_ltp = r3.number_input("Manual LTP", value=float(item.get("manual_ltp", edit_buy)), step=1.0, key=f"edit_mltp_{i}")

                    r4, r5 = st.columns(2)
                    edit_t1 = r4.number_input(APP_CONFIG["LABELS"]["T1"], value=float(item.get("target_1", 0.0)), step=1.0, key=f"edit_t1_{i}")
                    edit_t2 = r5.number_input(APP_CONFIG["LABELS"]["T2"], value=float(item.get("target_2", 0.0)), step=1.0, key=f"edit_t2_{i}")

                with c_act:
                    b_save, b_cancel = st.columns(2)
                    if b_save.button("💾", key=f"save_btn_{i}"):
                        watchlist[i] = {
                            "symbol": edit_sym.upper().strip(),
                            "trade_type": edit_type,
                            "avg_buy_price": float(edit_buy),
                            "quantity": int(edit_qty),
                            "stop_loss": float(edit_sl),
                            "trailing_sl": float(edit_tsl),
                            "target_1": float(edit_t1),
                            "target_2": float(edit_t2),
                            "manual_ltp": float(edit_manual_ltp),
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
                lbl_sl = APP_CONFIG["LABELS"]["SL"]
                lbl_tsl = APP_CONFIG["LABELS"]["TSL"]
                lbl_t1 = APP_CONFIG["LABELS"]["T1"]
                lbl_t2 = APP_CONFIG["LABELS"]["T2"]
                c_sym.markdown(f"**{i+1}. {sym_clean}**")
                
                type_badge = "📦 Delivery" if curr_trade_type == "DELIVERY" else "⚡ Intraday"
                c_type.markdown(f"<small><b>{type_badge}</b></small>", unsafe_allow_html=True)
                
                c_buy.markdown(f"₹{item['avg_buy_price']:,.2f}")
                c_qty.markdown(f"{item['quantity']}")
                c_risk.markdown(
                    f"<small>{lbl_sl}: ₹{item.get('stop_loss',0)} | {lbl_tsl}: ₹{item.get('trailing_sl',0)}<br>"
                    f"{lbl_t1}: ₹{item.get('target_1',0)} | {lbl_t2}: ₹{item.get('target_2',0)} | Manual: ₹{item.get('manual_ltp',0)}</small>",
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
    st.subheader("➕ Add New Script")

    search_query = st.text_input("Search Symbol or Company Name", key="script_search_input")

    selected_symbol = ""
    if search_query:
        search_results = search_ticker_symbols(search_query)
        if search_results:
            options_dict = {item["display"]: item["symbol"] for item in search_results}
            selected_display = st.selectbox("Select matching script:", options=list(options_dict.keys()))
            selected_symbol = options_dict[selected_display]
        else:
            st.warning("No ticker results found. Enter ticker manually below.")
            selected_symbol = search_query.upper().strip()

    with st.form("add_script_form"):
        add_sym = st.text_input("Ticker Symbol", value=selected_symbol)
        ac1, ac2, ac3, ac4 = st.columns(4)
        add_type = ac1.selectbox("Trade Type", options=["DELIVERY", "INTRADAY"], index=0)
        add_buy = ac2.number_input("Avg Buy Price (₹)", min_value=0.0, step=1.0)
        add_qty = ac3.number_input("Quantity", min_value=1, value=10, step=1)
        add_mltp = ac4.number_input("Manual LTP (₹)", min_value=0.0, step=1.0)

        rc1, rc2, rc3, rc4 = st.columns(4)
        add_sl = rc1.number_input(f"{APP_CONFIG['LABELS']['SL']} (₹)", min_value=0.0, step=1.0)
        add_tsl = rc2.number_input(f"{APP_CONFIG['LABELS']['TSL']} (₹)", min_value=0.0, step=1.0)
        add_t1 = rc3.number_input(f"{APP_CONFIG['LABELS']['T1']} (₹)", min_value=0.0, step=1.0)
        add_t2 = rc4.number_input(f"{APP_CONFIG['LABELS']['T2']} (₹)", min_value=0.0, step=1.0)

        submitted = st.form_submit_button("➕ Add Script to Watchlist", type="primary")
        if submitted and add_sym:
            new_item = {
                "symbol": add_sym.upper().strip(),
                "trade_type": add_type,
                "avg_buy_price": float(add_buy),
                "quantity": int(add_qty),
                "stop_loss": float(add_sl),
                "trailing_sl": float(add_tsl),
                "target_1": float(add_t1),
                "target_2": float(add_t2),
                "manual_ltp": float(add_mltp if add_mltp > 0 else add_buy),
            }
            st.session_state.config["watchlist"].append(new_item)
            save_config(st.session_state.config)
            st.success(f"Added {add_sym} ({add_type}) to watchlist!")
            st.session_state.is_modal_open = False
            st.rerun()

# --- SIDEBAR HEADER & USER BAR ---
st.sidebar.title(f"📈 {APP_CONFIG['LABELS']['APP_TITLE']}")
st.sidebar.caption(f"👤 Logged in: **{user_email}**")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.logout()

st.sidebar.divider()

if st.sidebar.button("⚙️ Manage Watchlist & Reorder", type="primary", use_container_width=True):
    open_watchlist_manager()

st.sidebar.divider()

# --- SIDEBAR DISPLAY & TABLE TOGGLE CONTROLS ---
st.sidebar.subheader("👁️ Display & Layout Controls")

show_table_toggle = st.sidebar.toggle("👁️ Show Main Table", value=st.session_state.show_table)
st.session_state.show_table = show_table_toggle

if st.session_state.show_table:
    view_preset = st.sidebar.radio(
        "Select Display Preset:",
        options=["🔍 Main Focus View", "📋 Full Detail View"],
        index=0 if st.session_state.table_view_preset == "🔍 Main Focus View" else 1,
    )
    st.session_state.table_view_preset = view_preset

st.sidebar.divider()

# --- FONT CONTROLLERS ---
if st.session_state.show_table:
    st.sidebar.subheader("📋 Main Table Font Size")
    t_col1, t_col2, t_col3 = st.sidebar.columns([1, 1, 1])

    if t_col1.button("🔍 A-", key="tbl_f_dn", use_container_width=True):
        st.session_state.table_font_scale = max(0.7, round(st.session_state.table_font_scale - 0.1, 2))
        st.rerun()

    t_col2.markdown(
        f"<div style='text-align:center; font-weight:bold; padding-top:0.3rem;'>{st.session_state.table_font_scale:.1f}x</div>",
        unsafe_allow_html=True,
    )

    if t_col3.button("🔍 A+", key="tbl_f_up", use_container_width=True):
        st.session_state.table_font_scale = min(2.0, round(st.session_state.table_font_scale + 0.1, 2))
        st.rerun()

st.sidebar.subheader("📊 Charts & UI Font Size")
c_col1, c_col2, c_col3 = st.sidebar.columns([1, 1, 1])

if c_col1.button("🔍 A-", key="crt_f_dn", use_container_width=True):
    st.session_state.chart_font_scale = max(0.7, round(st.session_state.chart_font_scale - 0.1, 2))
    st.rerun()

c_col2.markdown(
    f"<div style='text-align:center; font-weight:bold; padding-top:0.3rem;'>{st.session_state.chart_font_scale:.1f}x</div>",
    unsafe_allow_html=True,
)

if c_col3.button("🔍 A+", key="crt_f_up", use_container_width=True):
    st.session_state.chart_font_scale = min(2.0, round(st.session_state.chart_font_scale + 0.1, 2))
    st.rerun()

st.sidebar.divider()

manual_override_active = st.sidebar.toggle("🟡 Manual Override", value=False)

if manual_override_active:
    st.sidebar.caption("✏️ Adjust Live LTPs below:")
    updated_watchlist = st.session_state.config.get("watchlist", [])
    config_changed = False

    for idx, item in enumerate(updated_watchlist):
        sym_clean = item["symbol"].replace(".NS", "")
        current_mltp = float(item.get("manual_ltp", item["avg_buy_price"]))

        new_mltp = st.sidebar.number_input(f"{sym_clean} Price (₹)", value=current_mltp, step=1.0, key=f"sb_mltp_{idx}")

        if new_mltp != current_mltp:
            updated_watchlist[idx]["manual_ltp"] = float(new_mltp)
            config_changed = True

    if config_changed:
        st.session_state.config["watchlist"] = updated_watchlist
        save_config(st.session_state.config)
        st.rerun()

market_is_open, market_reason = is_market_open()

refresh_rate = st.sidebar.slider("Refresh Interval (s)", min_value=5, max_value=60, value=10)
chart_cols_per_row = st.sidebar.select_slider("Grid Columns", options=[1, 2, 3], value=2)
auto_zoom_risk_range = st.sidebar.toggle("🔍 Auto-Zoom Range", value=True)

if not manual_override_active and market_is_open and not st.session_state.is_modal_open:
    st_autorefresh(interval=refresh_rate * 1000, key="portfolio_autorefresh")

def get_10day_history(sym):
    ticker_obj = yf.Ticker(sym)
    df_daily = ticker_obj.history(period="20d", interval="1d")

    if df_daily.empty:
        raise ValueError(f"Yahoo Finance returned empty history for {sym}. (Possible rate-limit/block)")

    df_daily.index = df_daily.index.strftime("%Y-%m-%d")

    # Multi-tier price resolution to prevent silent stale price fallbacks
    ltp = None
    prev_close = None

    # Tier 1: Fast Info
    try:
        fast_info = ticker_obj.fast_info
        ltp = round(float(fast_info.last_price), 2)
        prev_close = float(fast_info.previous_close)
    except Exception:
        pass

    # Tier 2: Recent Close Price from Daily History
    if ltp is None or ltp <= 0:
        if len(df_daily) > 0:
            ltp = round(float(df_daily["Close"].iloc[-1]), 2)
            prev_close = float(df_daily["Close"].iloc[-2]) if len(df_daily) > 1 else ltp

    if ltp is None or ltp <= 0:
        raise ValueError(f"Could not extract valid LTP for {sym}")

    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)
    target_dt = now.date() if now.hour >= 16 else (now.date() - pd.Timedelta(days=1))
    
    if target_dt.weekday() < 5:
        target_str = target_dt.strftime("%Y-%m-%d")
        if target_str not in df_daily.index:
            try:
                df_intraday = ticker_obj.history(period="5d", interval="5m")
                if not df_intraday.empty:
                    df_intraday.index = pd.to_datetime(df_intraday.index).tz_convert(india_tz)
                    df_target_day = df_intraday[df_intraday.index.strftime("%Y-%m-%d") == target_str]
                    
                    if not df_target_day.empty:
                        missing_bar = pd.DataFrame(
                            {
                                "Open": df_target_day["Open"].iloc[0],
                                "High": df_target_day["High"].max(),
                                "Low": df_target_day["Low"].min(),
                                "Close": df_target_day["Close"].iloc[-1],
                                "Volume": df_target_day["Volume"].sum(),
                            },
                            index=[target_str],
                        )
                        df_daily = pd.concat([df_daily, missing_bar])
                        df_daily = df_daily[~df_daily.index.duplicated(keep="last")].sort_index()
            except Exception as patch_err:
                logging.warning(f"Failed to patch missing daily bar for {sym}: {patch_err}")

    df_10d = df_daily.tail(10)
    return ltp, prev_close, df_10d

def fetch_portfolio_data(watchlist, use_manual_override):
    lbl_sl = APP_CONFIG["LABELS"]["SL"]
    lbl_tsl = APP_CONFIG["LABELS"]["TSL"]
    lbl_t1 = APP_CONFIG["LABELS"]["T1"]
    lbl_t2 = APP_CONFIG["LABELS"]["T2"]

    all_cols = [
        "Symbol", "RawSymbol", "Type", "Status", "Qty", "Avg Buy (₹)", "Invested (₹)",
        "LTP (₹)", "Current Val (₹)", "Weight (%)", lbl_sl, lbl_tsl, lbl_t1, lbl_t2,
        "Day's Gain/Loss", "Day's Gain/Loss (%)", "Expenses (₹)", "Gross P&L (₹)",
        "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)", "Raw_DayPnL", "Raw_PnL",
        "Raw_NetPnL", "Raw_Expenses", "Raw_Invested", "Raw_Current", "df_10d"
    ]

    if not watchlist:
        return pd.DataFrame(columns=all_cols), []

    rows = []
    fetch_errors = []
    total_invested = sum(item["avg_buy_price"] * item["quantity"] for item in watchlist)

    for idx, item in enumerate(watchlist):
        sym = item["symbol"]
        buy_price = float(item["avg_buy_price"])
        qty = int(item["quantity"])
        trade_type = item.get("trade_type", "DELIVERY")
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
            prev_close = cached.get("prev_close", buy_price)
            df_10d = cached.get("df_10d", pd.DataFrame())
        else:
            try:
                ltp, prev_close, df_10d = get_10day_history(sym)
                status = "🟢 Live"
                st.session_state.stock_cache[sym] = {
                    "ltp": ltp,
                    "prev_close": prev_close,
                    "df_10d": df_10d,
                }
            except Exception as err:
                cached = st.session_state.stock_cache.get(sym, {})
                ltp = cached.get("ltp", buy_price)
                prev_close = cached.get("prev_close", buy_price)
                df_10d = cached.get("df_10d", pd.DataFrame())
                status = "🔴 Stale"
                fetch_errors.append(f"**{sym}**: {err}")

        exp_data = compute_trade_expenses_detailed(qty, buy_price, ltp, trade_type)
        total_exp = exp_data["total_expenses"]

        day_pnl = (ltp - prev_close) * qty if prev_close > 0 else 0.0
        day_pnl_pct = ((ltp - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

        current = ltp * qty
        gross_pnl = current - invested
        gross_pnl_pct = (gross_pnl / invested * 100) if invested > 0 else 0.0

        net_pnl = gross_pnl - total_exp
        net_pnl_pct = (net_pnl / invested * 100) if invested > 0 else 0.0

        weight_pct = (invested / total_invested * 100) if total_invested > 0 else 0.0

        rows.append(
            {
                "Symbol": sym.replace(".NS", ""),
                "RawSymbol": sym,
                "Type": trade_type,
                "Status": status,
                "Qty": qty,
                "Avg Buy (₹)": buy_price,
                "Invested (₹)": round(invested, 2),
                "LTP (₹)": ltp,
                "Current Val (₹)": round(current, 2),
                "Weight (%)": round(weight_pct, 2),
                lbl_sl: sl,
                lbl_tsl: tsl,
                lbl_t1: t1,
                lbl_t2: t2,
                "Day's Gain/Loss": round(day_pnl, 2),
                "Day's Gain/Loss (%)": round(day_pnl_pct, 2),
                "Expenses (₹)": round(total_exp, 2),
                "Gross P&L (₹)": round(gross_pnl, 2),
                "Gross P&L (%)": round(gross_pnl_pct, 2),
                "Net P&L (₹)": round(net_pnl, 2),
                "Net P&L (%)": round(net_pnl_pct, 2),
                "Raw_DayPnL": day_pnl,
                "Raw_PnL": gross_pnl,
                "Raw_NetPnL": net_pnl,
                "Raw_Expenses": total_exp,
                "Raw_Invested": invested,
                "Raw_Current": current,
                "df_10d": df_10d,
            }
        )

    return pd.DataFrame(rows), fetch_errors

df, error_logs = fetch_portfolio_data(
    st.session_state.config.get("watchlist", []), manual_override_active
)

# --- MARKET STATUS & STALE DATA CALLOUT BANNER ---
india_tz = pytz.timezone("Asia/Kolkata")
last_fetched_time = datetime.now(india_tz).strftime("%I:%M:%S %p IST")

# Detect if any symbol is running on stale/cached data
stale_symbols = [
    row["Symbol"] for _, row in df.iterrows() 
    if row.get("Status") == "🔴 Stale"
] if not df.empty else []

# 1. Global Callout Banner if Data is Stale
if stale_symbols:
    st.error(
        f"⚠️ **STALE DATA WARNING**: Live market data fetch failed for **{', '.join(stale_symbols)}**. "
        f"Showing last known cached prices. (Yahoo Finance API rate-limited or unreachable). "
        f"Try clicking **'🔄 Force Data Refresh'** in the sidebar."
    )
elif error_logs:
    st.warning(f"⚠️ **Market Fetch Notice**: {'; '.join(error_logs)}")

# 2. Market Status Line with Exact Timestamp Marker
if manual_override_active:
    st.warning("🟡 **Manual Override Active**: Live price polling is paused. Adjust prices in the sidebar.")
elif market_is_open:
    st.caption(
        f"🟢 **Market Status**: {market_reason} | "
        f"🕒 **Last Fetched**: `{last_fetched_time}` | "
        f"Auto-Refreshing every {refresh_rate}s"
    )
else:
    st.info(
        f"🔴 **Market Status**: {market_reason} | "
        f"🕒 **Last Fetched**: `{last_fetched_time}` | "
        f"Background auto-refresh paused."
    )


if df.empty:
    st.info("📋 **Your Watchlist is currently empty.** Click **'⚙️ Manage Watchlist & Reorder'** in the sidebar to add your first stock!")

# --- TOP STATS & MARKET INDICES HEADER ROW ---
tot_invested = df["Raw_Invested"].sum() if "Raw_Invested" in df.columns else 0.0
tot_current = df["Raw_Current"].sum() if "Raw_Current" in df.columns else 0.0
tot_expenses = df["Raw_Expenses"].sum() if "Raw_Expenses" in df.columns else 0.0

tot_gross_pnl = tot_current - tot_invested
tot_net_pnl = df["Raw_NetPnL"].sum() if "Raw_NetPnL" in df.columns else 0.0
tot_net_pnl_pct = (tot_net_pnl / tot_invested * 100) if tot_invested > 0 else 0.0

border_color = (
    APP_CONFIG["COLORS"]["PROFIT_GREEN"]
    if tot_net_pnl >= 0
    else APP_CONFIG["COLORS"]["LOSS_RED"]
)
sign = "+" if tot_net_pnl >= 0 else ""

index_data = fetch_market_indices()

# --- HEADER LAYOUT ---
top_col1, top_col2 = st.columns([1.4, 1.0])

with top_col1:
    if st.session_state.is_pnl_detached:
        # DETACHED STATE: Show ONLY Total Invested card in header
        s1, = st.columns(1)
        s1.markdown(
            f"""
            <div class="stat-card" style="border-color: #30363D;">
                <div class="stat-label">Total Invested</div>
                <div class="stat-value">{format_compact_inr(tot_invested)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # ATTACHED STATE: Show Net P&L (with Detach Button) + Net Return + Total Invested
        s1, s2, s3 = st.columns(3)
        
        with s1:
            st.markdown(
                f"""
                <div class="stat-card" style="border-color: {border_color};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="stat-label">Net P&L</div>
                        <a href="?toggle_pnl_float=true" target="_self" style="text-decoration: none; color: #9CA3AF; font-size: 0.8rem; border: 1px solid #374151; padding: 1px 5px; border-radius: 4px;" title="Detach to Bottom-Right">↗</a>
                    </div>
                    <div class="stat-value" style="color:{border_color};">{format_compact_inr(tot_net_pnl)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with s2:
            st.markdown(
                f"""
                <div class="stat-card" style="border-color: {border_color};">
                    <div class="stat-label">Net Return</div>
                    <div class="stat-value" style="color:{border_color};">{tot_net_pnl_pct:+.2f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with s3:
            st.markdown(
                f"""
                <div class="stat-card" style="border-color: #30363D;">
                    <div class="stat-label">Total Invested</div>
                    <div class="stat-value">{format_compact_inr(tot_invested)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with top_col2:
    i1, i2, i3 = st.columns(3)
    for idx_col, name in zip([i1, i2, i3], ["Sensex", "Nifty 50", "Bank Nifty"]):
        data = index_data.get(name, {"val": 0.0, "chg": 0.0, "pct": 0.0})
        idx_color = (
            APP_CONFIG["COLORS"]["PROFIT_GREEN"]
            if data["chg"] >= 0
            else APP_CONFIG["COLORS"]["LOSS_RED"]
        )
        idx_sign = "+" if data["chg"] >= 0 else ""

        idx_col.markdown(
            f"""
            <div class="index-card">
                <div class="index-label">{name}</div>
                <div class="index-val">{data['val']:,.0f}</div>
                <div class="index-chg" style="color:{idx_color};">{idx_sign}{data['chg']:,.0f} ({idx_sign}{data['pct']:.1f}%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- CONSTRUCT & RENDER TABLES ---
if not df.empty:
    winning_df = df[df["Raw_NetPnL"] > 0]
    losing_df = df[df["Raw_NetPnL"] < 0]

    lbl_sl = APP_CONFIG["LABELS"]["SL"]
    lbl_tsl = APP_CONFIG["LABELS"]["TSL"]
    lbl_t1 = APP_CONFIG["LABELS"]["T1"]
    lbl_t2 = APP_CONFIG["LABELS"]["T2"]

    win_invested = winning_df["Raw_Invested"].sum()
    win_gross = winning_df["Raw_PnL"].sum()
    win_net = winning_df["Raw_NetPnL"].sum()

    loss_invested = losing_df["Raw_Invested"].sum()
    loss_gross = losing_df["Raw_PnL"].sum()
    loss_net = losing_df["Raw_NetPnL"].sum()

    totals_rows = [
        {
            "Symbol": APP_CONFIG["LABELS"]["SUMMARY_WIN"],
            "Type": "-",
            "Status": "Summary",
            "Qty": winning_df["Qty"].sum(),
            "Avg Buy (₹)": None,
            "Invested (₹)": win_invested,
            "LTP (₹)": None,
            "Current Val (₹)": winning_df["Raw_Current"].sum(),
            "Weight (%)": round((win_invested / tot_invested * 100) if tot_invested > 0 else 0, 2),
            lbl_sl: None,
            lbl_tsl: None,
            lbl_t1: None,
            lbl_t2: None,
            "Expenses (₹)": winning_df["Raw_Expenses"].sum(),
            "Gross P&L (₹)": win_gross,
            "Gross P&L (%)": (win_gross / win_invested * 100) if win_invested > 0 else 0.0,
            "Net P&L (₹)": win_net,
            "Net P&L (%)": (win_net / win_invested * 100) if win_invested > 0 else 0.0,
        },
        {
            "Symbol": APP_CONFIG["LABELS"]["SUMMARY_LOSS"],
            "Type": "-",
            "Status": "Summary",
            "Qty": losing_df["Qty"].sum(),
            "Avg Buy (₹)": None,
            "Invested (₹)": loss_invested,
            "LTP (₹)": None,
            "Current Val (₹)": losing_df["Raw_Current"].sum(),
            "Weight (%)": round((loss_invested / tot_invested * 100) if tot_invested > 0 else 0, 2),
            lbl_sl: None,
            lbl_tsl: None,
            lbl_t1: None,
            lbl_t2: None,
            "Expenses (₹)": losing_df["Raw_Expenses"].sum(),
            "Gross P&L (₹)": loss_gross,
            "Gross P&L (%)": (loss_gross / loss_invested * 100) if loss_invested > 0 else 0.0,
            "Net P&L (₹)": loss_net,
            "Net P&L (%)": (loss_net / loss_invested * 100) if loss_invested > 0 else 0.0,
        },
        {
            "Symbol": APP_CONFIG["LABELS"]["SUMMARY_NET"],
            "Type": "-",
            "Status": "Summary",
            "Qty": df["Qty"].sum(),
            "Avg Buy (₹)": None,
            "Invested (₹)": tot_invested,
            "LTP (₹)": None,
            "Current Val (₹)": tot_current,
            "Weight (%)": 100.0,
            lbl_sl: None,
            lbl_tsl: None,
            lbl_t1: None,
            lbl_t2: None,
            "Expenses (₹)": tot_expenses,
            "Gross P&L (₹)": tot_gross_pnl,
            "Gross P&L (%)": (tot_gross_pnl / tot_invested * 100) if tot_invested > 0 else 0.0,
            "Net P&L (₹)": tot_net_pnl,
            "Net P&L (%)": tot_net_pnl_pct,
        },
    ]

    # Safely create df_table based on current preset
    if st.session_state.table_view_preset == "📋 Full Detail View":
        df_table = pd.concat([df, pd.DataFrame(totals_rows)], ignore_index=True)
    else:
        df_table = df.copy()

    if st.session_state.show_table:
        if st.session_state.table_view_preset == "🔍 Main Focus View":
            display_cols = [
                "Symbol",
                "Qty",
                "Avg Buy (₹)",
                "LTP (₹)",
                "Net P&L (₹)",
                "Net P&L (%)",
            ]
        else:
            display_cols = [
                "Symbol",
                "Type",
                "Qty",
                "Avg Buy (₹)",
                "Invested (₹)",
                "LTP (₹)",
                "Current Val (₹)",
                "Weight (%)",
                lbl_sl,
                lbl_tsl,
                lbl_t1,
                lbl_t2,
                "Expenses (₹)",
                "Gross P&L (₹)",
                "Gross P&L (%)",
                "Net P&L (₹)",
                "Net P&L (%)",
            ]

        render_df = df_table[display_cols].copy()

        currency_cols = [
            "Avg Buy (₹)",
            "Invested (₹)",
            "LTP (₹)",
            "Current Val (₹)",
            lbl_sl,
            lbl_tsl,
            lbl_t1,
            lbl_t2,
            "Expenses (₹)",
        ]
        for col in currency_cols:
            if col in render_df.columns:
                render_df[col] = render_df[col].apply(
                    lambda x: f"₹{x:,.2f}"
                    if pd.notnull(x) and isinstance(x, (int, float))
                    else "-"
                )

        if "Weight (%)" in render_df.columns:
            render_df["Weight (%)"] = render_df["Weight (%)"].apply(
                lambda x: f"{x:.1f}%" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
            )

        tbl_font_rem = round(0.9 * fs_table, 2)
        tbl_header_rem = round(0.95 * fs_table, 2)
        padding_v = round(0.3 * fs_table, 2)

        html_rows = []
        header_cells = "".join([f"<th>{col}</th>" for col in display_cols])
        html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")

        html_rows.append("<tbody>")
        for idx, row in render_df.iterrows():
            row_cells = []
            is_summary = df_table.loc[idx, "Status"] == "Summary" if "Status" in df_table.columns else False
            row_bg = (
                f"background-color: {APP_CONFIG['COLORS']['BG_CARD']}; font-weight: bold;"
                if is_summary
                else ""
            )

            for col in display_cols:
                val = row[col]
                cell_style = ""

                if col == "Type" and val in ["DELIVERY", "INTRADAY"]:
                    val = f"<span style='font-size:0.8em; padding:2px 5px; border-radius:3px; background-color:#1E293B; color:#A1A1AA;'>{val}</span>"

                elif col in ["Gross P&L (₹)", "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)"] and isinstance(val, (int, float)):
                    color = (
                        APP_CONFIG["COLORS"]["PROFIT_GREEN"]
                        if val >= 0
                        else APP_CONFIG["COLORS"]["LOSS_RED"]
                    )
                    sign_val = "+" if val >= 0 else ""
                    val = f"{sign_val}₹{val:,.2f}" if "₹" in col else f"{val:+.2f}%"
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
                margin-bottom: 0.2rem;
                background-color: {APP_CONFIG["COLORS"]["BG_DARK"]};
                color: #FFFFFF;
                font-family: Source Sans Pro, sans-serif;
            }}
            .tv-portfolio-table th {{
                background-color: {APP_CONFIG["COLORS"]["HEADER_BG"]};
                color: {APP_CONFIG["COLORS"]["TEXT_MUTED"]};
                font-size: {tbl_header_rem}rem !important;
                font-weight: 800;
                padding: {padding_v}rem 0.5rem !important;
                text-align: left;
                border-bottom: 2px solid {APP_CONFIG["COLORS"]["HEADER_BORDER"]};
                white-space: nowrap;
            }}
            .tv-portfolio-table td {{
                font-size: {tbl_font_rem}rem !important;
                padding: {padding_v}rem 0.5rem !important;
                border-bottom: 1px solid {APP_CONFIG["COLORS"]["HEADER_BG"]};
                white-space: nowrap;
            }}
            .tv-portfolio-table tr:hover {{
                background-color: {APP_CONFIG["COLORS"]["HEADER_BG"]};
            }}
        </style>
        <div style="overflow-x: auto; width: 100%;">
            <table class="tv-portfolio-table">
                {"".join(html_rows)}
            </table>
        </div>
        """

        with st.expander("📋 Main Portfolio Table", expanded=True):
            st.markdown(full_html_table, unsafe_allow_html=True)
            
# --- STREAMLINED EOD JOURNAL EXPORT ---
if not df.empty:
    st.sidebar.divider()
    st.sidebar.subheader("📥 Journal Export")

    export_cols = [
        "Symbol", "Type", "Qty", "Avg Buy (₹)", "Invested (₹)",
        "LTP (₹)", "Current Val (₹)", "Weight (%)",
        lbl_sl, lbl_tsl, lbl_t1, lbl_t2,
        "Expenses (₹)", "Gross P&L (₹)", "Gross P&L (%)", "Net P&L (₹)", "Net P&L (%)"
    ]

    journal_df = df[export_cols].copy()
    today_stamp = datetime.now().strftime("%Y-%m-%d")
    journal_df.insert(0, "Date", today_stamp)
    journal_df["Comments"] = ""

    csv_data = journal_df.to_csv(index=False).encode("utf-8")

    st.sidebar.download_button(
        label=f"📥 Export EOD Journal ({today_stamp})",
        data=csv_data,
        file_name=f"foliopulse_journal_{today_stamp}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# --- FORCE REFRESH / CACHE CLEAR CONTROL ---
st.sidebar.divider()
if st.sidebar.button("🔄 Force Data Refresh", type="secondary", use_container_width=True, help="Purge server cache & re-fetch from Yahoo Finance"):
    st.cache_data.clear()
    st.session_state.stock_cache = {}
    st.rerun()

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
                increasing_line_color=APP_CONFIG["COLORS"]["PROFIT_GREEN"],
                decreasing_line_color=APP_CONFIG["COLORS"]["LOSS_RED"],
            )
        )
        dates = list(df_10d.index)
    else:
        dates = [datetime.now().strftime("%Y-%m-%d")]

    lbl_sl = APP_CONFIG["LABELS"]["SL"]
    lbl_tsl = APP_CONFIG["LABELS"]["TSL"]
    lbl_buy = APP_CONFIG["LABELS"]["BUY"]
    lbl_ltp = APP_CONFIG["LABELS"]["LTP"]
    lbl_t1 = APP_CONFIG["LABELS"]["T1"]
    lbl_t2 = APP_CONFIG["LABELS"]["T2"]

    sl_val = float(row.get(lbl_sl, 0.0))
    tsl_val = float(row.get(lbl_tsl, 0.0))
    buy_val = float(row.get("Avg Buy (₹)", 0.0))
    ltp_val = float(row.get("LTP (₹)", 0.0))
    qty = int(row.get("Qty", 0))
    trade_type = str(row.get("Type", "DELIVERY")).upper().strip()

    invested = buy_val * qty

    ltp_exp_details = compute_trade_expenses_detailed(qty, buy_val, ltp_val, trade_type)
    ltp_net_pnl = ((ltp_val * qty) - invested) - ltp_exp_details["total_expenses"]
    ltp_net_pct = (ltp_net_pnl / invested * 100) if invested > 0 else 0.0

    ltp_net_color = (
        APP_CONFIG["COLORS"]["PROFIT_GREEN"]
        if ltp_net_pnl >= 0
        else APP_CONFIG["COLORS"]["LOSS_RED"]
    )
    ltp_net_sign = "+" if ltp_net_pnl >= 0 else ""

    t1_val = float(row.get(lbl_t1, 0.0))
    t2_val = float(row.get(lbl_t2, 0.0))

    raw_levels = [
        {
            "name": lbl_sl,
            "val": sl_val,
            "color": APP_CONFIG["COLORS"]["SL_ORANGE"],
            "dash": "dash",
            "width": 1.5,
        },
        {
            "name": lbl_tsl,
            "val": tsl_val,
            "color": APP_CONFIG["COLORS"]["TSL_YELLOW"],
            "dash": "dash",
            "width": 1.5,
        },
        {
            "name": lbl_buy,
            "val": buy_val,
            "color": APP_CONFIG["COLORS"]["BUY_BLUE"],
            "dash": "solid",
            "width": 2.0,
        },
        {
            "name": lbl_t1,
            "val": t1_val,
            "color": APP_CONFIG["COLORS"]["PROFIT_GREEN"],
            "dash": "dash",
            "width": 1.5,
        },
        {
            "name": lbl_t2,
            "val": t2_val,
            "color": APP_CONFIG["COLORS"]["PROFIT_GREEN"],
            "dash": "dash",
            "width": 1.5,
        },
        {
            "name": lbl_ltp,
            "val": ltp_val,
            "color": APP_CONFIG["COLORS"]["LTP_RED"],
            "dash": "dot",
            "width": 2.5,
        },
    ]

    horizontal_levels = []
    for item in raw_levels:
        if item["val"] <= 0:
            continue
        if item["name"] == lbl_tsl and sl_val > 0 and abs(tsl_val - sl_val) < 0.01:
            continue
        if item["name"] == lbl_t2 and t1_val > 0 and abs(t2_val - t1_val) < 0.01:
            continue
        horizontal_levels.append(item)

    # --- ANCHOR DATES ---
    num_dates = len(dates)
    left_anchor_date = dates[0]
    # Move LTP further right to dates[2] (or dates[3] if available) to avoid overlap with Buy
    ltp_anchor_index = min(2, num_dates - 1) if num_dates > 2 else (1 if num_dates > 1 else 0)
    ltp_anchor_date = dates[ltp_anchor_index]

    c_title_size = int(14 * fs_chart)
    c_badge_size = int(11 * fs_chart)
    c_axis_size = int(11 * fs_chart)

    # Detect if Buy and LTP values are very close (< 1.5% difference)
    prices_are_close = buy_val > 0 and abs(ltp_val - buy_val) / buy_val < 0.015

    # Draw horizontal guide lines
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

    # COLUMN 1 (dates[0]): Buy Price, Targets (T1, T2), Stop-Losses (SL, TSL)
    for item in horizontal_levels:
        if item["name"] == lbl_ltp:
            continue

        if item["name"] == lbl_buy:
            badge_text = f" <span style='color:{APP_CONFIG['COLORS']['BUY_BLUE']};'><b>BUY: {qty} Qty @ ₹{buy_val:,.2f}</b></span> "
            border_c = APP_CONFIG["COLORS"]["BUY_BLUE"]
            text_c = APP_CONFIG["COLORS"]["BUY_BLUE"]
            # If prices are very close, anchor Buy slightly lower to avoid collision
            y_anchor_buy = "top" if prices_are_close else "middle"
        else:
            level_exp_details = compute_trade_expenses_detailed(qty, buy_val, item["val"], trade_type)
            level_gross_pnl = (item["val"] - buy_val) * qty
            level_net_pnl = level_gross_pnl - level_exp_details["total_expenses"]
            level_net_pct = (level_net_pnl / invested * 100) if invested > 0 else 0.0

            lvl_color = (
                APP_CONFIG["COLORS"]["PROFIT_GREEN"]
                if level_net_pnl >= 0
                else APP_CONFIG["COLORS"]["LOSS_RED"]
            )
            lvl_sign = "+" if level_net_pnl >= 0 else ""

            badge_text = (
                f" <b>{item['name']}</b> | "
                f"<span style='color:{lvl_color};'><b>{lvl_sign}₹{level_net_pnl:,.2f} ({level_net_pct:+.1f}%)</b></span> "
            )
            border_c = item["color"]
            text_c = item["color"]
            y_anchor_buy = "middle"

        fig.add_annotation(
            x=left_anchor_date,
            y=item["val"],
            text=badge_text,
            showarrow=False,
            font=dict(color=text_c, size=c_badge_size),
            bgcolor="#161B22",
            bordercolor=border_c,
            borderwidth=1.5,
            borderpad=3,
            yanchor=y_anchor_buy,
            xanchor="left",
        )

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

    # COLUMN 2 (dates[2]): Live LTP Badge shifted right with anti-overlap vertical alignment
    ltp_item = next((item for item in horizontal_levels if item["name"] == lbl_ltp), None)
    if ltp_item:
        badge_text_ltp = (
            f" <b>{lbl_ltp}</b> | "
            f"<span style='color:{ltp_net_color};'><b>{ltp_net_sign}₹{ltp_net_pnl:,.2f} ({ltp_net_pct:+.1f}%)</b></span> "
        )

        # If prices are close, float LTP slightly higher
        y_anchor_ltp = "bottom" if prices_are_close else "middle"

        fig.add_annotation(
            x=ltp_anchor_date,
            y=ltp_item["val"],
            text=badge_text_ltp,
            showarrow=False,
            font=dict(color=APP_CONFIG["COLORS"]["LTP_RED"], size=c_badge_size + 1),
            bgcolor="#161B22",
            bordercolor=APP_CONFIG["COLORS"]["LTP_RED"],
            borderwidth=2.0,
            borderpad=4,
            yanchor=y_anchor_ltp,
            xanchor="left",
        )

        fig.add_annotation(
            xref="paper",
            x=1.002,
            y=ltp_item["val"],
            text=f" <b>{ltp_item['val']:,.2f}</b> ",
            showarrow=False,
            font=dict(color="#FFFFFF", size=c_badge_size + 1),
            bgcolor=APP_CONFIG["COLORS"]["LTP_RED"],
            xanchor="left",
            yanchor="middle",
        )

    if auto_zoom_risk_range and sl_val > 0 and row.get(lbl_t2, 0) > 0:
        min_bound = sl_val * 0.98
        max_bound = float(row[lbl_t2]) * 1.02
    else:
        min_bound = (
            min(df_10d["Low"].min(), sl_val)
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else sl_val
        )
        max_bound = (
            max(df_10d["High"].max(), float(row.get(lbl_t2, 0)))
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else float(row.get(lbl_t2, 0))
        )

    fig.update_layout(
        title=dict(
            text=f"<b>{row['Symbol']}</b> [{trade_type}] ({row['Status']}) | P&L: <span style='color:{ltp_net_color};'><b>{ltp_net_sign}₹{ltp_net_pnl:,.2f} ({ltp_net_pct:+.1f}%)</b></span>",
            font=dict(size=c_title_size),
        ),
        xaxis=dict(
            type="category",
            rangeslider=dict(visible=False),
            tickfont=dict(size=c_axis_size),
            showline=True,
            linewidth=1.0,
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
            linewidth=1.0,
            linecolor="#64748B",
            mirror=True,
        ),
        height=int(360 * fs_chart),
        showlegend=False,
        margin=dict(l=10, r=70, t=35, b=20),
    )

    return fig

# --- CHARTS RENDER SECTION ---
if not df.empty:
    stock_rows_only = df[df["Status"] != "Summary"]

    num_cols = chart_cols_per_row
    cols = st.columns(num_cols)
    for idx, (_, row) in enumerate(stock_rows_only.iterrows()):
        col_idx = idx % num_cols
        with cols[col_idx]:
            st.plotly_chart(create_candlestick_chart(row), use_container_width=True)

# =========================================================
# FLOATING BOTTOM-RIGHT STICKY CARD (RENDERED AT VERY END)
# =========================================================
if st.session_state.is_pnl_detached:
    st.markdown(
        f"""
        <style>
            /* Force GPU layer promotion to stick to mobile Visual Viewport */
            .sticky-pnl-card-wrapper {{
                position: fixed !important;
                bottom: 24px !important;
                right: 24px !important;
                z-index: 9999999 !important;
                -webkit-transform: translate3d(0, 0, 0);
                transform: translate3d(0, 0, 0);
                will-change: transform;
            }}
            .sticky-pnl-card {{
                background-color: {APP_CONFIG['COLORS']['BG_DARK']} !important;
                border: 2px solid {border_color} !important;
                border-radius: 12px !important;
                padding: 10px 18px !important;
                box-shadow: 0 8px 24px rgba(0,0,0,0.85) !important;
                backdrop-filter: blur(8px) !important;
                -webkit-backdrop-filter: blur(8px) !important;
                font-family: Source Sans Pro, -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
                display: flex !important;
                align-items: center !important;
                gap: 16px !important;
            }}
            .sticky-pnl-label {{
                font-size: 0.75rem !important;
                color: {APP_CONFIG['COLORS']['TEXT_MUTED']} !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
            }}
            .sticky-pnl-val {{
                font-size: 1.25rem !important;
                font-weight: 800 !important;
                color: {border_color} !important;
                white-space: nowrap !important;
            }}
            .dock-link-btn {{
                text-decoration: none !important;
                color: #9CA3AF !important;
                background-color: #1F2937 !important;
                border: 1px solid #374151 !important;
                border-radius: 6px !important;
                padding: 3px 8px !important;
                font-size: 12px !important;
                font-weight: bold !important;
                transition: all 0.2s ease !important;
            }}
            .dock-link-btn:hover {{
                border-color: #FFFFFF !important;
                color: #FFFFFF !important;
            }}
        </style>

        <div class="sticky-pnl-card-wrapper">
            <div class="sticky-pnl-card">
                <div>
                    <div class="sticky-pnl-label">NET P&L</div>
                    <div class="sticky-pnl-val">
                        {format_compact_inr(tot_net_pnl)} <span style="font-size: 0.95rem;">({sign}{tot_net_pnl_pct:.2f}%)</span>
                    </div>
                </div>
                <a href="?dock_pnl=true" target="_self" class="dock-link-btn" title="Dock Back to Header">↙</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )