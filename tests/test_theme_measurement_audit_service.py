import numpy as np
import pandas as pd

from src.services.theme_measurement_audit_service import (
    build_audited_measurement_baskets,
)


def _frame(growth: float, wobble: float) -> pd.DataFrame:
    rows = 260
    index = pd.bdate_range("2025-01-02", periods=rows)
    trend = 50 * np.power(1 + growth, np.arange(rows))
    close = trend * (1 + wobble * np.sin(np.arange(rows) / 15))
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(rows, 1_000_000.0),
        },
        index=index,
    )


def test_audit_reduces_only_when_theme_and_market_rank_metrics_pass():
    themes = {
        f"T{theme_index}": [
            f"T{theme_index}_{ticker_index}" for ticker_index in range(6)
        ]
        for theme_index in range(4)
    }
    frames = {
        ticker: _frame(0.0005 + theme_index * 0.0004, ticker_index * 0.00002)
        for theme_index, tickers in enumerate(themes.values())
        for ticker_index, ticker in enumerate(tickers)
    }

    result = build_audited_measurement_baskets(themes=themes, price_frames=frames)

    assert result["passed"] is True
    assert all(len(tickers) >= 4 for tickers in result["baskets"].values())
    assert all(
        audit["correlation_20d"] >= 0.90
        and audit["correlation_63d"] >= 0.90
        and audit["direction_agreement"] >= 0.85
        for audit in result["theme_audits"].values()
    )
    assert result["rank_correlation_1w"] >= 0.92
    assert result["top10_overlap_6m"] >= 0.80


def test_audit_keeps_full_membership_when_price_evidence_is_missing():
    themes = {"T1": ["A", "B", "C", "D", "E"]}

    result = build_audited_measurement_baskets(themes=themes, price_frames={})

    assert result["passed"] is False
    assert result["baskets"]["T1"] == themes["T1"]
    assert result["warnings"]
