from datetime import datetime, timedelta, timezone

import pytest

from src.marketdata_client import MarketDataResponse
from src.marketdata_option_provider import normalize_option_chain_response


def _payload(expiration_date: str = "2026-06-29"):
    expiration = int(
        datetime.fromisoformat(expiration_date).replace(tzinfo=timezone.utc).timestamp()
    )
    updated = int(datetime(2026, 6, 13, tzinfo=timezone.utc).timestamp())
    return {
        "s": "ok",
        "optionSymbol": ["SPY_CALL", "SPY_PUT"],
        "underlying": ["SPY", "SPY"],
        "expiration": [expiration, expiration],
        "side": ["call", "put"],
        "strike": [600, 600],
        "dte": [1, 1],
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
    assert list(frame["expiration"]) == ["2026-06-29", "2026-06-29"]
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
    expiration_date = (
        datetime.now(timezone.utc).date() + timedelta(days=7)
    ).isoformat()

    class FakeClient:
        def get(self, path, params=None):
            calls.append((path, params))
            if path == "/options/expirations/SPY/":
                return MarketDataResponse(
                    data={"s": "ok", "expirations": [expiration_date]},
                    status_code=200,
                )
            return MarketDataResponse(data=_payload(expiration_date), status_code=200)

    monkeypatch.setattr(
        provider,
        "_cache",
        lambda: PersistentJsonCache(tmp_path, "marketdata_option_chain_cache"),
    )

    result = provider.fetch_marketdata_option_chain("SPY", client=FakeClient())

    assert result is not None
    assert len(result.calls) == 1
    assert len(result.puts) == 1
    assert calls[0][0] == "/options/expirations/SPY/"
    assert calls[1][1]["expiration"] == expiration_date
    assert "dte" not in calls[1][1]
    assert calls[1][1]["strikeLimit"] == 100
    assert calls[1][1]["nonstandard"] == "false"
    assert "mode" not in calls[1][1]
    assert result.resolved_expiration == expiration_date
    assert result.resolved_dte >= 1


def test_resolve_marketdata_expiration_skips_0dte_after_cutoff():
    from src import marketdata_option_provider as provider

    class FakeClient:
        def get(self, path, params=None):
            return MarketDataResponse(
                data={"s": "ok", "expirations": ["2026-06-26", "2026-06-27"]},
                status_code=200,
            )

    expiration, dte, reason = provider.resolve_option_expiration(
        "SPY",
        client=FakeClient(),
        now=datetime(2026, 6, 26, 20, 5, tzinfo=timezone.utc),
    )

    assert expiration == "2026-06-27"
    assert dte == 1
    assert "skipped" in reason


def test_resolve_marketdata_expiration_allows_0dte_before_cutoff():
    from src import marketdata_option_provider as provider

    class FakeClient:
        def get(self, path, params=None):
            return MarketDataResponse(
                data={"s": "ok", "expirations": ["2026-06-26", "2026-06-27"]},
                status_code=200,
            )

    expiration, dte, reason = provider.resolve_option_expiration(
        "SPY",
        client=FakeClient(),
        now=datetime(2026, 6, 26, 17, 0, tzinfo=timezone.utc),
    )

    assert expiration == "2026-06-26"
    assert dte == 0
    assert "same-day" in reason


def test_resolve_marketdata_expiration_selects_target_dte():
    from src import marketdata_option_provider as provider

    class FakeClient:
        def get(self, path, params=None):
            return MarketDataResponse(
                data={
                    "s": "ok",
                    "expirations": ["2026-06-27", "2026-07-03", "2026-07-31"],
                },
                status_code=200,
            )

    expiration, dte, reason = provider.resolve_option_expiration(
        "SPY",
        target_dte=7,
        min_dte=1,
        client=FakeClient(),
        now=datetime(2026, 6, 26, 17, 0, tzinfo=timezone.utc),
    )

    assert expiration == "2026-07-03"
    assert dte == 7
    assert "target_dte=7" in reason


def test_resolve_marketdata_expiration_can_cache_expiration_list():
    from src import marketdata_option_provider as provider

    provider._expiration_cache.clear()
    calls = []

    class FakeClient:
        def get(self, path, params=None):
            calls.append(path)
            return MarketDataResponse(
                data={"s": "ok", "expirations": ["2026-07-03", "2026-07-24"]},
                status_code=200,
            )

    client = FakeClient()
    provider.resolve_option_expiration(
        "SPY",
        target_dte=7,
        client=client,
        use_cache=True,
        now=datetime(2026, 6, 26, 17, 0, tzinfo=timezone.utc),
    )
    provider.resolve_option_expiration(
        "SPY",
        target_dte=30,
        client=client,
        use_cache=True,
        now=datetime(2026, 6, 26, 17, 0, tzinfo=timezone.utc),
    )

    assert calls == ["/options/expirations/SPY/"]
    provider._expiration_cache.clear()
