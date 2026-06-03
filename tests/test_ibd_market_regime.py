import pandas as pd

from src.advisor.ibd_market_regime import (
    REGIME_CONFIRMED_UPTREND,
    REGIME_MARKET_IN_CORRECTION,
    classify_ibd_market_regime,
)


def _frame(close_values: list[float], volume_values: list[int] | None = None):
    volume_values = volume_values or [1_000_000] * len(close_values)
    return pd.DataFrame(
        {
            "Open": close_values,
            "High": [value * 1.01 for value in close_values],
            "Low": [value * 0.99 for value in close_values],
            "Close": close_values,
            "Volume": volume_values,
        },
        index=pd.date_range("2025-01-01", periods=len(close_values)),
    )


def test_ibd_regime_marks_clean_uptrend_as_confirmed():
    prices = [100 + idx * 0.5 for idx in range(230)]

    result = classify_ibd_market_regime(_frame(prices), _frame(prices))

    assert result.status_key == REGIME_CONFIRMED_UPTREND
    assert result.score > 0
    assert result.weight == 2.0


def test_ibd_regime_marks_ma_break_as_correction():
    prices = [140 + idx * 0.1 for idx in range(210)] + [90, 88, 86, 84, 82]
    volumes = [1_000_000] * 210 + [
        1_500_000,
        1_600_000,
        1_700_000,
        1_800_000,
        1_900_000,
    ]

    result = classify_ibd_market_regime(
        _frame(prices, volumes), _frame(prices, volumes)
    )

    assert result.status_key == REGIME_MARKET_IN_CORRECTION
    assert result.score < 0
    assert "200日線割れ" in result.rationale
