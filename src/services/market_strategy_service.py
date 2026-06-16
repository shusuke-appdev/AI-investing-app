"""Market direction, key levels, and strategy-regime selection."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.log_config import get_logger
from src.market_data import get_stock_data
from src.market_volatility_intelligence import fetch_cboe_indices

logger = get_logger(__name__)

LEVEL_TICKERS = {
    "S&P 500": "SPY",
    "Nasdaq 100": "QQQ",
}

DRIVER_TICKERS = {
    "US10Y": "^TNX",
    "WTI": "CL=F",
    "Gold": "GC=F",
    "Dollar": "UUP",
}


def build_market_strategy_context(
    market_type: str = "US",
    *,
    options: list[dict[str, Any]] | None = None,
    ibd_regime: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
    volatility_regime: dict[str, Any] | None = None,
    credit_stress: dict[str, Any] | None = None,
    trend_ranking: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return all strategy-related market-monitoring payloads."""

    if market_type != "US":
        return {
            "important_levels": {},
            "market_timeframes": {},
            "strategy_regime": {},
            "market_driver_monitor": {},
        }
    levels = build_important_levels()
    drivers = build_market_driver_monitor()
    timeframes = build_timeframe_outlooks(
        levels,
        drivers,
        options=options,
        ibd_regime=ibd_regime,
        evaluation=evaluation,
        volatility_regime=volatility_regime,
        credit_stress=credit_stress,
        trend_ranking=trend_ranking,
    )
    strategy = select_strategy_regime(
        levels,
        timeframes,
        options=options,
        ibd_regime=ibd_regime,
        volatility_regime=volatility_regime,
    )
    return {
        "important_levels": levels,
        "market_timeframes": timeframes,
        "strategy_regime": strategy,
        "market_driver_monitor": drivers,
    }


def build_important_levels() -> dict[str, Any]:
    """Calculate key price levels and latest behavior for SPY and QQQ."""

    items = []
    warnings = []
    for label, ticker in LEVEL_TICKERS.items():
        try:
            frame = get_stock_data(ticker, "1y")
        except Exception as exc:
            logger.warning("[MarketStrategy] %s level fetch failed: %s", ticker, exc)
            frame = pd.DataFrame()
        payload = _level_payload(label, ticker, frame)
        if payload.get("data_quality") != "ok":
            warnings.append(f"{ticker} key levels unavailable.")
        items.append(payload)
    return {
        "items": items,
        "summary": _levels_summary(items),
        "quality_warnings": warnings,
    }


def build_market_driver_monitor() -> dict[str, Any]:
    """Build level/change diagnostics for macro and volatility drivers."""

    rows = []
    warnings = []
    for label, ticker in DRIVER_TICKERS.items():
        try:
            frame = get_stock_data(ticker, "3mo")
        except Exception as exc:
            logger.warning("[MarketStrategy] %s driver fetch failed: %s", ticker, exc)
            frame = pd.DataFrame()
        payload = _driver_payload(label, ticker, frame)
        if payload.get("data_quality") != "ok":
            warnings.append(f"{label} unavailable.")
        rows.append(payload)

    cboe = fetch_cboe_indices()
    if cboe.data.empty:
        warnings.extend(cboe.warnings)
    else:
        for symbol in ("VIX", "VVIX", "SKEW", "VIX9D", "VIX3M"):
            if symbol in cboe.data:
                rows.append(_series_driver_payload(symbol, symbol, cboe.data[symbol]))

    return {
        "items": rows,
        "summary": _drivers_summary(rows),
        "source": "yfinance_and_cboe",
        "quality_warnings": warnings[:10],
    }


def build_timeframe_outlooks(
    levels: dict[str, Any],
    drivers: dict[str, Any],
    *,
    options: list[dict[str, Any]] | None = None,
    ibd_regime: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
    volatility_regime: dict[str, Any] | None = None,
    credit_stress: dict[str, Any] | None = None,
    trend_ranking: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify current, one-week, and one-month market direction."""

    current_score = _current_score(levels, ibd_regime, evaluation)
    week_score = current_score * 0.45 + _option_score(options) + _driver_score(drivers)
    month_score = (
        current_score * 0.35
        + _trend_ranking_score(trend_ranking)
        + _credit_score(credit_stress)
        + _volatility_score(volatility_regime)
    )
    rows = [
        _outlook(
            "現在時点", "current", current_score, _current_evidence(levels, ibd_regime)
        ),
        _outlook("1週間先", "one_week", week_score, _week_evidence(options, drivers)),
        _outlook(
            "1ヶ月先",
            "one_month",
            month_score,
            _month_evidence(trend_ranking, credit_stress),
        ),
    ]
    return {
        "items": rows,
        "summary": " / ".join(
            f"{item['label']}: {item['direction_label']}" for item in rows
        ),
    }


def select_strategy_regime(
    levels: dict[str, Any],
    timeframes: dict[str, Any],
    *,
    options: list[dict[str, Any]] | None = None,
    ibd_regime: dict[str, Any] | None = None,
    volatility_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select one of the five requested strategy regimes."""

    outlooks = {item["key"]: item for item in (timeframes or {}).get("items", [])}
    current = float(outlooks.get("current", {}).get("score", 0.0))
    one_week = float(outlooks.get("one_week", {}).get("score", 0.0))
    behavior = _dominant_behavior(levels)
    option_score = _option_score(options)
    ibd_key = str((ibd_regime or {}).get("status_key") or "")
    vol_label = str((volatility_regime or {}).get("regime") or "")

    if (
        current >= 0.55
        and one_week >= 0.45
        and behavior in {"breakout", "support_bounce"}
    ):
        key = "aggressive_trend_following"
        label = "積極的順張り"
    elif current >= 0.25 and one_week >= 0.15:
        key = "trend_following"
        label = "順張り"
    elif behavior == "support_bounce" and current < 0.1 and option_score >= 0.15:
        key = "aggressive_mean_reversion"
        label = "積極的逆張り"
    elif current <= -0.25 and behavior in {"near_support", "support_bounce"}:
        key = "mean_reversion"
        label = "逆張り"
    else:
        key = "wait"
        label = "判断不能(待ち)"

    if ibd_key == "market_in_correction" and key == "aggressive_trend_following":
        key = "trend_following"
        label = "順張り"
    if vol_label in {"persistent_stress", "shock_rising"} and key.startswith(
        "aggressive"
    ):
        key = "wait"
        label = "判断不能(待ち)"

    return {
        "key": key,
        "label": label,
        "rationale": _strategy_rationale(
            label, behavior, current, one_week, option_score
        ),
        "risk_budget": _strategy_risk_budget(key),
        "invalidation": _strategy_invalidation(key, levels),
        "evidence": [
            f"重要水準での挙動={behavior}",
            f"現在スコア={current:+.2f}",
            f"1週間スコア={one_week:+.2f}",
            f"オプション寄与={option_score:+.2f}",
        ],
    }


def _level_payload(label: str, ticker: str, frame: pd.DataFrame) -> dict[str, Any]:
    close = _close(frame)
    if len(close) < 50:
        return {"label": label, "ticker": ticker, "data_quality": "insufficient"}
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    ma20 = _ma(close, 20)
    ma50 = _ma(close, 50)
    ma200 = _ma(close, 200)
    high_63 = float(close.tail(63).max())
    low_63 = float(close.tail(63).min())
    atr = _atr(frame)
    behavior = _level_behavior(
        latest, previous, ma20, ma50, ma200, high_63, low_63, atr
    )
    return {
        "label": label,
        "ticker": ticker,
        "close": round(latest, 2),
        "change_1d": round((latest - previous) / previous * 100, 2)
        if previous
        else 0.0,
        "ma20": _round(ma20),
        "ma50": _round(ma50),
        "ma200": _round(ma200),
        "resistance": round(high_63, 2),
        "support": round(max(value for value in (low_63, ma50 or 0) if value), 2),
        "lower_support": round(low_63, 2),
        "atr14": _round(atr),
        "behavior": behavior,
        "behavior_label": _behavior_label(behavior),
        "data_quality": "ok",
    }


def _level_behavior(
    latest: float,
    previous: float,
    ma20: float | None,
    ma50: float | None,
    ma200: float | None,
    high_63: float,
    low_63: float,
    atr: float | None,
) -> str:
    band = atr or latest * 0.015
    if latest >= high_63 - band * 0.2 and latest > previous:
        return "breakout"
    if latest <= low_63 + band and latest > previous:
        return "support_bounce"
    if latest <= low_63 - band * 0.2:
        return "breakdown"
    if ma50 and abs(latest - ma50) <= band:
        return "near_support"
    if ma20 and latest < ma20 and ma50 and latest > ma50:
        return "resistance"
    if ma200 and latest < ma200:
        return "breakdown"
    return "range"


def _driver_payload(label: str, ticker: str, frame: pd.DataFrame) -> dict[str, Any]:
    close = _close(frame)
    if len(close) < 22:
        return {"label": label, "ticker": ticker, "data_quality": "insufficient"}
    latest = float(close.iloc[-1])
    if ticker == "^TNX":
        latest = latest / 10.0
    return {
        "label": label,
        "ticker": ticker,
        "value": round(latest, 3),
        "change_5d": _period_change(close, 5),
        "change_20d": _period_change(close, 20),
        "interpretation": "変動重視"
        if label in {"US10Y", "WTI", "VIX", "VVIX"}
        else "水準と変動",
        "data_quality": "ok",
    }


def _series_driver_payload(
    label: str, ticker: str, series: pd.Series
) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 22:
        return {"label": label, "ticker": ticker, "data_quality": "insufficient"}
    return {
        "label": label,
        "ticker": ticker,
        "value": round(float(clean.iloc[-1]), 2),
        "change_5d": _period_change(clean, 5),
        "change_20d": _period_change(clean, 20),
        "interpretation": "変動重視",
        "data_quality": "ok",
    }


def _current_score(
    levels: dict[str, Any],
    ibd_regime: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> float:
    behaviors = [item.get("behavior") for item in levels.get("items", [])]
    score = sum(_behavior_score(behavior) for behavior in behaviors) / max(
        len(behaviors), 1
    )
    score += float((ibd_regime or {}).get("score", 0.0)) * 0.25
    score += float((evaluation or {}).get("score", 0.0)) * 0.35
    return _clamp(score)


def _option_score(options: list[dict[str, Any]] | None) -> float:
    if not options:
        return 0.0
    scores = []
    for item in options:
        gex = item.get("gex") or {}
        nearby = _float(gex.get("nearby_net_gex"))
        pcr = _float((item.get("pcr") or {}).get("volume_pcr"))
        score = 0.0
        if nearby is not None and nearby < 0:
            score += 0.18
        elif nearby is not None and nearby > 0:
            score -= 0.05
        if pcr is not None and pcr < 0.75:
            score += 0.12
        elif pcr is not None and pcr > 1.25:
            score -= 0.12
        scores.append(score)
    return sum(scores) / max(len(scores), 1)


def _driver_score(drivers: dict[str, Any]) -> float:
    lookup = {item.get("label"): item for item in drivers.get("items", [])}
    vix_change = _float((lookup.get("VIX") or {}).get("change_5d")) or 0.0
    tnx_change = _float((lookup.get("US10Y") or {}).get("change_5d")) or 0.0
    oil_change = _float((lookup.get("WTI") or {}).get("change_5d")) or 0.0
    return _clamp(
        -vix_change / 40.0 - abs(tnx_change) / 80.0 - max(oil_change, 0) / 120.0
    )


def _trend_ranking_score(trend_ranking: dict[str, Any] | None) -> float:
    items = (trend_ranking or {}).get("items", [])
    if not items:
        return 0.0
    top = float(items[0].get("total_score", 0.0))
    return _clamp(top / 100.0)


def _credit_score(credit_stress: dict[str, Any] | None) -> float:
    status = str((credit_stress or {}).get("status") or "")
    if status == "rapid_stress":
        return -0.45
    if status == "watch":
        return -0.2
    if status == "equity_adjustment":
        return 0.15
    return 0.0


def _volatility_score(volatility_regime: dict[str, Any] | None) -> float:
    posture = str((volatility_regime or {}).get("posture") or "")
    if posture == "Defensive":
        return -0.35
    if posture in {"Pilot", "Staged"}:
        return 0.18
    return 0.0


def _outlook(label: str, key: str, score: float, evidence: list[str]) -> dict[str, Any]:
    score = _clamp(score)
    direction = (
        "uptrend" if score >= 0.25 else "downtrend" if score <= -0.25 else "range"
    )
    return {
        "label": label,
        "key": key,
        "score": round(score, 2),
        "market_tone": _tone(score),
        "direction": direction,
        "direction_label": {
            "uptrend": "上昇相場",
            "range": "レンジ相場",
            "downtrend": "下落相場",
        }[direction],
        "confidence": "高"
        if abs(score) >= 0.55
        else "中"
        if abs(score) >= 0.25
        else "低",
        "evidence": evidence,
    }


def _current_evidence(
    levels: dict[str, Any], ibd_regime: dict[str, Any] | None
) -> list[str]:
    evidence = [levels.get("summary", "")]
    if ibd_regime and ibd_regime.get("label"):
        evidence.append(f"IBD式状態={ibd_regime.get('label')}")
    return [item for item in evidence if item]


def _week_evidence(
    options: list[dict[str, Any]] | None, drivers: dict[str, Any]
) -> list[str]:
    evidence = []
    if options:
        evidence.append("主要ETFオプション構造を反映")
    if drivers.get("summary"):
        evidence.append(drivers["summary"])
    return evidence


def _month_evidence(
    trend_ranking: dict[str, Any] | None, credit_stress: dict[str, Any] | None
) -> list[str]:
    evidence = []
    if trend_ranking and trend_ranking.get("summary"):
        evidence.append(trend_ranking["summary"])
    if credit_stress and credit_stress.get("summary"):
        evidence.append(credit_stress["summary"])
    return evidence


def _dominant_behavior(levels: dict[str, Any]) -> str:
    scores = {}
    for item in levels.get("items", []):
        behavior = str(item.get("behavior") or "range")
        scores[behavior] = scores.get(behavior, 0) + 1
    return max(scores, key=scores.get) if scores else "range"


def _strategy_rationale(
    label: str, behavior: str, current: float, one_week: float, option_score: float
) -> str:
    return (
        f"{label}: 重要水準での挙動={_behavior_label(behavior)}、"
        f"現在={current:+.2f}、1週間={one_week:+.2f}、"
        f"オプション寄与={option_score:+.2f}。"
    )


def _strategy_risk_budget(key: str) -> str:
    return {
        "aggressive_trend_following": "60-100%",
        "trend_following": "30-70%",
        "wait": "0-30%",
        "mean_reversion": "10-30%",
        "aggressive_mean_reversion": "20-40%",
    }.get(key, "0-30%")


def _strategy_invalidation(key: str, levels: dict[str, Any]) -> str:
    items = levels.get("items", [])
    if not items:
        return "重要水準が取得できるまで判断しない"
    first = items[0]
    if key in {"aggressive_trend_following", "trend_following"}:
        return f"{first.get('label')} が50日線または直近支持を明確に割る"
    if key in {"mean_reversion", "aggressive_mean_reversion"}:
        return f"{first.get('label')} が直近安値を再度割り込む"
    return "支持/抵抗のどちらかを明確に突破するまで待つ"


def _behavior_score(behavior: str | None) -> float:
    return {
        "breakout": 0.55,
        "support_bounce": 0.35,
        "range": 0.0,
        "near_support": -0.05,
        "resistance": -0.15,
        "breakdown": -0.55,
    }.get(str(behavior or "range"), 0.0)


def _behavior_label(behavior: str) -> str:
    return {
        "breakout": "突破",
        "support_bounce": "反発/下値形成",
        "range": "レンジ",
        "near_support": "支持接近",
        "resistance": "抵抗",
        "breakdown": "割れ",
    }.get(behavior, behavior)


def _tone(score: float) -> str:
    if score >= 0.35:
        return "強気"
    if score <= -0.35:
        return "弱気"
    return "中立"


def _levels_summary(items: list[dict[str, Any]]) -> str:
    available = [item for item in items if item.get("data_quality") == "ok"]
    if not available:
        return "重要水準は判定不能です。"
    return " / ".join(
        f"{item['label']} {item['behavior_label']} close={item['close']}"
        for item in available
    )


def _drivers_summary(items: list[dict[str, Any]]) -> str:
    lookup = {item.get("label"): item for item in items}
    parts = []
    for label in ("VIX", "VVIX", "US10Y", "WTI"):
        item = lookup.get(label)
        if item and item.get("data_quality") == "ok":
            parts.append(f"{label} 5日={item.get('change_5d'):+.1f}%")
    return " / ".join(parts) if parts else "市場ドライバーは一部不足しています。"


def _close(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    column = next((col for col in frame.columns if str(col).lower() == "close"), None)
    if column is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _ma(close: pd.Series, window: int) -> float | None:
    if len(close) < window:
        return None
    value = close.rolling(window).mean().iloc[-1]
    return None if pd.isna(value) else float(value)


def _atr(frame: pd.DataFrame | None, window: int = 14) -> float | None:
    if frame is None or frame.empty or "High" not in frame or "Low" not in frame:
        return None
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = _close(frame)
    if len(close) < window + 1:
        return None
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    value = true_range.rolling(window).mean().iloc[-1]
    return None if pd.isna(value) else float(value)


def _period_change(series: pd.Series, periods: int) -> float:
    if len(series) <= periods:
        return 0.0
    previous = float(series.iloc[-periods - 1])
    current = float(series.iloc[-1])
    return round((current - previous) / previous * 100, 2) if previous else 0.0


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))
