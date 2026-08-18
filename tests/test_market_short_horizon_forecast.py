import numpy as np
import pandas as pd

from src.market_volatility_intelligence import CboeIndexResult
from src.services import market_short_horizon_forecast as module


def _price_frame(index: pd.DatetimeIndex, start: float, slope: float) -> pd.DataFrame:
    wave = np.sin(np.arange(len(index)) / 9) * 1.5
    close = start + np.arange(len(index)) * slope + wave
    volume = 1_000_000 + np.cos(np.arange(len(index)) / 7) * 50_000
    return pd.DataFrame({"Close": close, "Volume": volume}, index=index)


def _inputs(rows: int = 360):
    index = pd.date_range("2024-01-02", periods=rows, freq="B")
    frames = {
        ticker: _price_frame(index, 80 + position * 5, 0.04 + position * 0.002)
        for position, ticker in enumerate(module.INPUT_TICKERS)
    }
    cboe = pd.DataFrame(
        {
            "VIX": 18 + np.sin(np.arange(rows) / 13) * 3,
            "VIX1D": 17 + np.sin(np.arange(rows) / 11) * 4,
            "VIX9D": 18 + np.sin(np.arange(rows) / 12) * 3,
            "VIX3M": 20 + np.sin(np.arange(rows) / 15) * 2,
            "VVIX": 95 + np.sin(np.arange(rows) / 10) * 8,
            "SKEW": 135 + np.cos(np.arange(rows) / 17) * 6,
            "VXN": 21 + np.sin(np.arange(rows) / 14) * 3,
        },
        index=index,
    )
    return frames, CboeIndexResult(data=cboe, source="test")


def test_feature_frame_contains_predeclared_joint_indicators():
    frames, cboe = _inputs()

    result = module.build_market_feature_frame("SPY", frames, cboe.data)

    assert "interaction_vix_skew" in result
    assert "interaction_vix_vvix" in result
    assert "interaction_term_breadth" in result
    assert result["interaction_vix_skew"].dropna().size > 0


def test_feature_frame_joins_daily_sources_with_different_clock_times():
    frames, cboe = _inputs()
    for frame in frames.values():
        frame.index = frame.index + pd.Timedelta(hours=4)
    cftc = pd.DataFrame(
        {
            "cftc_asset_manager_net_oi": np.linspace(0.1, 0.3, len(cboe.data)),
            "cftc_leveraged_money_net_oi": np.linspace(-0.3, -0.1, len(cboe.data)),
        },
        index=cboe.data.index,
    )

    result = module.build_market_feature_frame("SPY", frames, cboe.data, cftc)

    assert result["vix_level"].notna().sum() == len(result)
    assert result["cftc_asset_manager_net_oi"].notna().sum() == len(result)
    assert "cftc_asset_manager_net_oi" in module._select_features(result, 20)


def test_compute_forecast_keeps_failed_validation_research_only(monkeypatch):
    frames, cboe = _inputs()
    monkeypatch.setattr(module, "FORECAST_TICKERS", ("SPY",))
    monkeypatch.setattr(module, "HORIZONS", (1,))
    monkeypatch.setattr(module, "MIN_TRAIN_ROWS", 120)
    monkeypatch.setattr(module, "OOS_TARGET_ROWS", 80)
    monkeypatch.setattr(module, "MIN_OOS_ROWS", 60)
    monkeypatch.setattr(module, "REFIT_STEP", 20)
    monkeypatch.setattr(module, "_passes_validation", lambda validation, analog: False)

    result = module.compute_market_short_horizon_forecast(frames, cboe)

    one_day = result["targets"]["SPY"]["horizons"]["1d"]
    assert one_day["status"] == "research_only"
    assert 0 <= one_day["probability_up"] <= 1
    assert one_day["p10"] <= one_day["p50"] <= one_day["p90"]
    assert result["integration_enabled"] is False


def test_compute_forecast_dispatches_every_ticker_and_horizon(monkeypatch):
    frames, cboe = _inputs()
    calls = []

    def fake_horizon(ticker, horizon, close, features, cboe_frame):
        calls.append((ticker, horizon, len(close), len(features), len(cboe_frame)))
        return {
            "status": "research_only",
            "ticker": ticker,
            "horizon_days": horizon,
            "as_of": "2025-05-19",
            "probability_up": 0.5,
        }

    monkeypatch.setattr(module, "MIN_TRAIN_ROWS", 120)
    monkeypatch.setattr(module, "_forecast_horizon", fake_horizon)

    result = module.compute_market_short_horizon_forecast(frames, cboe)

    assert {(ticker, horizon) for ticker, horizon, *_ in calls} == {
        (ticker, horizon)
        for ticker in module.FORECAST_TICKERS
        for horizon in module.HORIZONS
    }
    assert set(result["targets"]) == set(module.FORECAST_TICKERS)
    assert result["status"] == "research_only"


def test_implied_move_prefers_matching_vix_horizon():
    cboe = pd.DataFrame({"VIX": [20.0], "VIX1D": [30.0], "VIX9D": [25.0]})

    one_day = module._implied_expected_move(cboe, 1)
    five_day = module._implied_expected_move(cboe, 5)

    assert one_day == 0.30 * np.sqrt(1 / 252)
    assert five_day == 0.25 * np.sqrt(5 / 252)


def test_validation_uses_predeclared_ensemble_without_oos_model_selection():
    oos = {
        "actual": [1.0, 0.0, 1.0, 0.0],
        "actual_return": [0.02, -0.01, 0.03, -0.02],
        "baseline": [0.5, 0.5, 0.5, 0.5],
        "full": [0.9, 0.1, 0.8, 0.2],
        "trend": [0.8, 0.2, 0.7, 0.3],
        # Deliberately poor; it must remain in the predeclared evaluation ensemble.
        "analog": [0.1, 0.9, 0.2, 0.8],
        "analog_p10": [-0.03, -0.03, -0.03, -0.03],
        "analog_p90": [0.03, 0.03, 0.03, 0.03],
    }

    metrics = module._validation_metrics(oos)
    fixed = np.mean([oos[name] for name in module.PREDECLARED_MODELS], axis=0)
    expected_brier = np.mean((np.asarray(oos["actual"]) - fixed) ** 2)

    assert metrics["ensemble_models"] == list(module.PREDECLARED_MODELS)
    assert metrics["brier"] == round(float(expected_brier), 6)
    assert "eligible_models" not in metrics


def test_horizon_stops_when_required_current_sentiment_is_missing(monkeypatch):
    frames, cboe = _inputs()
    monkeypatch.setattr(module, "MIN_TRAIN_ROWS", 120)
    features = module.build_market_feature_frame(
        "SPY", frames, cboe.data.drop(columns="SKEW")
    )

    result = module._forecast_horizon(
        "SPY", 5, frames["SPY"]["Close"], features, cboe.data
    )

    assert result["status"] == "insufficient_data"
    assert "skew_level" in result["quality_warnings"][0]
