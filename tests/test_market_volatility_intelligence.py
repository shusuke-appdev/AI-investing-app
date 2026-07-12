from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.market_volatility_intelligence import (
    CboeIndexResult,
    _historical_outcomes,
    build_local_sentiment_composite,
    build_market_volatility_regime,
    fetch_cboe_indices,
    fetch_cnn_fear_greed,
)


def _history(rows: int = 500, start: float = 100.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = np.linspace(start, start * 1.25, rows)
    return pd.DataFrame({"Close": close}, index=index)


def test_market_volatility_regime_returns_staged_posture_for_stable_history():
    spy = _history()
    cboe = pd.DataFrame(
        {
            "VIX": np.linspace(25, 15, 500),
            "VIX9D": np.linspace(24, 14, 500),
            "VIX3M": np.linspace(26, 17, 500),
            "VVIX": np.linspace(105, 85, 500),
            "SKEW": np.linspace(125, 135, 500),
        },
        index=spy.index,
    )

    result = build_market_volatility_regime(
        spy,
        cboe_result=CboeIndexResult(data=cboe, source="test"),
        credit_stress={"rapid_stress": False},
        ibd_regime={"status_key": "confirmed_uptrend"},
    )

    assert result["regime"] in {"healthy_risk_on", "complacent", "normalization"}
    assert result["forward_outcomes"]["sample_size"] > 0
    assert result["posture"] in {"Watch", "Pilot", "Staged"}


def test_historical_outcomes_sorts_misaligned_datetime_indexes():
    spy = _history().sort_index(ascending=False)
    cboe = pd.DataFrame(
        {
            "VIX": np.linspace(15, 25, 500),
            "VVIX": np.linspace(85, 105, 500),
            "SKEW": np.linspace(135, 125, 500),
        },
        index=spy.index + pd.Timedelta(days=1),
    )

    result = _historical_outcomes(cboe, spy)

    assert result["sample_size"] > 0
    assert result["20d"]["mean_return"] > 0


def test_fetch_cboe_indices_sorts_misaligned_datetime_indexes(monkeypatch):
    from src import market_volatility_intelligence as module

    cache = SimpleNamespace(
        read=lambda *args, **kwargs: SimpleNamespace(
            status="expired", is_available=False
        ),
        write=lambda *args, **kwargs: None,
    )
    frames = {
        "VIX": pd.DataFrame(
            {"VIX": [20.0, 19.0]},
            index=pd.to_datetime(["2026-01-03", "2026-01-01"]),
        ),
        "VVIX": pd.DataFrame(
            {"VVIX": [90.0, 91.0]},
            index=pd.to_datetime(["2026-01-04", "2026-01-02"]),
        ),
    }
    response = SimpleNamespace(text="unused", raise_for_status=lambda: None)
    monkeypatch.setattr(module, "repo_state_cache", lambda namespace: cache)
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(module, "_parse_cboe_csv", lambda text, symbol: frames[symbol])

    result = fetch_cboe_indices(("VIX", "VVIX"))

    assert result.data.index.is_monotonic_increasing
    assert list(result.data.index) == list(pd.date_range("2026-01-01", periods=4))


def test_local_sentiment_reweights_available_components():
    spy = _history(200)
    tlt = _history(200, 100.0)
    cboe = pd.DataFrame({"VIX": np.linspace(30, 16, 200)}, index=spy.index)

    result = build_local_sentiment_composite(
        spy,
        tlt,
        cboe_result=CboeIndexResult(data=cboe, source="test"),
        credit_stress={"score": 0.2},
    )

    assert 0 <= result["score"] <= 100
    assert result["coverage"].endswith("/7")
    assert len(result["components"]) == 4
    assert result["source"] == "local_equal_weight_composite"


def test_cnn_failure_is_non_blocking(monkeypatch, tmp_path):
    from src import market_volatility_intelligence as module
    from src.persistent_cache import PersistentJsonCache

    monkeypatch.setattr(
        module,
        "repo_state_cache",
        lambda namespace: PersistentJsonCache(tmp_path, namespace),
    )
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bot blocked")),
    )

    result = fetch_cnn_fear_greed()

    assert result["status"] == "unavailable"
    assert result["score"] is None
