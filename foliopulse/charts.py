"""Plotly candlestick chart with risk-level overlays for one holding."""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go

from foliopulse.config import APP_CONFIG
from foliopulse.expenses import INSTRUMENT_EQUITY, compute_trade_expenses_detailed


def format_chart_date_label(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b")
    except (ValueError, TypeError):
        return date_str


def create_candlestick_chart(row, font_scale=1.0, auto_zoom=True):
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
    instrument = str(row.get("Instrument", INSTRUMENT_EQUITY)).upper().strip()

    invested = buy_val * qty

    breakeven_val = compute_trade_expenses_detailed(qty, buy_val, buy_val, trade_type, instrument)["breakeven_price"]

    ltp_exp_details = compute_trade_expenses_detailed(qty, buy_val, ltp_val, trade_type, instrument)
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
            "name": APP_CONFIG["LABELS"]["BREAKEVEN"],
            "val": breakeven_val,
            "color": APP_CONFIG["COLORS"]["BREAKEVEN_GRAY"],
            "dash": "dash",
            "width": 1.5,
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

    num_dates = len(dates)
    left_anchor_date = dates[0]
    ltp_anchor_index = min(2, num_dates - 1) if num_dates > 2 else (1 if num_dates > 1 else 0)
    ltp_anchor_date = dates[ltp_anchor_index]

    c_title_size = int(14 * font_scale)
    c_badge_size = int(11 * font_scale)
    c_axis_size = int(11 * font_scale)

    prices_are_close = buy_val > 0 and abs(ltp_val - buy_val) / buy_val < 0.015
    breakeven_close_to_buy = buy_val > 0 and abs(breakeven_val - buy_val) / buy_val < 0.025

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

    for item in horizontal_levels:
        if item["name"] == lbl_ltp:
            continue

        y_shift_buy = 0

        if item["name"] == lbl_buy:
            badge_text = f" <span style='color:{APP_CONFIG['COLORS']['BUY_BLUE']};'><b>BUY: {qty} Qty @ ₹{buy_val:,.2f}</b></span> "
            border_c = APP_CONFIG["COLORS"]["BUY_BLUE"]
            text_c = APP_CONFIG["COLORS"]["BUY_BLUE"]
            if prices_are_close or breakeven_close_to_buy:
                y_anchor_buy = "top"
                y_shift_buy = -4
            else:
                y_anchor_buy = "middle"
        else:
            level_exp_details = compute_trade_expenses_detailed(qty, buy_val, item["val"], trade_type, instrument)
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
                f"<span style='color:{lvl_color};'><b>{lvl_sign}₹{round(level_net_pnl):,} ({level_net_pct:+.1f}%)</b></span> "
            )
            border_c = item["color"]
            text_c = item["color"]

            if item["name"] == APP_CONFIG["LABELS"]["BREAKEVEN"] and breakeven_close_to_buy:
                y_anchor_buy = "bottom"
                y_shift_buy = 4
            else:
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
            yshift=y_shift_buy,
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
            yanchor=y_anchor_buy,
            yshift=y_shift_buy,
        )

    ltp_item = next((item for item in horizontal_levels if item["name"] == lbl_ltp), None)
    if ltp_item:
        badge_text_ltp = (
            f" <b>{lbl_ltp}</b> | "
            f"<span style='color:{ltp_net_color};'><b>{ltp_net_sign}₹{round(ltp_net_pnl):,} ({ltp_net_pct:+.1f}%)</b></span> "
        )

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

    target_val = float(row.get(lbl_t2, 0.0)) if float(row.get(lbl_t2, 0.0)) > 0 else float(row.get(lbl_t1, 0.0))

    if auto_zoom and sl_val > 0 and target_val > 0:
        lower_bound_ref = ltp_val if (ltp_val > 0 and ltp_val < sl_val) else sl_val
        min_bound = lower_bound_ref * 0.98
        max_bound = target_val * 1.02
    else:
        min_bound = (
            min(df_10d["Low"].min(), sl_val if sl_val > 0 else ltp_val, ltp_val)
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else ltp_val * 0.98
        )
        max_bound = (
            max(df_10d["High"].max(), target_val if target_val > 0 else ltp_val, ltp_val)
            if isinstance(df_10d, pd.DataFrame) and not df_10d.empty
            else ltp_val * 1.02
        )

    fig.update_layout(
        title=dict(
            text=f"<b>{row['Symbol']}</b> [{trade_type}] ({row['Status']}) | P&L: <span style='color:{ltp_net_color};'><b>{ltp_net_sign}₹{round(ltp_net_pnl):,} ({ltp_net_pct:+.1f}%)</b></span>",
            font=dict(size=c_title_size),
        ),
        xaxis=dict(
            type="category",
            tickvals=dates,
            ticktext=[format_chart_date_label(d) for d in dates],
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
        height=int(360 * font_scale),
        showlegend=False,
        margin=dict(l=10, r=70, t=35, b=20),
    )

    return fig
