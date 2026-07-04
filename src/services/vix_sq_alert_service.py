"""VIX technical and US options-expiration week alert diagnostics."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from src.services.technical_strategy_service import calculate_parabolic_sar


def build_vix_sq_alert_context(
    cboe_data: pd.DataFrame | None, *, today: date | pd.Timestamp | None = None
) -> dict[str, Any]:
    """Detect VIX MACD/PSAR trend persistence into monthly SQ week."""

    if cboe_data is None or cboe_data.empty or "VIX" not in cboe_data.columns:
        return {
            "status": "unavailable",
            "summary": "VIX履歴がないためSQ週アラートを判定できません。",
            "quality_warnings": ["VIX history unavailable."],
        }
    series = pd.to_numeric(cboe_data["VIX"], errors="coerce").dropna()
    if len(series) < 60:
        return {
            "status": "insufficient_data",
            "summary": "VIXのMACD/PSAR判定には60営業日以上が必要です。",
            "quality_warnings": ["Insufficient VIX history."],
        }
    frame = pd.DataFrame({"High": series, "Low": series, "Close": series})
    macd = _macd(series)
    psar = calculate_parabolic_sar(frame["High"], frame["Low"])
    macd_cross = _macd_cross(macd["line"], macd["signal"])
    psar_trend = "up" if series.iloc[-1] > psar.iloc[-1] else "down"
    vix_uptrend = macd["line"].iloc[-1] > macd["signal"].iloc[-1] and psar_trend == "up"
    vix_downturn = macd_cross == "dead_cross" and psar_trend == "down"
    current_day = (
        pd.Timestamp(today).date()
        if today is not None
        else pd.Timestamp(series.index[-1]).date()
    )
    sq = _monthly_expiration_friday(current_day)
    in_sq_week = abs((sq - current_day).days) <= 5 and current_day <= sq
    if vix_uptrend and in_sq_week:
        status = "hedge_alert"
        summary = "VIX上昇トレンドがSQ週まで残存。指数下落・ヘッジ警戒。"
        score = 1.0
    elif vix_downturn:
        status = "bottoming_candidate"
        summary = "VIXのMACDとPSARが下落転換。指数底打ち候補。"
        score = 0.75
    elif vix_uptrend:
        status = "vix_uptrend_watch"
        summary = "VIX上昇トレンド継続。SQ週接近時に再確認。"
        score = 0.55
    else:
        status = "neutral"
        summary = "VIX×SQの強い警戒/反転シグナルは未発火。"
        score = 0.0
    return {
        "status": status,
        "summary": summary,
        "score": score,
        "in_sq_week": in_sq_week,
        "monthly_expiration": sq.isoformat(),
        "vix": round(float(series.iloc[-1]), 2),
        "macd": round(float(macd["line"].iloc[-1]), 4),
        "macd_signal": round(float(macd["signal"].iloc[-1]), 4),
        "macd_cross": macd_cross,
        "psar_trend": psar_trend,
        "quality_warnings": [],
    }


def _monthly_expiration_friday(day: date) -> date:
    first = day.replace(day=1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    third_friday = first_friday + timedelta(days=14)
    if day > third_friday + timedelta(days=2):
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        first_friday = next_month + timedelta(days=(4 - next_month.weekday()) % 7)
        return first_friday + timedelta(days=14)
    return third_friday


def _macd(close: pd.Series) -> dict[str, pd.Series]:
    line = (
        close.ewm(span=12, adjust=False).mean()
        - close.ewm(span=26, adjust=False).mean()
    )
    signal = line.ewm(span=9, adjust=False).mean()
    return {"line": line, "signal": signal}


def _macd_cross(line: pd.Series, signal: pd.Series) -> str:
    if len(line) < 2:
        return "none"
    if line.iloc[-1] > signal.iloc[-1] and line.iloc[-2] <= signal.iloc[-2]:
        return "golden_cross"
    if line.iloc[-1] < signal.iloc[-1] and line.iloc[-2] >= signal.iloc[-2]:
        return "dead_cross"
    return "none"
