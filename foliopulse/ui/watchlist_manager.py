"""Watchlist & script sequence manager dialog (Streamlit)."""

import json

import streamlit as st

from foliopulse.config import APP_CONFIG
from foliopulse.expenses import (
    INSTRUMENT_EQUITY,
    INSTRUMENT_TYPES,
    compute_trade_expenses_detailed,
    price_for_target_net_pnl_pct,
)
from foliopulse.models import instrument_from_quote_type, instrument_index, preserved_chart_flag


@st.dialog("🛠️ Watchlist & Script Sequence Manager", width="large")
def open_watchlist_manager(save_config, search_ticker_symbols):
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
            curr_instrument = item.get("instrument_type", INSTRUMENT_EQUITY)

            if is_editing:
                edit_sym = c_sym.text_input("Symbol", value=item["symbol"], key=f"edit_sym_{i}")
                edit_type = c_type.selectbox(
                    "Type", options=["DELIVERY", "INTRADAY"], index=0 if curr_trade_type == "DELIVERY" else 1, key=f"edit_ttype_{i}"
                )
                edit_instrument = c_type.selectbox(
                    "Instrument", options=INSTRUMENT_TYPES,
                    index=instrument_index(curr_instrument), key=f"edit_instr_{i}",
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
                            "instrument_type": edit_instrument,
                            "avg_buy_price": float(edit_buy),
                            "quantity": int(edit_qty),
                            "stop_loss": float(edit_sl),
                            "trailing_sl": float(edit_tsl),
                            "target_1": float(edit_t1),
                            "target_2": float(edit_t2),
                            "manual_ltp": float(edit_manual_ltp),
                            **preserved_chart_flag(item),
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
                if curr_instrument != INSTRUMENT_EQUITY:
                    type_badge += f" · {curr_instrument.replace('_', ' ').title()}"
                c_type.markdown(f"<small><b>{type_badge}</b></small>", unsafe_allow_html=True)
                
                c_buy.markdown(f"₹{item['avg_buy_price']:,.2f}")
                c_qty.markdown(f"{item['quantity']}")
                c_risk.markdown(
                    f"<small>{lbl_sl}: ₹{item.get('stop_loss',0):,.2f} | {lbl_tsl}: ₹{item.get('trailing_sl',0):,.2f}<br>"
                    f"{lbl_t1}: ₹{item.get('target_1',0):,.2f} | {lbl_t2}: ₹{item.get('target_2',0):,.2f} | Manual: ₹{item.get('manual_ltp',0):,.2f}</small>",
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
    selected_quote_type = ""
    if search_query:
        search_results = search_ticker_symbols(search_query)
        if search_results:
            options_dict = {item["display"]: item for item in search_results}
            selected_display = st.selectbox("Select matching script:", options=list(options_dict.keys()))
            chosen = options_dict[selected_display]
            selected_symbol = chosen["symbol"]
            selected_quote_type = chosen.get("quote_type", "")
        else:
            st.warning("No ticker results found. Enter ticker manually below.")
            selected_symbol = search_query.upper().strip()

    add_instrument = st.selectbox(
        "Instrument",
        options=INSTRUMENT_TYPES,
        index=instrument_index(instrument_from_quote_type(selected_quote_type)),
        key=f"add_instr_{selected_symbol}",
        help="Mutual funds and SIFs skip Zerodha equity charges. Yahoo does not label SIFs, so pick SIF manually.",
    )

    ac1, ac2, ac3, ac4 = st.columns(4)
    add_type = ac1.selectbox("Trade Type", options=["DELIVERY", "INTRADAY"], index=0, key="add_script_type")
    add_buy = ac2.number_input("Avg Buy Price (₹)", min_value=0.0, step=1.0, key="add_script_buy")
    add_qty = ac3.number_input("Quantity", min_value=1, value=10, step=1, key="add_script_qty")
    add_mltp = ac4.number_input("Manual LTP (₹)", min_value=0.0, step=1.0, key="add_script_mltp")

    suggested_sl = price_for_target_net_pnl_pct(int(add_qty), float(add_buy), -2, add_type, add_instrument)
    suggested_t1 = price_for_target_net_pnl_pct(int(add_qty), float(add_buy), 5, add_type, add_instrument)
    preview_breakeven = compute_trade_expenses_detailed(
        int(add_qty), float(add_buy), float(add_buy), add_type, add_instrument
    )["breakeven_price"]

    if add_buy > 0:
        st.caption(
            f"📍 Break-even: **₹{preview_breakeven:,.2f}** &nbsp;|&nbsp; "
            f"Suggested {APP_CONFIG['LABELS']['SL']} (−2% net): **₹{suggested_sl:,.2f}** &nbsp;|&nbsp; "
            f"Suggested {APP_CONFIG['LABELS']['T1']} (+5% net): **₹{suggested_t1:,.2f}**",
            unsafe_allow_html=True,
        )

    suggestion_key_suffix = f"{add_type}_{add_buy}_{add_qty}"

    with st.form("add_script_form"):
        add_sym = st.text_input("Ticker Symbol", value=selected_symbol)

        rc1, rc2, rc3, rc4 = st.columns(4)
        add_sl = rc1.number_input(
            f"{APP_CONFIG['LABELS']['SL']} (₹)", min_value=0.0, step=1.0,
            value=suggested_sl, key=f"add_sl_{suggestion_key_suffix}",
        )
        add_tsl = rc2.number_input(f"{APP_CONFIG['LABELS']['TSL']} (₹)", min_value=0.0, step=1.0)
        add_t1 = rc3.number_input(
            f"{APP_CONFIG['LABELS']['T1']} (₹)", min_value=0.0, step=1.0,
            value=suggested_t1, key=f"add_t1_{suggestion_key_suffix}",
        )
        add_t2 = rc4.number_input(f"{APP_CONFIG['LABELS']['T2']} (₹)", min_value=0.0, step=1.0)

        submitted = st.form_submit_button("➕ Add Script to Watchlist", type="primary")
        if submitted and add_sym:
            new_item = {
                "symbol": add_sym.upper().strip(),
                "trade_type": add_type,
                "instrument_type": add_instrument,
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
