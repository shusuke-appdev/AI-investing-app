"""High-volatility stock regime diagnostics.

The output describes the quality of volatility and trend participation. It is
not a standalone buy/sell recommendation.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_FOMO_UNIVERSE = (
    "NVDA",
    "AMD",
    "AVGO",
    "MU",
    "SMCI",
    "285A.T",
    "000660.KS",
    "6857.T",
    "6920.T",
)


def analyze_fomo_volatility_regime(
    price_df: pd.DataFrame | None,
    *,
    ticker: str = "",
) -> dict[str, Any]:
    """Classify the latest high-volatility stock state from daily OHLCV."""

    frame = _prepare_frame(price_df)
    if len(frame) < 60:
        return {
            "ticker": ticker,
            "state": "insufficient_data",
            "label": "データ不足",
            "risk_level": "unknown",
            "evidence": ["判定には最低60営業日のOHLCVが必要です。"],
            "confirmation": "",
            "invalidation": "",
            "coexisting_flags": [],
            "profile": {},
            "metrics": {},
            "data_quality": {"status": "insufficient_data", "rows": len(frame)},
        }

    profile = _profile(len(frame))
    features = _feature_frame(frame, profile)
    latest = features.iloc[-1]
    prior = features.iloc[-2]

    uptrend = bool(
        latest["close"] > latest["ema20"] > latest["ema50"] > latest["ema100"]
    )
    volume_spike = bool(latest["volume_ratio"] >= profile["volume_spike_multiplier"])
    wide_range = bool(latest["range_atr"] >= profile["wide_range_atr_multiplier"])
    fomo = bool(
        volume_spike
        and wide_range
        and latest["rsi"] >= profile["fomo_rsi_threshold"]
        and latest["atr_rank"] >= profile["fomo_atr_rank_threshold"]
        and latest["close"] > latest["ema20"]
    )
    flags = {
        "confirmed_fomo_trap": bool(
            prior["high_price_stall"] and latest["close"] < prior["low"]
        ),
        "ema20_break": bool(
            prior["close"] >= prior["ema20"]
            and latest["close"] < latest["ema20"]
            and latest["atr_rank"] >= 65
            and latest["adx_slope_5d"] < 0
        ),
        "high_price_stall": bool(
            fomo
            and (latest["upper_wick_ratio"] >= 0.35 or latest["close_location"] <= 0.45)
        ),
        "selling_pressure": bool(
            latest["close"] < latest["open"]
            and volume_spike
            and latest["close_location"] <= 0.30
        ),
        "fomo_momentum": bool(
            fomo
            and latest["close_location"] >= 0.75
            and latest["upper_wick_ratio"] < 0.25
            and latest["close"] > latest["open"]
        ),
        "fomo_buying": fomo,
        "volatility_overheat": bool(latest["atr_rank"] >= 85),
        "breakout": bool(
            latest["close"] > latest["prior_donchian_high"]
            and uptrend
            and latest["adx"] >= 20
        ),
        "pullback_candidate": bool(
            uptrend
            and latest["low"] <= latest["ema20"] * 1.015
            and latest["close"] > latest["ema20"]
            and latest["close"] > latest["open"]
        ),
        "trend_continuation": bool(uptrend and latest["adx"] >= 20),
    }
    precedence = [
        "confirmed_fomo_trap",
        "ema20_break",
        "high_price_stall",
        "selling_pressure",
        "fomo_momentum",
        "fomo_buying",
        "volatility_overheat",
        "breakout",
        "pullback_candidate",
        "trend_continuation",
    ]
    state = next((name for name in precedence if flags[name]), "neutral")
    labels = {
        "confirmed_fomo_trap": "FOMO Trap",
        "ema20_break": "20EMA割れ",
        "high_price_stall": "高値失速",
        "selling_pressure": "売り圧力増加",
        "fomo_momentum": "FOMO Momentum",
        "fomo_buying": "FOMO Buying",
        "volatility_overheat": "ボラティリティ過熱",
        "breakout": "高値ブレイク",
        "pullback_candidate": "押し目候補",
        "trend_continuation": "上昇トレンド継続",
        "neutral": "中立",
    }
    risk_levels = {
        "confirmed_fomo_trap": "critical",
        "ema20_break": "high",
        "high_price_stall": "high",
        "selling_pressure": "high",
        "fomo_buying": "elevated",
        "volatility_overheat": "elevated",
        "fomo_momentum": "elevated",
        "breakout": "moderate",
        "pullback_candidate": "moderate",
        "trend_continuation": "moderate",
        "neutral": "low",
    }
    active = [name for name in precedence if flags[name]]
    return {
        "ticker": ticker,
        "state": state,
        "label": labels[state],
        "risk_level": risk_levels[state],
        "evidence": _evidence(latest, active),
        "confirmation": _confirmation(state),
        "invalidation": _invalidation(state),
        "coexisting_flags": active,
        "profile": profile,
        "metrics": {
            "close": _round(latest["close"], 2),
            "atr_percent": _round(latest["atr_percent"], 2),
            "atr_rank": _round(latest["atr_rank"], 1),
            "rsi": _round(latest["rsi"], 1),
            "adx": _round(latest["adx"], 1),
            "volume_ratio": _round(latest["volume_ratio"], 2),
            "range_atr": _round(latest["range_atr"], 2),
            "close_location": _round(latest["close_location"], 2),
        },
        "data_quality": {
            "status": "ok",
            "rows": len(frame),
            "as_of": str(frame.index[-1].date())
            if hasattr(frame.index[-1], "date")
            else str(frame.index[-1]),
        },
    }


def scan_fomo_universe(
    data_fetcher: Callable[[str, str], pd.DataFrame],
    tickers: list[str] | tuple[str, ...] = DEFAULT_FOMO_UNIVERSE,
    *,
    max_workers: int = 6,
) -> dict[str, Any]:
    """Scan a bounded watchlist while preserving partial successes."""

    normalized = list(
        dict.fromkeys(
            str(item).strip().upper() for item in tickers if str(item).strip()
        )
    )[:20]
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(
        max_workers=min(max_workers, max(1, len(normalized)))
    ) as executor:
        futures = {
            executor.submit(data_fetcher, ticker, "1y"): ticker for ticker in normalized
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = analyze_fomo_volatility_regime(future.result(), ticker=ticker)
                result["rank_score"] = _rank_score(result)
                items.append(result)
            except Exception as exc:
                errors.append(f"{ticker}: {exc}")
    items.sort(key=lambda item: float(item.get("rank_score", 0.0)), reverse=True)
    return {
        "summary": f"{len(items)}/{len(normalized)}銘柄を判定",
        "items": items,
        "errors": errors,
        "is_partial": bool(errors),
    }


def _prepare_frame(price_df: pd.DataFrame | None) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return pd.DataFrame()
    frame = price_df.copy().sort_index()
    lookup = {str(column).lower(): column for column in frame.columns}
    normalized = pd.DataFrame(index=frame.index)
    for name in ("open", "high", "low", "close", "volume"):
        source = lookup.get(name)
        if source is None:
            if name == "volume":
                normalized[name] = 0.0
            elif "close" in normalized:
                normalized[name] = normalized["close"]
            else:
                return pd.DataFrame()
        else:
            normalized[name] = pd.to_numeric(frame[source], errors="coerce")
    return normalized.dropna(subset=["close"])


def _feature_frame(frame: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    close, high, low = out["close"], out["high"], out["low"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(14).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_di = 100 * plus_dm.rolling(14).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(14).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    candle_range = (high - low).replace(0, np.nan)

    out["ema20"] = close.ewm(span=20, adjust=False).mean()
    out["ema50"] = close.ewm(span=50, adjust=False).mean()
    out["ema100"] = close.ewm(span=100, adjust=False).mean()
    out["atr_percent"] = atr / close * 100
    out["atr_rank"] = (
        out["atr_percent"]
        .rolling(
            profile["atr_rank_window"],
            min_periods=min(40, profile["atr_rank_window"]),
        )
        .rank(pct=True)
        * 100
    )
    out["rsi"] = 100 - 100 / (1 + rs)
    out["adx"] = dx.rolling(14).mean()
    out["adx_slope_5d"] = out["adx"].diff(5)
    out["prior_donchian_high"] = high.rolling(20).max().shift(1)
    out["volume_ratio"] = out["volume"] / out["volume"].rolling(20).mean().replace(
        0, np.nan
    )
    out["range_atr"] = true_range / atr.replace(0, np.nan)
    out["close_location"] = (close - low) / candle_range
    out["upper_wick_ratio"] = (
        high - pd.concat([out["open"], close], axis=1).max(axis=1)
    ) / candle_range
    fomo_series = (
        (out["volume_ratio"] >= profile["volume_spike_multiplier"])
        & (out["range_atr"] >= profile["wide_range_atr_multiplier"])
        & (out["rsi"] >= profile["fomo_rsi_threshold"])
        & (out["atr_rank"] >= profile["fomo_atr_rank_threshold"])
        & (out["close"] > out["ema20"])
    )
    out["high_price_stall"] = fomo_series & (
        (out["upper_wick_ratio"] >= 0.35) | (out["close_location"] <= 0.45)
    )
    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _profile(rows: int) -> dict[str, Any]:
    if rows < 120:
        return {
            "name": "short_history",
            "atr_rank_window": 60,
            "fomo_rsi_threshold": 70,
            "fomo_atr_rank_threshold": 65,
            "volume_spike_multiplier": 1.8,
            "wide_range_atr_multiplier": 1.25,
        }
    return {
        "name": "established",
        "atr_rank_window": 120,
        "fomo_rsi_threshold": 72,
        "fomo_atr_rank_threshold": 70,
        "volume_spike_multiplier": 2.0,
        "wide_range_atr_multiplier": 1.35,
    }


def _evidence(latest: pd.Series, active: list[str]) -> list[str]:
    evidence = [
        f"ATR%順位 {latest['atr_rank']:.0f} / RSI {latest['rsi']:.0f} / ADX {latest['adx']:.0f}",
        f"出来高倍率 {latest['volume_ratio']:.2f}x / 値幅 {latest['range_atr']:.2f} ATR",
    ]
    if active:
        evidence.append("併存状態: " + ", ".join(active))
    return evidence


def _confirmation(state: str) -> str:
    return {
        "pullback_candidate": "EMA20上を維持し、直近高値を終値で更新すること。",
        "breakout": "ブレイク水準を終値で維持し、出来高が急減しないこと。",
        "fomo_momentum": "高値圏で強く引け続け、上ヒゲが拡大しないこと。",
        "high_price_stall": "失速日の安値を終値で割るとTrap警戒が強まります。",
    }.get(state, "次の終値と出来高で状態継続を確認してください。")


def _invalidation(state: str) -> str:
    if state in {
        "breakout",
        "pullback_candidate",
        "trend_continuation",
        "fomo_momentum",
    }:
        return "EMA20または直近支持線の終値割れ。"
    if state in {
        "confirmed_fomo_trap",
        "ema20_break",
        "high_price_stall",
        "selling_pressure",
    }:
        return "失速水準を出来高を伴って回復すること。"
    return "価格・出来高・ATR順位の組み合わせが変化すること。"


def _round(value: Any, digits: int) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else round(number, digits)


def _rank_score(result: dict[str, Any]) -> float:
    severity = {
        "confirmed_fomo_trap": 100,
        "high_price_stall": 90,
        "ema20_break": 85,
        "selling_pressure": 80,
        "fomo_momentum": 75,
        "fomo_buying": 70,
        "volatility_overheat": 65,
        "breakout": 60,
        "pullback_candidate": 55,
        "trend_continuation": 40,
        "neutral": 0,
    }
    metrics = result.get("metrics") or {}
    return float(severity.get(result.get("state"), 0)) + min(
        float(metrics.get("volume_ratio") or 0) * 2,
        10,
    )
