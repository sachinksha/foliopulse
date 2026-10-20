"""Firestore persistence for per-user watchlist configs.

The Firestore client is injected so this module can be tested with a fake.
"""

from __future__ import annotations

import copy
import logging

from foliopulse.config import DEFAULT_CONFIG

COLLECTION = "user_configs"
DEFAULT_TRADE_TYPE = "DELIVERY"


class ConfigStore:
    def __init__(self, db):
        self._db = db

    def _doc(self, email: str):
        return self._db.collection(COLLECTION).document(email)

    def load(self, email: str) -> dict:
        """Load a user's config. Creates the default config on first use.

        Falls back to defaults on any error, so the app stays usable when Firestore is down.
        """
        try:
            ref = self._doc(email)
            doc = ref.get()
            if doc.exists:
                cfg = doc.to_dict()
                for item in cfg.get("watchlist", []):
                    item.setdefault("trade_type", DEFAULT_TRADE_TYPE)
                return cfg
            ref.set(copy.deepcopy(DEFAULT_CONFIG))
            return copy.deepcopy(DEFAULT_CONFIG)
        except Exception as err:  # noqa: BLE001 - any Firestore failure falls back to defaults
            logging.error(f"Firestore load failed: {err}")
            return copy.deepcopy(DEFAULT_CONFIG)

    def save(self, email: str, config: dict) -> None:
        """Merge-save a user's config. Raises on failure so the caller can report it."""
        self._doc(email).set(config, merge=True)
