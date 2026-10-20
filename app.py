from datetime import datetime
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import pytz
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from foliopulse.charts import create_candlestick_chart
from foliopulse.config import APP_CONFIG
from foliopulse.formatting import format_compact_inr
from foliopulse.market_data import MARKET_INDICES, fetch_index_quotes, get_history, search_symbols
from foliopulse.market_hours import is_market_open
from foliopulse.models import Holding
from foliopulse.portfolio import build_portfolio
from foliopulse.storage import ConfigStore
from foliopulse.ui.theme import dashboard_css
from foliopulse.ui.watchlist_manager import open_watchlist_manager

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

# --- CLOUD CONFIG SYNC ---
store = ConfigStore(db)


def save_config(config_dict):
    st.session_state.config = config_dict
    try:
        store.save(user_email, config_dict)
    except Exception as e:
        st.error(f"Failed to sync with cloud: {e}")


if "config" not in st.session_state:
    st.session_state.config = store.load(user_email)

if "stock_cache" not in st.session_state:
    st.session_state.stock_cache = {}

st.markdown(dashboard_css(fs_chart), unsafe_allow_html=True)


@st.cache_data(ttl=300)
def search_ticker_symbols(query):
    return search_symbols(query)


@st.cache_data(ttl=10)
def fetch_market_indices():
    return fetch_index_quotes(MARKET_INDICES)


# --- SIDEBAR HEADER & USER BAR ---
st.sidebar.title(f"📈 {APP_CONFIG['LABELS']['APP_TITLE']}")
st.sidebar.caption(f"👤 Logged in: **{user_email}**")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.logout()

st.sidebar.divider()

if st.sidebar.button("⚙️ Manage Watchlist & Reorder", type="primary", use_container_width=True):
    open_watchlist_manager(save_config, search_ticker_symbols)

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

df, error_logs = build_portfolio(
    [Holding.from_dict(h) for h in st.session_state.config.get("watchlist", [])],
    get_history,
    st.session_state.stock_cache,
    manual_override_active,
)

# --- MARKET STATUS & STALE DATA CALLOUT BANNER ---
india_tz = pytz.timezone("Asia/Kolkata")
last_fetched_time = datetime.now(india_tz).strftime("%I:%M:%S %p IST")

stale_symbols = [
    row["Symbol"] for _, row in df.iterrows() 
    if row.get("Status") == "🔴 Stale"
] if not df.empty else []

if stale_symbols:
    st.error(
        f"⚠️ **STALE DATA WARNING**: Live market data fetch failed for **{', '.join(stale_symbols)}**. "
        f"Showing last known cached prices. (Yahoo Finance API rate-limited or unreachable). "
        f"Try clicking **'🔄 Force Data Refresh'** in the sidebar."
    )
elif error_logs:
    st.warning(f"⚠️ **Market Fetch Notice**: {'; '.join(error_logs)}")

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

# --- TOP STATS & MARKET INDICES HEADER ROW (AGGREGATE UNROUNDED VALUES FIRST) ---
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
        s1, = st.columns(1)
        s1.markdown(
            f"""
            <div class="stat-card" style="border-color: #30363D;">
                <div class="stat-label">Total Invested</div>
                <div class="stat-value">{format_compact_inr(tot_invested, decimals=0)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        s1, s2, s3 = st.columns(3)
        
        with s1:
            st.markdown(
                f"""
                <div class="stat-card" style="border-color: {border_color};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="stat-label">Net P&L</div>
                        <a href="?toggle_pnl_float=true" target="_self" style="text-decoration: none; color: #9CA3AF; font-size: 0.8rem; border: 1px solid #374151; padding: 1px 5px; border-radius: 4px;" title="Detach to Bottom-Right">↗</a>
                    </div>
                    <div class="stat-value" style="color:{border_color};">{format_compact_inr(tot_net_pnl, decimals=0)}</div>
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
                    <div class="stat-value">{format_compact_inr(tot_invested, decimals=0)}</div>
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

        # Retain 2 decimals strictly for Price columns; round non-price totals to whole numbers
        price_cols = ["Avg Buy (₹)", "LTP (₹)", lbl_sl, lbl_tsl, lbl_t1, lbl_t2]
        integer_total_cols = ["Invested (₹)", "Current Val (₹)", "Expenses (₹)"]

        for col in price_cols:
            if col in render_df.columns:
                render_df[col] = render_df[col].apply(
                    lambda x: f"₹{x:,.2f}" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
                )

        for col in integer_total_cols:
            if col in render_df.columns:
                render_df[col] = render_df[col].apply(
                    lambda x: f"₹{round(x):,}" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
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
                    
                    if "₹" in col:
                        # Round Gross & Net P&L to whole integers for main table display
                        val = f"{sign_val}₹{abs(round(val)):,}" if val >= 0 else f"-₹{abs(round(val)):,}"
                    else:
                        val = f"{val:+.2f}%"
                        
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

# --- CHARTS RENDER SECTION ---
if not df.empty:
    stock_rows_only = df[df["Status"] != "Summary"]

    num_cols = chart_cols_per_row
    cols = st.columns(num_cols)
    for idx, (_, row) in enumerate(stock_rows_only.iterrows()):
        col_idx = idx % num_cols
        with cols[col_idx]:
            st.plotly_chart(
                create_candlestick_chart(row, font_scale=fs_chart, auto_zoom=auto_zoom_risk_range),
                use_container_width=True,
            )

# =========================================================
# FLOATING BOTTOM-RIGHT STICKY CARD (RENDERED AT VERY END)
# =========================================================
if st.session_state.is_pnl_detached:
    st.markdown(
        f"""
        <style>
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
                        {format_compact_inr(tot_net_pnl, decimals=0)} <span style="font-size: 0.95rem;">({sign}{tot_net_pnl_pct:.2f}%)</span>
                    </div>
                </div>
                <a href="?dock_pnl=true" target="_self" class="dock-link-btn" title="Dock Back to Header">↙</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )