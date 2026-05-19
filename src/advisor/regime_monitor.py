"""Regime and distribution-shift checks for stock signals."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SHIFT_FEATURES = [
    "return_5d",
    "return_20d",
    "realized_vol_20d",
    "vol_ratio_20_60",
    "volume_zscore_20d",
    "vwap_deviation_z_120d",
    "range_position_20d",
]


def _classify_volatility(latest_vol: float, history: pd.Series) -> str:
    clean = history.dropna()
    if len(clean) < 60 or not np.isfinite(latest_vol):
        return "Unknown"
    p40, p70, p90 = clean.quantile([0.40, 0.70, 0.90])
    if latest_vol >= p90:
        return "Crisis"
    if latest_vol >= p70:
        return "High"
    if latest_vol <= p40:
        return "Low"
    return "Normal"


def _classify_trend(frame: pd.DataFrame) -> str:
    if "close" not in frame.columns or len(frame) < 200:
        return "Unknown"
    close = frame["close"].dropna()
    if len(close) < 200:
        return "Unknown"
    latest = close.iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1]
    if latest > ma50 > ma200:
        return "Uptrend"
    if latest < ma50 < ma200:
        return "Downtrend"
    return "Range"


def _distribution_shift_score(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 100.0

    latest = frame.iloc[-1]
    z_scores: list[float] = []
    for column in SHIFT_FEATURES:
        if column not in frame.columns or column not in latest.index:
            continue
        history = frame[column].dropna().tail(756)
        if len(history) < 60:
            continue
        std = history.std()
        if not std or not np.isfinite(std):
            continue
        z_scores.append(abs(float((latest[column] - history.mean()) / std)))

    if not z_scores:
        return 100.0
    return float(min(100.0, np.mean(np.clip(z_scores, 0, 5)) * 20.0))


def _signal_decay_score(frame: pd.DataFrame) -> float:
    required = {"signal_label", "forward_5d_return"}
    if not required.issubset(frame.columns):
        return 0.0

    recent = frame.dropna(subset=["forward_5d_return"]).tail(60)
    if len(recent) < 20:
        return 0.0

    active = recent[recent["signal_label"] != "Neutral"]
    if len(active) < 10:
        return 0.0

    hit_rate = float((active["forward_5d_return"] > 0).mean())
    return float(max(0.0, (0.50 - hit_rate) * 200.0))


def evaluate_regime(feature_frame: pd.DataFrame) -> dict[str, Any]:
    """Return conservative regime and model-fit diagnostics."""

    if feature_frame.empty:
        return {
            "volatility_regime": "Unknown",
            "trend_regime": "Unknown",
            "distribution_shift_score": 100.0,
            "signal_decay_score": 0.0,
            "regime_fit": 0.0,
            "retraining_flag": True,
            "notes": ["Insufficient feature history for regime analysis."],
        }

    latest_vol = (
        float(feature_frame["realized_vol_20d"].iloc[-1])
        if "realized_vol_20d" in feature_frame
        else np.nan
    )
    volatility_regime = _classify_volatility(
        latest_vol, feature_frame.get("realized_vol_20d", pd.Series(dtype=float))
    )
    trend_regime = _classify_trend(feature_frame)
    shift_score = _distribution_shift_score(feature_frame)
    decay_score = _signal_decay_score(feature_frame)
    regime_fit = float(max(0.0, 100.0 - max(shift_score, decay_score)))
    notes: list[str] = []

    if volatility_regime in {"High", "Crisis"}:
        notes.append(
            f"Volatility regime is {volatility_regime}; size should be reduced."
        )
    if shift_score >= 50:
        notes.append("Current features differ materially from recent history.")
    if decay_score >= 25:
        notes.append("Recent similar signals have shown weaker hit rates.")
    if not notes:
        notes.append("Current feature distribution is broadly consistent with history.")

    return {
        "volatility_regime": volatility_regime,
        "trend_regime": trend_regime,
        "distribution_shift_score": round(shift_score, 2),
        "signal_decay_score": round(decay_score, 2),
        "regime_fit": round(regime_fit, 2),
        "retraining_flag": regime_fit < 50.0,
        "notes": notes,
    }
