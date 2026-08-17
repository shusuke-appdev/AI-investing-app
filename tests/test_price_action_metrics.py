import numpy as np
import pandas as pd
import pytest

from src.advisor.price_action_metrics import (
    atr_series,
    normalize_price_frame,
    period_returns,
    recent_pivot,
    relative_returns,
    relative_volume,
)


def test_missing_ohlcv_is_unavailable_instead_of_zero_filled():
    frame = pd.DataFrame({"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0]})

    assert normalize_price_frame(frame).empty
    assert period_returns(pd.Series([100.0, 101.0]), periods=(20,)) == {}


def test_relative_returns_use_aligned_sessions():
    index = pd.bdate_range("2026-01-02", periods=70)
    stock = pd.Series(np.linspace(100, 140, 70), index=index)
    benchmark = pd.Series(np.linspace(100, 110, 70), index=index)

    result = relative_returns(stock, benchmark, periods=(20, 63))

    assert result["20d"] > 0
    assert result["63d"] > result["20d"]


def test_atr_warmup_is_missing_not_zero():
    close = pd.Series(np.linspace(100, 110, 20))
    high = close + 1
    low = close - 1

    result = atr_series(high, low, close)

    assert pd.isna(result.iloc[0])
    assert result.iloc[-1] == pytest.approx(2.0)


def test_recent_pivot_and_relative_volume_exclude_latest_session():
    high = pd.Series([10.0, 11.0, 12.0, 15.0])
    volume = pd.Series([100.0, 100.0, 100.0, 200.0])

    assert recent_pivot(high, lookback=3) == 12.0
    assert relative_volume(volume, lookback=3) == 2.0
