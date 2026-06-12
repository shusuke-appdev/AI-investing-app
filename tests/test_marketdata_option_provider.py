from datetime import datetime, timezone

import pytest

from src.marketdata_client import MarketDataResponse
from src.marketdata_option_provider import normalize_option_chain_response


def _payload():
    expiration = int(datetime(2026, 6, 19, tzinfo=timezone.utc).timestamp())
    updated = int(datetime(2026, 6, 13, tzinfo=timezone.utc).timestamp())
    return {
        "s": "ok",
        "optionSymbol": ["SPY_CALL", "SPY_PUT"],
        "underlying": ["SPY", "SPY"],
        "expiration": [expiration, expiration],
        "side": ["call", "put"],
        "strike": [600, 600],
        "dte": [0, 0],
        "volume": [10, 20],
        "openInterest": [100, 200],
        "underlyingPrice": [601.5, 601.5],
        "iv": [0.2, 0.22],
        "delta": [0.5, -0.5],
        "gamma": [0.03, 0.03],
        "theta": [-0.1, -0.1],
        "vega": [0.2, 0.2],
        "updated": [updated, updated],
    }


def test_normalize_marketdata_option_chain():
    frame = normalize_option_chain_response(_payload())

    assert list(frame["side"]) == ["call", "put"]
    assert list(frame["impliedVolatility"]) == [0.2, 0.22]
    assert list(frame["expiration"]) == ["2026-06-19", "2026-06-19"]
    assert list(frame["gamma"]) == [0.03, 0.03]


def test_normalize_marketdata_option_chain_rejects_mismatched_columns():
    payload = _payload()
    payload["gamma"] = [0.03]

    with pytest.raises(Exception, match="mismatched"):
        normalize_option_chain_response(payload)


def test_fetch_marketdata_option_chain_uses_bounded_request(monkeypatch, tmp_path):
    from src import marketdata_option_provider as provider
    from src.persistent_cache import PersistentJsonCache

    calls = []

    class FakeClient:
        def get(self, path, params=None):
            calls.append((path, params))
            return MarketDataResponse(data=_payload(), status_code=200)

    monkeypatch.setattr(
        provider,
        "_cache",
        lambda: PersistentJsonCache(tmp_path, "marketdata_option_chain_cache"),
    )

    result = provider.fetch_marketdata_option_chain("SPY", client=FakeClient())

    assert result is not None
    assert len(result.calls) == 1
    assert len(result.puts) == 1
    assert calls[0][1]["dte"] == 0
    assert calls[0][1]["strikeLimit"] == 100
    assert calls[0][1]["nonstandard"] == "false"
    assert "mode" not in calls[0][1]
