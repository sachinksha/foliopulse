"""Main portfolio table with a chart switch on each stock row (Streamlit).

Rows are laid out with st.columns, not one HTML block, so each row can hold a
real st.toggle. Cell formatting comes from foliopulse.table_format.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from foliopulse.config import APP_CONFIG
from foliopulse.table_format import TOGGLE_HEADER, format_cell, view_columns


def render_portfolio_table(
    df_table,
    preset: str,
    font_scale: float,
    on_toggle: Callable,
) -> None:
    """Render the table. ``on_toggle(symbol, widget_key)`` is called when a switch changes."""
    labels = APP_CONFIG["LABELS"]
    colors = APP_CONFIG["COLORS"]
    columns = view_columns(preset, labels)

    font_rem = round(0.9 * font_scale, 2)
    header_rem = round(0.95 * font_scale, 2)
    pad_rem = round(0.3 * font_scale, 2)

    weights = [1.3 if c == "Symbol" else 1.0 for c in columns] + [1.2]

    header = st.columns(weights)
    for cell, name in zip(header, columns + [TOGGLE_HEADER]):
        cell.markdown(
            f"<div style='font-size:{header_rem}rem; font-weight:800; color:{colors['TEXT_MUTED']}; "
            f"border-bottom:2px solid {colors['HEADER_BORDER']}; padding:{pad_rem}rem 0.25rem; "
            f"white-space:nowrap;'>{name}</div>",
            unsafe_allow_html=True,
        )

    for _, row in df_table.iterrows():
        is_summary = row.get("Status") == "Summary"
        row_style = f"background-color:{colors['BG_CARD']}; font-weight:bold;" if is_summary else ""
        cells = st.columns(weights)

        for cell, col in zip(cells, columns):
            text, cell_style = format_cell(col, row[col], labels)
            cell.markdown(
                f"<div style='font-size:{font_rem}rem; padding:{pad_rem}rem 0.25rem; "
                f"border-bottom:1px solid {colors['HEADER_BG']}; white-space:nowrap; "
                f"{row_style} {cell_style}'>{text}</div>",
                unsafe_allow_html=True,
            )

        if not is_summary:
            symbol = row["RawSymbol"]
            visible = bool(row["Show Chart"])
            widget_key = f"chart_toggle_{symbol}_{int(visible)}"
            with cells[-1]:
                st.toggle(
                    f"Chart {row['Symbol']}",
                    value=visible,
                    key=widget_key,
                    label_visibility="collapsed",
                    on_change=on_toggle,
                    args=(symbol, widget_key),
                )
