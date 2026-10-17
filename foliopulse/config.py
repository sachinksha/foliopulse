"""Static app configuration: labels, colors, units, and the default watchlist."""

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
        "BREAKEVEN": "BREAK-EVEN",
        "SUMMARY_WIN": "🟢 TOTAL PROFITS",
        "SUMMARY_LOSS": "🔴 TOTAL LOSSES",
        "SUMMARY_NET": "💼 NET TOTAL",
    },
    "COLORS": {
        "PROFIT_GREEN": "#00CC96",
        "LOSS_RED": "#FF2B2B",
        "SL_ORANGE": "#FF872B",
        "TSL_YELLOW": "#77671F",
        "BREAKEVEN_GRAY": "#94A3B8",
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


TIMEZONE_NAME = "Asia/Kolkata"
