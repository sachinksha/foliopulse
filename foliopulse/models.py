"""Watchlist domain model and instrument helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

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
        )

    def to_dict(self) -> dict:
        return asdict(self)


def instrument_from_quote_type(quote_type) -> str:
    """Map a Yahoo quoteType to our instrument flag, defaulting to EQUITY."""
    return YAHOO_QUOTE_TYPE_TO_INSTRUMENT.get(str(quote_type or "").upper(), INSTRUMENT_EQUITY)


def instrument_index(value) -> int:
    """Index of an instrument in the selectbox options; 0 (EQUITY) if unknown."""
    return INSTRUMENT_TYPES.index(value) if value in INSTRUMENT_TYPES else 0
