import numpy as np
import pandas as pd

from src.advisor.exposure_sizing import suggest_exposure
from src.advisor.probabilistic_signal import (
    add_forward_outcomes,
    classify_signal_row,
    generate_probabilistic_stock_signal,
)
from src.advisor.stock_feature_engine import build_stock_feature_frame
from src.backtesting.walk_forward import run_walk_forward_validation


def _price_frame(rows: int = 900, start: float = 100.0) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=rows)
    trend = np.linspace(0, rows * 0.03, rows)
    cycle = np.sin(np.arange(rows) / 9) * 2.0
    close = start + trend + cycle
    high = close * 1.01
    low = close * 0.99
    open_ = close * 0.995
    volume = 1_000_000 + np.sin(np.arange(rows) / 7) * 50_000
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )


def test_feature_frame_has_stationary_features_without_infinite_values():
    prices = _price_frame()
    benchmark = _price_frame(start=90.0)

    features = build_stock_feature_frame(
        prices,
        benchmark,
        {"pe_ratio": 25.0, "forward_pe": 20.0},
        {"overall_score": 62, "rsi": 55.0, "adx": 20.0},
    )

    assert "vwap_deviation_z_120d" in features.columns
    assert "return_1d_percentile_252d" in features.columns
    assert "spy_excess_return_20d" in features.columns
    assert np.isfinite(features["vwap_deviation_z_120d"].dropna()).all()
    assert np.isfinite(features["return_1d_percentile_252d"].dropna()).all()


def test_signal_classification_uses_vwap_z_and_return_percentile():
    assert (
        classify_signal_row(
            pd.Series({"vwap_deviation_z_120d": -2.7, "return_1d_percentile_252d": 3.0})
        )
        == "Strong Oversold Rebound Candidate"
    )
    assert (
        classify_signal_row(
            pd.Series({"vwap_deviation_z_120d": 2.7, "return_1d_percentile_252d": 97.0})
        )
        == "Strong Overbought Mean-Reversion Candidate"
    )
    assert (
        classify_signal_row(
            pd.Series({"vwap_deviation_z_120d": 0.2, "return_1d_percentile_252d": 45.0})
        )
        == "Neutral"
    )


def test_forward_outcomes_do_not_use_current_day_as_future():
    prices = _price_frame(rows=80)
    features = build_stock_feature_frame(prices)

    enriched = add_forward_outcomes(features, prices)
    first_valid = enriched["forward_5d_return"].dropna().index[0]
    idx = prices.index.get_loc(first_valid)
    expected = prices["Close"].iloc[idx + 5] / prices["Close"].iloc[idx] - 1

    assert enriched.loc[first_valid, "forward_5d_return"] == expected


def test_exposure_sizing_caps_low_confidence_and_bad_regime():
    result = suggest_exposure(
        expected_return=0.04,
        risk_adjusted_signal=1.2,
        confidence="Low",
        realized_vol_20d=0.35,
        realized_vol_percentile=85.0,
        adverse_loss_p95=0.15,
        regime_fit=40.0,
    )

    assert result["suggested_action"] == "Watch"
    assert result["max_allocation_pct"] <= 1
    assert result["size_multiplier"] <= 0.25


def test_walk_forward_validation_keeps_chronological_folds():
    prices = _price_frame(rows=1300)
    features = build_stock_feature_frame(prices, prices)
    enriched = add_forward_outcomes(features, prices, prices)
    enriched["signal_label"] = "Neutral"

    result = run_walk_forward_validation(enriched, "Neutral")

    assert result["folds"]
    first = result["folds"][0]
    assert first["train_start"] < first["test_start"] < first["test_end"]


def test_generate_probabilistic_signal_with_mocked_data(monkeypatch):
    prices = _price_frame(rows=1100)
    benchmark = _price_frame(rows=1100, start=95.0)

    def fake_get_stock_data(ticker, period="5y"):
        return benchmark if ticker == "SPY" else prices

    def fake_get_stock_info(ticker, **kwargs):
        return {"ticker": ticker, "name": "Test Inc.", "pe_ratio": 22.0}

    monkeypatch.setattr("src.market_data.get_stock_data", fake_get_stock_data)
    monkeypatch.setattr("src.market_data.get_stock_info", fake_get_stock_info)

    signal = generate_probabilistic_stock_signal("TEST")

    assert signal.ticker == "TEST"
    assert signal.confidence in {"Low", "Medium", "High"}
    assert signal.suggested_action in {"Add small", "Hold", "Watch", "Avoid"}
    if signal.signal_label == "Neutral" or signal.confidence == "Low":
        assert signal.suggested_action == "Watch"
        assert signal.max_allocation_pct == 0
    assert signal.max_allocation_pct in {0, 1, 2, 3, 5}
