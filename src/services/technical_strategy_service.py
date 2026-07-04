"""Strategy-level technical diagnostics built from daily OHLCV data."""

from __future__ import annotations

from typing import Any

import pandas as pd


def build_technical_strategy_context(
    ticker: str, price_df: pd.DataFrame | None, *, market_type: str = "US"
) -> dict[str, Any]:
    """Return strategy-level diagnostics without replacing the base score."""

    frame = _normalize(price_df)
    if frame.empty or len(frame) < 80:
        return {
            "status": "insufficient_data",
            "summary": "戦略別テクニカル判定には80営業日以上のOHLCVが必要です。",
            "items": [],
            "quality_warnings": ["Insufficient daily OHLCV for strategy diagnostics."],
        }
    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    psar = calculate_parabolic_sar(high, low)
    macd = _macd(close)
    bb = _bollinger(close, period=25)
    divergence = _divergence_context(close, macd["line"])
    dow = _dow_context(close)
    bandwalk = _bandwalk_reversal_context(close, bb, psar, macd)
    fib = _fibonacci_extension_context(high, low, close)
    crash = _crash_top_context(close, high, low, bb, macd, divergence, fib)
    items = [bandwalk, divergence, dow, fib, crash]
    score = sum(float(item.get("score", 0.0)) for item in items) / len(items)
    summary = _summary(items, score)
    return {
        "ticker": ticker,
        "market_type": market_type,
        "status": "available",
        "summary": summary,
        "score": round(score, 2),
        "items": items,
        "parabolic_sar": {
            "latest": _round(psar.iloc[-1]),
            "trend": "bullish" if close.iloc[-1] > psar.iloc[-1] else "bearish",
            "reversal": _psar_reversal(close, psar),
        },
        "macd": {
            "line": _round(macd["line"].iloc[-1]),
            "signal": _round(macd["signal"].iloc[-1]),
            "cross": _macd_cross(macd["line"], macd["signal"]),
        },
        "quality_warnings": [],
    }


def calculate_parabolic_sar(
    high: pd.Series, low: pd.Series, *, step: float = 0.02, maximum: float = 0.2
) -> pd.Series:
    """Calculate Parabolic SAR with a small pandas-only implementation."""

    if len(high) == 0:
        return pd.Series(dtype=float)
    sar = pd.Series(index=high.index, dtype=float)
    bull = True
    af = step
    ep = float(high.iloc[0])
    sar.iloc[0] = float(low.iloc[0])
    for i in range(1, len(high)):
        prior = sar.iloc[i - 1]
        current = prior + af * (ep - prior)
        if bull:
            current = min(current, float(low.iloc[i - 1]))
            if i > 1:
                current = min(current, float(low.iloc[i - 2]))
            if low.iloc[i] < current:
                bull = False
                current = ep
                ep = float(low.iloc[i])
                af = step
            elif high.iloc[i] > ep:
                ep = float(high.iloc[i])
                af = min(maximum, af + step)
        else:
            current = max(current, float(high.iloc[i - 1]))
            if i > 1:
                current = max(current, float(high.iloc[i - 2]))
            if high.iloc[i] > current:
                bull = True
                current = ep
                ep = float(high.iloc[i])
                af = step
            elif low.iloc[i] < ep:
                ep = float(low.iloc[i])
                af = min(maximum, af + step)
        sar.iloc[i] = current
    return sar


def _bandwalk_reversal_context(
    close: pd.Series,
    bb: dict[str, pd.Series],
    psar: pd.Series,
    macd: dict[str, pd.Series],
) -> dict[str, Any]:
    upper_walk = (close.tail(10) >= bb["upper"].tail(10)).sum() >= 4
    lower_walk = (close.tail(10) <= bb["lower"].tail(10)).sum() >= 4
    left_band = (
        close.iloc[-1] < bb["upper"].iloc[-1]
        if upper_walk
        else close.iloc[-1] > bb["lower"].iloc[-1]
        if lower_walk
        else False
    )
    psar_inside = (
        psar.iloc[-1] <= bb["middle"].iloc[-1]
        if upper_walk
        else psar.iloc[-1] >= bb["middle"].iloc[-1]
        if lower_walk
        else False
    )
    macd_cross = _macd_cross(macd["line"], macd["signal"])
    confirmed = bool(left_band and psar_inside and macd_cross != "none")
    return {
        "key": "bandwalk_reversal",
        "label": "バンドウォーク終了・25日線回帰",
        "status": "confirmed"
        if confirmed
        else "watch"
        if upper_walk or lower_walk
        else "inactive",
        "score": 1.0 if confirmed else 0.45 if upper_walk or lower_walk else 0.0,
        "detail": (
            f"bandwalk={'upper' if upper_walk else 'lower' if lower_walk else 'none'} / "
            f"PSAR内側={'yes' if psar_inside else 'no'} / MACD={macd_cross}"
        ),
        "target": _round(bb["middle"].iloc[-1]),
        "warning": "" if psar_inside else "PSARが25日線の外側なら騙し確率が高い。",
    }


def _divergence_context(close: pd.Series, indicator: pd.Series) -> dict[str, Any]:
    highs = _swing_points(close, kind="high")
    ind_highs = _swing_points(indicator, kind="high")
    bearish = False
    if len(highs) >= 2 and len(ind_highs) >= 2:
        bearish = highs[-1][1] > highs[-2][1] and ind_highs[-1][1] < ind_highs[-2][1]
    support_break = bool(
        len(ind_highs) >= 2
        and indicator.iloc[-1] < min(ind_highs[-2][1], ind_highs[-1][1])
    )
    return {
        "key": "bearish_divergence",
        "label": "RSI/MACDダイバージェンス",
        "status": "triggered"
        if bearish and support_break
        else "watch"
        if bearish
        else "inactive",
        "score": 1.0 if bearish and support_break else 0.5 if bearish else 0.0,
        "detail": f"価格高値切上げ/指標切下げ={'yes' if bearish else 'no'} / 指標支持割れ={'yes' if support_break else 'no'}",
    }


def _dow_context(close: pd.Series) -> dict[str, Any]:
    highs = _swing_points(close, kind="high")
    lows = _swing_points(close, kind="low")
    uptrend = (
        len(highs) >= 2
        and len(lows) >= 2
        and highs[-1][1] > highs[-2][1]
        and lows[-1][1] > lows[-2][1]
    )
    downshift = len(lows) >= 2 and close.iloc[-1] < lows[-1][1]
    return {
        "key": "dow_theory",
        "label": "ダウ理論",
        "status": "trend_break"
        if downshift
        else "higher_high_higher_low"
        if uptrend
        else "range",
        "score": 1.0 if downshift else 0.2 if uptrend else 0.0,
        "detail": "直近安値割れ。"
        if downshift
        else "高値・安値切上げ。"
        if uptrend
        else "明確な切上げ/切下げなし。",
    }


def _fibonacci_extension_context(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> dict[str, Any]:
    swing_high = float(high.tail(126).max())
    swing_low = float(low.tail(126).min())
    diff = swing_high - swing_low
    current = float(close.iloc[-1])
    levels = {"361.8%": swing_low + diff * 3.618, "423.6%": swing_low + diff * 4.236}
    in_zone = diff > 0 and current >= levels["361.8%"] * 0.97
    return {
        "key": "fibonacci_red_zone",
        "label": "フィボナッチ天井圏",
        "status": "red_zone" if in_zone else "not_reached",
        "score": 0.7 if in_zone else 0.0,
        "detail": f"現在値={current:.2f} / 361.8%={levels['361.8%']:.2f} / 423.6%={levels['423.6%']:.2f}",
        "levels": levels,
    }


def _crash_top_context(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    bb: dict[str, pd.Series],
    macd: dict[str, pd.Series],
    divergence: dict[str, Any],
    fib: dict[str, Any],
) -> dict[str, Any]:
    ma5 = close.rolling(5).mean()
    ma25 = close.rolling(25).mean()
    dead_cross = (
        len(close) >= 26
        and ma5.iloc[-1] < ma25.iloc[-1]
        and ma5.iloc[-2] >= ma25.iloc[-2]
    )
    below_25 = close.iloc[-1] < ma25.iloc[-1]
    cloud = _ichimoku_cloud(high, low)
    wall = bool(
        cloud
        and close.iloc[-1] < cloud["cloud_bottom"]
        and cloud["cloud_top"] > close.iloc[-1]
    )
    triggered = (
        fib.get("status") == "red_zone"
        and divergence.get("status") in {"watch", "triggered"}
        and below_25
        and dead_cross
    )
    return {
        "key": "top_crash_pattern",
        "label": "天井圏・暴落パターン",
        "status": "triggered"
        if triggered
        else "watch"
        if below_25 and divergence.get("status") != "inactive"
        else "inactive",
        "score": 1.0
        if triggered and wall
        else 0.8
        if triggered
        else 0.35
        if below_25
        else 0.0,
        "detail": f"25日線割れ={'yes' if below_25 else 'no'} / 5-25DC={'yes' if dead_cross else 'no'} / 一目の壁={'yes' if wall else 'no'}",
        "target_risk": "15-20%下落警戒" if triggered and wall else "通常監視",
    }


def _normalize(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data.rename(columns={"close": "Close", "high": "High", "low": "Low"}, inplace=True)
    required = {"Close", "High", "Low"}
    if not required.issubset(data.columns):
        return pd.DataFrame()
    for column in required:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["Close", "High", "Low"])


def _bollinger(close: pd.Series, period: int = 25) -> dict[str, pd.Series]:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {"middle": middle, "upper": middle + 2 * std, "lower": middle - 2 * std}


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


def _psar_reversal(close: pd.Series, psar: pd.Series) -> str:
    if len(close) < 2 or len(psar) < 2:
        return "none"
    prev_above = close.iloc[-2] > psar.iloc[-2]
    now_above = close.iloc[-1] > psar.iloc[-1]
    if not prev_above and now_above:
        return "bullish"
    if prev_above and not now_above:
        return "bearish"
    return "none"


def _swing_points(
    series: pd.Series, *, kind: str, window: int = 3
) -> list[tuple[Any, float]]:
    points: list[tuple[Any, float]] = []
    data = series.dropna()
    for i in range(window, len(data) - window):
        chunk = data.iloc[i - window : i + window + 1]
        value = data.iloc[i]
        if kind == "high" and value == chunk.max():
            points.append((data.index[i], float(value)))
        if kind == "low" and value == chunk.min():
            points.append((data.index[i], float(value)))
    return points[-5:]


def _ichimoku_cloud(high: pd.Series, low: pd.Series) -> dict[str, float] | None:
    if len(high) < 52:
        return None
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high.rolling(52).max() + low.rolling(52).min()) / 2
    return {
        "cloud_top": float(max(senkou_a.iloc[-1], senkou_b.iloc[-1])),
        "cloud_bottom": float(min(senkou_a.iloc[-1], senkou_b.iloc[-1])),
    }


def _summary(items: list[dict[str, Any]], score: float) -> str:
    active = [
        item["label"]
        for item in items
        if item.get("status") not in {"inactive", "not_reached", "range"}
    ]
    if not active:
        return "追加戦略シグナルは未発火。"
    return f"戦略警戒 {score:.0%}: " + " / ".join(active[:3])


def _round(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return round(number, 4)
