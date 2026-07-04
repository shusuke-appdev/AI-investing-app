import pandas as pd

from src.services.technical_strategy_service import (
    build_technical_strategy_context,
    calculate_parabolic_sar,
)


def _ohlcv(rows: int = 120) -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=rows)
    close = pd.Series([100 + i * 0.2 for i in range(rows)], index=dates)
    return pd.DataFrame(
        {
            "Close": close,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Volume": 1000,
        },
        index=dates,
    )


def test_parabolic_sar_returns_aligned_series():
    frame = _ohlcv()
    psar = calculate_parabolic_sar(frame["High"], frame["Low"])

    assert list(psar.index) == list(frame.index)
    assert psar.notna().all()


def test_technical_strategy_context_returns_strategy_items():
    context = build_technical_strategy_context("AAPL", _ohlcv())

    assert context["status"] == "available"
    assert {item["key"] for item in context["items"]} >= {
        "bandwalk_reversal",
        "bearish_divergence",
        "dow_theory",
        "fibonacci_red_zone",
        "top_crash_pattern",
    }
    assert context["parabolic_sar"]["trend"] in {"bullish", "bearish"}


def test_technical_strategy_context_requires_enough_rows():
    context = build_technical_strategy_context("AAPL", _ohlcv(rows=40))

    assert context["status"] == "insufficient_data"
    assert context["items"] == []
