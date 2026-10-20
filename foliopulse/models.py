"""Watchlist domain model and instrument helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from foliopulse.expenses import INSTRUMENT_EQUITY, INSTRUMENT_MUTUAL_FUND, INSTRUMENT_TYPES

# Yahoo quoteType values that map onto our instrument flag. Yahoo does not label
# SIFs, so they can only be chosen manually.
YAHOO_QUOTE_TYPE_TO_INSTRUMENT = {"MUTUALFUND": INSTRUMENT_MUTUAL_FUND}

DEFAULT_TRADE_TYPE = "DELIVERY"


@dataclass(frozen=True)
class Holding:
    """One watchlist entry. Mirrors the dict shape stored in Firestore."""

    symbol: str
    avg_buy_price: float
    quantity: int
    trade_type: str = DEFAULT_TRADE_TYPE
    instrument_type: str = INSTRUMENT_EQUITY
    stop_loss: float = 0.0
    trailing_sl: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    manual_ltp: float = 0.0
    # None means the user has not chosen; the default depends on the instrument.
    show_chart: Optional[bool] = None

    @property
    def chart_visible(self) -> bool:
        return resolve_show_chart(self.show_chart, self.instrument_type)

    @classmethod
    def from_dict(cls, data: dict) -> "Holding":
        """Build a Holding from a stored watchlist dict, applying defaults for older entries."""
        return cls(
            symbol=str(data["symbol"]),
            avg_buy_price=float(data["avg_buy_price"]),
            quantity=int(data["quantity"]),
            trade_type=str(data.get("trade_type") or DEFAULT_TRADE_TYPE).upper().strip(),
            instrument_type=str(data.get("instrument_type") or INSTRUMENT_EQUITY).upper().strip(),
            stop_loss=float(data.get("stop_loss", 0.0)),
            trailing_sl=float(data.get("trailing_sl", 0.0)),
            target_1=float(data.get("target_1", 0.0)),
            target_2=float(data.get("target_2", 0.0)),
            manual_ltp=float(data.get("manual_ltp", 0.0)),
            show_chart=_optional_bool(data.get("show_chart")),
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        # Only persist the chart flag once the user has chosen one, so untouched items stay as they were.
        if data["show_chart"] is None:
            del data["show_chart"]
        return data


def default_show_chart(instrument_type: str) -> bool:
    """Charts are shown by default for equities only; funds and SIFs start hidden."""
    return str(instrument_type or INSTRUMENT_EQUITY).upper().strip() == INSTRUMENT_EQUITY


def resolve_show_chart(explicit: Optional[bool], instrument_type: str) -> bool:
    """The user's explicit choice if there is one, otherwise the instrument default."""
    if explicit is None:
        return default_show_chart(instrument_type)
    return bool(explicit)


def _optional_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def set_chart_visibility(watchlist: list, symbol: str, visible: bool) -> bool:
    """Record a user's chart choice on the matching watchlist dict(s).

    Mutates the list in place. Returns True if anything changed.
    """
    changed = False
    for item in watchlist:
        if item.get("symbol") == symbol and item.get("show_chart") != bool(visible):
            item["show_chart"] = bool(visible)
            changed = True
    return changed


def preserved_chart_flag(old_item: dict) -> dict:
    """Chart choice to carry over when a watchlist row is rewritten (e.g. by the edit form)."""
    if old_item.get("show_chart") is None:
        return {}
    return {"show_chart": bool(old_item["show_chart"])}


def instrument_from_quote_type(quote_type) -> str:
    """Map a Yahoo quoteType to our instrument flag, defaulting to EQUITY."""
    return YAHOO_QUOTE_TYPE_TO_INSTRUMENT.get(str(quote_type or "").upper(), INSTRUMENT_EQUITY)


def instrument_index(value) -> int:
    """Index of an instrument in the selectbox options; 0 (EQUITY) if unknown."""
    return INSTRUMENT_TYPES.index(value) if value in INSTRUMENT_TYPES else 0
