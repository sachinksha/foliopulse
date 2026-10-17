"""Market data access via yfinance. No Streamlit imports: caching lives in the app."""

from datetime import datetime
import logging

import pandas as pd
import pytz
import yfinance as yf


MARKET_INDICES = {
    "Sensex": "^BSESN",
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
}


def fetch_index_quotes(indices=MARKET_INDICES, ticker_factory=yf.Ticker) -> dict:
    """Last price and day change for each index. Failures return zeros."""
    results = {}
    for name, ticker in indices.items():
        try:
            fast_info = ticker_factory(ticker).fast_info
            curr_price = float(fast_info.last_price)
            prev_close = float(fast_info.previous_close)
            chg = curr_price - prev_close
            chg_pct = (chg / prev_close) * 100
            results[name] = {"val": curr_price, "chg": chg, "pct": chg_pct}
        except Exception:  # noqa: BLE001
            results[name] = {"val": 0.0, "chg": 0.0, "pct": 0.0}
    return results


def get_history(sym, ticker_factory=yf.Ticker, now=None):
    ticker_obj = ticker_factory(sym)
    df_daily = ticker_obj.history(period="20d", interval="1d")

    if df_daily.empty:
        raise ValueError(f"Yahoo Finance returned empty history for {sym}. (Possible rate-limit/block)")

    df_daily.index = df_daily.index.strftime("%Y-%m-%d")

    ltp = None
    prev_close = None

    try:
        fast_info = ticker_obj.fast_info
        ltp = round(float(fast_info.last_price), 2)
        prev_close = float(fast_info.previous_close)
    except Exception:
        pass

    if ltp is None or ltp <= 0:
        if len(df_daily) > 0:
            ltp = round(float(df_daily["Close"].iloc[-1]), 2)
            prev_close = float(df_daily["Close"].iloc[-2]) if len(df_daily) > 1 else ltp

    if ltp is None or ltp <= 0:
        raise ValueError(f"Could not extract valid LTP for {sym}")

    india_tz = pytz.timezone("Asia/Kolkata")
    now = now if now is not None else datetime.now(india_tz)
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


def search_symbols(query, search=yf.Search):
    if not query or len(query.strip()) < 2:
        return []
    try:
        search_res = search(query, max_results=8)
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
                        "quote_type": q.get("quoteType") or "",
                    }
                )
        return results
    except Exception as e:
        logging.error(f"yfinance search failed: {e}")
        return []
