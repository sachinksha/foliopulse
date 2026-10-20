import copy

from foliopulse.config import DEFAULT_CONFIG
from foliopulse.storage import COLLECTION, ConfigStore


class FakeDoc:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class FakeRef:
    def __init__(self, store, email):
        self._store = store
        self._email = email

    def get(self):
        if self._store.get_error:
            raise RuntimeError("firestore unavailable")
        return FakeDoc(self._store.docs.get(self._email))

    def set(self, data, merge=False):
        if self._store.set_error:
            raise RuntimeError("write failed")
        self._store.set_calls.append((self._email, copy.deepcopy(data), merge))
        if merge:
            self._store.docs.setdefault(self._email, {}).update(copy.deepcopy(data))
        else:
            self._store.docs[self._email] = copy.deepcopy(data)


class FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, email):
        return FakeRef(self._store, email)


class FakeDB:
    def __init__(self):
        self.docs = {}
        self.set_calls = []
        self.get_error = False
        self.set_error = False

    def collection(self, name):
        assert name == COLLECTION
        return FakeCollection(self)


def test_load_creates_default_config_for_new_user():
    db = FakeDB()
    cfg = ConfigStore(db).load("new@example.com")
    assert cfg == DEFAULT_CONFIG
    assert "new@example.com" in db.docs


def test_load_returns_a_copy_not_the_shared_default():
    db = FakeDB()
    cfg = ConfigStore(db).load("new@example.com")
    cfg["watchlist"].append({"symbol": "X"})
    assert len(DEFAULT_CONFIG["watchlist"]) == 2  # module default untouched


def test_load_fills_missing_trade_type_for_old_items():
    db = FakeDB()
    db.docs["u@example.com"] = {"watchlist": [{"symbol": "LT.NS", "avg_buy_price": 1, "quantity": 1}]}
    cfg = ConfigStore(db).load("u@example.com")
    assert cfg["watchlist"][0]["trade_type"] == "DELIVERY"


def test_load_falls_back_to_defaults_when_firestore_fails():
    db = FakeDB()
    db.get_error = True
    cfg = ConfigStore(db).load("u@example.com")
    assert cfg == DEFAULT_CONFIG


def test_save_merges_into_document():
    db = FakeDB()
    store = ConfigStore(db)
    store.save("u@example.com", {"watchlist": [{"symbol": "TITAN.NS"}]})
    assert db.set_calls[-1][2] is True  # merge=True
    assert db.docs["u@example.com"]["watchlist"] == [{"symbol": "TITAN.NS"}]


def test_save_raises_so_the_caller_can_report_it():
    db = FakeDB()
    db.set_error = True
    try:
        ConfigStore(db).save("u@example.com", {})
    except RuntimeError:
        return
    raise AssertionError("save should propagate Firestore errors")
