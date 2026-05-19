"""Feature engineering for probabilistic single-stock signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    "realized_vol_20d",
    "realized_vol_60d",
    "vol_ratio_20_60",
    "atr_percent",
    "volume_zscore_20d",
    "volume_ratio_20d",
    "rolling_vwap_20d",
    "vwap_deviation_pct",
    "vwap_deviation_z_120d",
    "range_position_20d",
    "return_1d_percentile_252d",
    "return_5d_percentile_252d",
    "spy_excess_return_5d",
    "spy_excess_return_20d",
    "pe_ratio",
    "forward_pe",
    "price_to_book",
    "peg_ratio",
    "overall_score",
    "rsi",
    "adx",
    "bb_width",
    "pcr_ratio",
    "atm_iv",
]


@dataclass
class StockFeatureSnapshot:
    """Latest feature snapshot used by the probabilistic signal engine."""

    ticker: str
    as_of: str
    features: dict[str, float | str | None]
    data_quality: dict[str, Any] = field(default_factory=dict)
    lookback_days: int = 0


def _clean_ohlcv(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out = out.sort_index()
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in out.columns:
            if column == "Volume":
                out[column] = 0.0
            elif column == "Open":
                out[column] = out.get("Close", pd.Series(index=out.index, dtype=float))
            else:
                out[column] = out.get("Close", pd.Series(index=out.index, dtype=float))
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.dropna(subset=["Close"])


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _rolling_last_percentile(values: pd.Series, window: int) -> pd.Series:
    def percentile(sample: np.ndarray) -> float:
        sample = sample[~np.isnan(sample)]
        if len(sample) == 0:
            return np.nan
        latest = sample[-1]
        return float((sample <= latest).sum() / len(sample) * 100.0)

    min_periods = min(60, window)
    return values.rolling(window, min_periods=min_periods).apply(percentile, raw=True)


def _latest_scalar(source: dict[str, Any] | None, *keys: str) -> float | None:
    if not source:
        return None
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _technical_scalar(source: dict[str, Any] | None, key: str) -> float | None:
    return _latest_scalar(source, key)


def _add_constant_feature(frame: pd.DataFrame, name: str, value: float | None) -> None:
    frame[name] = float(value) if value is not None else np.nan


def build_stock_feature_frame(
    price_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    stock_info: dict[str, Any] | None = None,
    technical_data: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build stationary daily features from OHLCV and optional context."""

    prices = _clean_ohlcv(price_df)
    if prices.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    frame = pd.DataFrame(index=prices.index)
    close = prices["Close"]
    high = prices["High"]
    low = prices["Low"]
    volume = prices["Volume"].fillna(0.0)

    frame["close"] = close
    frame["return_1d"] = close.pct_change(1)
    frame["return_5d"] = close.pct_change(5)
    frame["return_20d"] = close.pct_change(20)
    frame["return_60d"] = close.pct_change(60)

    daily_return = close.pct_change()
    frame["realized_vol_20d"] = daily_return.rolling(20).std() * np.sqrt(252)
    frame["realized_vol_60d"] = daily_return.rolling(60).std() * np.sqrt(252)
    frame["vol_ratio_20_60"] = _safe_div(
        frame["realized_vol_20d"], frame["realized_vol_60d"]
    )

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(14).mean()
    frame["atr_percent"] = _safe_div(atr, close) * 100

    volume_mean = volume.rolling(20).mean()
    volume_std = volume.rolling(20).std()
    frame["volume_zscore_20d"] = _safe_div(volume - volume_mean, volume_std)
    frame["volume_ratio_20d"] = _safe_div(volume, volume_mean)

    typical_price = (high + low + close) / 3
    rolling_value = (typical_price * volume).rolling(20).sum()
    rolling_volume = volume.rolling(20).sum()
    frame["rolling_vwap_20d"] = _safe_div(rolling_value, rolling_volume)
    frame["vwap_deviation_pct"] = _safe_div(close, frame["rolling_vwap_20d"]) - 1
    vwap_mean = frame["vwap_deviation_pct"].rolling(120).mean()
    vwap_std = frame["vwap_deviation_pct"].rolling(120).std()
    frame["vwap_deviation_z_120d"] = _safe_div(
        frame["vwap_deviation_pct"] - vwap_mean, vwap_std
    )

    range_high = high.rolling(20).max()
    range_low = low.rolling(20).min()
    frame["range_position_20d"] = _safe_div(close - range_low, range_high - range_low)

    frame["return_1d_percentile_252d"] = _rolling_last_percentile(
        frame["return_1d"], 252
    )
    frame["return_5d_percentile_252d"] = _rolling_last_percentile(
        frame["return_5d"], 252
    )

    benchmark = _clean_ohlcv(benchmark_df)
    if not benchmark.empty:
        benchmark_close = benchmark["Close"].reindex(frame.index).ffill()
        frame["benchmark_return_5d"] = benchmark_close.pct_change(5)
        frame["benchmark_return_20d"] = benchmark_close.pct_change(20)
        frame["spy_excess_return_5d"] = (
            frame["return_5d"] - frame["benchmark_return_5d"]
        )
        frame["spy_excess_return_20d"] = (
            frame["return_20d"] - frame["benchmark_return_20d"]
        )
    else:
        frame["benchmark_return_5d"] = np.nan
        frame["benchmark_return_20d"] = np.nan
        frame["spy_excess_return_5d"] = np.nan
        frame["spy_excess_return_20d"] = np.nan

    _add_constant_feature(
        frame, "pe_ratio", _latest_scalar(stock_info, "pe_ratio", "peRatio")
    )
    _add_constant_feature(
        frame, "forward_pe", _latest_scalar(stock_info, "forward_pe", "forwardPE")
    )
    _add_constant_feature(
        frame,
        "price_to_book",
        _latest_scalar(stock_info, "price_to_book", "priceToBook"),
    )
    _add_constant_feature(
        frame, "peg_ratio", _latest_scalar(stock_info, "peg_ratio", "pegRatio")
    )

    _add_constant_feature(
        frame, "overall_score", _technical_scalar(technical_data, "overall_score")
    )
    _add_constant_feature(frame, "rsi", _technical_scalar(technical_data, "rsi"))
    _add_constant_feature(frame, "adx", _technical_scalar(technical_data, "adx"))
    _add_constant_feature(
        frame, "bb_width", _technical_scalar(technical_data, "bb_width")
    )
    _add_constant_feature(
        frame, "pcr_ratio", _technical_scalar(technical_data, "pcr_ratio")
    )
    _add_constant_feature(frame, "atm_iv", _technical_scalar(technical_data, "atm_iv"))
    frame["gex_regime"] = (
        technical_data.get("gex_regime") if technical_data else "unknown"
    )

    return frame.replace([np.inf, -np.inf], np.nan)


def create_feature_snapshot(
    ticker: str,
    feature_frame: pd.DataFrame,
) -> StockFeatureSnapshot:
    """Return the latest feature row and basic quality metadata."""

    if feature_frame.empty:
        return StockFeatureSnapshot(
            ticker=ticker,
            as_of="",
            features={},
            data_quality={"status": "no_data"},
            lookback_days=0,
        )

    latest = feature_frame.iloc[-1]
    features: dict[str, float | str | None] = {}
    for column in FEATURE_COLUMNS + ["gex_regime"]:
        if column not in latest.index:
            features[column] = None
            continue
        value = latest[column]
        if isinstance(value, str):
            features[column] = value
        elif pd.isna(value):
            features[column] = None
        else:
            features[column] = float(value)

    missing_count = sum(value is None for value in features.values())
    return StockFeatureSnapshot(
        ticker=ticker,
        as_of=str(feature_frame.index[-1].date())
        if hasattr(feature_frame.index[-1], "date")
        else str(feature_frame.index[-1]),
        features=features,
        data_quality={
            "status": "ok" if missing_count < len(features) else "insufficient_data",
            "missing_features": missing_count,
            "total_features": len(features),
        },
        lookback_days=len(feature_frame),
    )
