from __future__ import annotations

import numpy as np
import pandas as pd

from src.services import comprehensive_theme_ranking_service as service


def _frame(
    *,
    rows: int = 260,
    growth: float = 0.001,
    volume_growth: float = 0.0,
) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=rows)
    close = 50 * np.power(1 + growth, np.arange(rows))
    volume = 1_000_000 * np.power(1 + volume_growth, np.arange(rows))
    return pd.DataFrame(
        {
            "Open": close * 0.998,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )


def _basket(theme: str, tickers: list[str], proxy: str = "") -> dict:
    return {
        "theme": theme,
        "market_type": "US",
        "all_tickers": tickers,
        "measurement_tickers": tickers,
        "proxy_ticker": proxy,
        "method": "test",
        "reduced": False,
    }


def test_comprehensive_ranking_rewards_price_relative_volume_and_breadth():
    baskets = {
        "Strong": _basket("Strong", ["S1", "S2", "S3"], "SPROXY"),
        "Weak": _basket("Weak", ["W1", "W2", "W3"]),
    }
    frames = {
        "S1": _frame(growth=0.002, volume_growth=0.002),
        "S2": _frame(growth=0.0018, volume_growth=0.0018),
        "S3": _frame(growth=0.0016, volume_growth=0.0015),
        "SPROXY": _frame(growth=0.0015, volume_growth=0.001),
        "W1": _frame(growth=-0.0004),
        "W2": _frame(growth=-0.0005),
        "W3": _frame(growth=-0.0006),
    }

    result = service.build_comprehensive_theme_ranking(
        market_type="US",
        price_frames=frames,
        benchmark_frame=_frame(growth=0.0004),
        baskets=baskets,
        fetched_at="2026-08-17T00:00:00+00:00",
    )

    assert result["status"] == "available"
    strong, weak = result["items"]
    assert strong["theme"] == "Strong"
    assert strong["total_score"] > weak["total_score"]
    assert strong["momentum_score"] > weak["momentum_score"]
    assert strong["relative_strength_score"] > weak["relative_strength_score"]
    assert strong["attention_score"] > weak["attention_score"]
    assert strong["breadth_score"] > weak["breadth_score"]
    assert strong["proxy_confirmation"] == "確認あり"
    assert strong["rank"] == 1
    assert 0 < strong["total_score"] <= 100


def test_missing_volume_excludes_theme_instead_of_zero_scoring():
    missing = _frame().drop(columns=["Volume"])
    result = service.build_comprehensive_theme_ranking(
        market_type="US",
        price_frames={"A": missing, "B": missing, "C": missing},
        benchmark_frame=_frame(growth=0.0004),
        baskets={"Missing": _basket("Missing", ["A", "B", "C"])},
    )

    assert result["items"] == []
    assert result["excluded_reasons"]["代表銘柄の取得率不足"] == 1


def test_partial_coverage_is_preserved_when_threshold_is_met():
    result = service.build_comprehensive_theme_ranking(
        market_type="US",
        price_frames={
            "A": _frame(growth=0.001),
            "B": _frame(growth=0.0011),
            "C": _frame(growth=0.0012),
        },
        benchmark_frame=_frame(growth=0.0004),
        baskets={"Partial": _basket("Partial", ["A", "B", "C", "D"])},
    )

    assert result["status"] == "partial"
    assert result["items"][0]["data_quality"] == "partial"
    assert result["items"][0]["coverage_1m"] == 0.75


def test_theme_measurement_registry_preserves_full_membership():
    from src.theme_measurement import get_theme_measurement_baskets

    baskets = get_theme_measurement_baskets("US")
    reduced = [item for item in baskets.values() if item["reduced"]]

    assert reduced
    assert all(len(item["measurement_tickers"]) >= 4 for item in reduced)
    assert all(
        set(item["measurement_tickers"]).issubset(item["all_tickers"])
        for item in baskets.values()
    )
