"""Number formatting helpers for the UI."""

from foliopulse.config import APP_CONFIG


def format_compact_inr(val, decimals=0):
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
        return f"{sign}{sym}{abs_val:,.{decimals}f}"
