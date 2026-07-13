import json
from datetime import datetime, timedelta, timezone

from src import persistent_cache as cache_module
from src.persistent_cache import PersistentJsonCache, safe_cache_key

_FIXED_NOW = datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return _FIXED_NOW if tz else _FIXED_NOW.replace(tzinfo=None)


def _iso_age(seconds: int) -> str:
    return (_FIXED_NOW - timedelta(seconds=seconds)).isoformat()


def test_persistent_cache_classifies_fresh_stale_and_expired(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_module, "datetime", _FrozenDateTime)
    store = PersistentJsonCache(tmp_path, "market_context_cache")

    store.write("US/summary", {"value": "fresh"}, fetched_at=_iso_age(60))
    fresh = store.read("US/summary", fresh_seconds=300, stale_seconds=900)

    assert fresh.status == "fresh"
    assert fresh.payload == {"value": "fresh"}
    assert fresh.is_available is True

    store.write("US/summary", {"value": "stale"}, fetched_at=_iso_age(600))
    stale = store.read("US/summary", fresh_seconds=300, stale_seconds=900)

    assert stale.status == "stale"
    assert stale.is_stale is True
    assert stale.payload == {"value": "stale"}

    store.write("US/summary", {"value": "old"}, fetched_at=_iso_age(1_000))
    expired = store.read("US/summary", fresh_seconds=300, stale_seconds=900)

    assert expired.status == "expired"
    assert expired.is_available is False
    assert expired.payload == {}


def test_persistent_cache_ignores_corrupt_json(tmp_path):
    store = PersistentJsonCache(tmp_path, "option_chain_cache")
    path = store.path_for_key("SPY")
    path.write_text("{not-json", encoding="utf-8")

    result = store.read("SPY", fresh_seconds=60, stale_seconds=120)

    assert result.status == "invalid"
    assert result.is_available is False


def test_persistent_cache_reads_legacy_unwrapped_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_module, "datetime", _FrozenDateTime)
    store = PersistentJsonCache(tmp_path, "option_chain_cache")
    path = store.path_for_key("SPY")
    fetched_at = _iso_age(10)
    path.write_text(
        json.dumps({"fetched_at": fetched_at, "value": "legacy"}),
        encoding="utf-8",
    )

    result = store.read("SPY", fresh_seconds=60, stale_seconds=120)

    assert result.status == "fresh"
    assert result.payload["value"] == "legacy"
    assert result.fetched_at == fetched_at


def test_safe_cache_key_replaces_path_separators():
    assert safe_cache_key("../SPY/USD") == "SPY_USD"
