import pandas as pd

from src import credit_stress_monitor as monitor
from src.economic_data_provider import EconomicDataResult


def test_credit_stress_detects_rapid_stress(monkeypatch):
    dates = pd.date_range("2018-01-01", periods=90, freq="MS")
    data = pd.DataFrame(
        {
            "BAA10Y": [1.0] * 89 + [2.0],
            "KCFSI": [0.0] * 89 + [1.0],
            "BAMLH0A0HYM2": [3.0] * 90,
        },
        index=dates,
    )
    monkeypatch.setattr(
        monitor,
        "fetch_fred_series",
        lambda *args, **kwargs: EconomicDataResult(
            data=data,
            source="test",
            fetched_at="2026-01-01T00:00:00+00:00",
        ),
    )
    monkeypatch.setattr(monitor, "_market_confirmation_payloads", lambda: [])

    result = monitor.build_credit_stress_monitor("US")

    assert result["status"] == "rapid_stress"
    assert result["rapid_stress"] is True
    assert result["indicators"][0]["is_hot"] is True
    assert result["indicators"][1]["is_hot"] is True


def test_credit_stress_us_only():
    result = monitor.build_credit_stress_monitor("JP")

    assert result["status"] == "unavailable"
    assert result["is_partial"] is True
