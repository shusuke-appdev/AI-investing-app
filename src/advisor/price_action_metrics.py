"""Pure daily-price metrics shared by stock and theme-leader analysis."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd


def normalize_price_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Normalize an OHLCV frame without fetching or filling missing evidence."""

    if frame is None or frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(column not in normalized.columns for column in required):
        return pd.DataFrame()
    result = normalized.loc[:, required].copy()
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["High", "Low", "Close", "Volume"]).sort_index()


def atr_series(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    window: int = 14,
) -> pd.Series:
    """Return Wilder-style true-range rolling mean without zero-filling warmup."""

    previous = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous).abs(), (low - previous).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window).mean()


def period_returns(
    close: pd.Series,
    periods: Iterable[int] = (20, 63, 126),
) -> dict[str, float]:
    """Return percentage changes for available session windows only."""

    clean = pd.to_numeric(close, errors="coerce").dropna()
    result: dict[str, float] = {}
    if clean.empty:
        return result
    latest = float(clean.iloc[-1])
    for window in periods:
        if len(clean) <= window:
            continue
        base = _finite_float(clean.iloc[-window - 1])
        if base in (None, 0):
            continue
        result[f"{window}d"] = (latest / base - 1) * 100
    return result


def relative_returns(
    stock: pd.Series,
    benchmark: pd.Series,
    periods: Iterable[int] = (20, 63, 126),
) -> dict[str, float]:
    """Compare aligned stock and benchmark returns over session windows."""

    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1)
    aligned = aligned.ffill().dropna()
    result: dict[str, float] = {}
    for window in periods:
        if len(aligned) <= window:
            continue
        stock_base = _finite_float(aligned["stock"].iloc[-window - 1])
        benchmark_base = _finite_float(aligned["benchmark"].iloc[-window - 1])
        if stock_base in (None, 0) or benchmark_base in (None, 0):
            continue
        stock_return = float(aligned["stock"].iloc[-1]) / stock_base - 1
        benchmark_return = float(aligned["benchmark"].iloc[-1]) / benchmark_base - 1
        result[f"{window}d"] = (stock_return - benchmark_return) * 100
    return result


def rs_line_near_high(
    stock: pd.Series,
    benchmark: pd.Series,
    *,
    threshold: float = 0.99,
    min_sessions: int = 126,
) -> bool:
    """Return whether the price-ratio RS line is near its 52-week high."""

    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1)
    aligned = aligned.ffill().dropna()
    if len(aligned) < min_sessions:
        return False
    rs_line = aligned["stock"] / aligned["benchmark"].replace(0, pd.NA)
    recent = rs_line.tail(252).dropna()
    return bool(not recent.empty and recent.iloc[-1] >= recent.max() * threshold)


def recent_pivot(high: pd.Series, *, lookback: int = 50) -> float | None:
    """Return the highest high before the latest session."""

    clean = pd.to_numeric(high, errors="coerce")
    if len(clean) < lookback + 1:
        return None
    return _finite_float(clean.iloc[-lookback - 1 : -1].max())


def relative_volume(volume: pd.Series, *, lookback: int = 50) -> float | None:
    """Return latest volume divided by the preceding-session mean."""

    clean = pd.to_numeric(volume, errors="coerce")
    if len(clean) < lookback + 1:
        return None
    prior = _finite_float(clean.iloc[-lookback - 1 : -1].mean())
    latest = _finite_float(clean.iloc[-1])
    if prior in (None, 0) or latest is None:
        return None
    return latest / prior


def atr_contraction(
    atr: pd.Series, *, recent_sessions: int = 10, prior_sessions: int = 20
) -> bool:
    """Compare recent ATR mean with the preceding window."""

    required = recent_sessions + prior_sessions
    if len(atr) < required:
        return False
    recent = _finite_float(atr.iloc[-recent_sessions:].mean())
    prior = _finite_float(atr.iloc[-required:-recent_sessions].mean())
    return bool(recent is not None and prior is not None and recent < prior)


def volume_contraction(
    volume: pd.Series,
    *,
    recent_sessions: int = 10,
    prior_sessions: int = 40,
    threshold: float = 0.8,
) -> bool:
    """Return whether recent mean volume contracted versus its prior window."""

    required = recent_sessions + prior_sessions
    if len(volume) < required:
        return False
    recent = _finite_float(volume.iloc[-recent_sessions:].mean())
    prior = _finite_float(volume.iloc[-required:-recent_sessions].mean())
    return bool(
        recent is not None
        and prior is not None
        and prior > 0
        and recent <= prior * threshold
    )


def ma_extension_atr(current: float, moving_average: float, atr: float) -> float | None:
    """Return price extension above a moving average in ATR units."""

    if atr <= 0:
        return None
    return (current - moving_average) / atr


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None
