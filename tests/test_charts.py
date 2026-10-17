import plotly.graph_objects as go
import pandas as pd

from foliopulse.charts import create_candlestick_chart
from foliopulse.config import APP_CONFIG

LBL = APP_CONFIG["LABELS"]


def make_row(with_history=True):
    candles = pd.DataFrame(
        {
            "Open": [100.0, 102.0, 104.0],
            "High": [103.0, 105.0, 107.0],
            "Low": [99.0, 101.0, 103.0],
            "Close": [102.0, 104.0, 106.0],
            "Volume": [1, 1, 1],
        },
        index=["2026-10-13", "2026-10-14", "2026-10-15"],
    )
    return {
        "Qty": 10,
        "Avg Buy (₹)": 100.0,
        "LTP (₹)": 106.0,
        LBL["SL"]: 95.0,
        LBL["TSL"]: 97.0,
        LBL["T1"]: 110.0,
        LBL["T2"]: 115.0,
        "Type": "DELIVERY",
        "Instrument": "EQUITY",
        "Symbol": "TITAN",
        "Status": "🟢 Live",
        "df_10d": candles if with_history else pd.DataFrame(),
    }


def test_chart_has_candlestick_trace_when_history_present():
    fig = create_candlestick_chart(make_row(with_history=True))
    assert isinstance(fig, go.Figure)
    assert any(isinstance(t, go.Candlestick) for t in fig.data)


def test_chart_renders_without_history():
    fig = create_candlestick_chart(make_row(with_history=False))
    assert isinstance(fig, go.Figure)
    assert not any(isinstance(t, go.Candlestick) for t in fig.data)


def test_font_scale_changes_title_size():
    small = create_candlestick_chart(make_row(), font_scale=1.0)
    large = create_candlestick_chart(make_row(), font_scale=2.0)
    assert large.layout.height > small.layout.height


def test_auto_zoom_can_be_disabled():
    assert isinstance(create_candlestick_chart(make_row(), auto_zoom=False), go.Figure)
