"""Indian market session detection (NSE hours and holidays)."""

from datetime import datetime

import pytz


NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-08-26", "2026-09-14", "2026-10-02",
    "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
}

def is_market_open(now=None):
    india_tz = pytz.timezone("Asia/Kolkata")
    if now is None:
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
