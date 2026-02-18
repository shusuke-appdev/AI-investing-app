"""
テクニカル指標（パターン認識）モジュール

極値検出 (Higher Highs/Lower Lows) および
ローソク足パターン認識 (pandas-ta利用) の関数を提供します。
"""

import numpy as np
import pandas as pd


def detect_peaks_valleys(
    close: pd.Series, high: pd.Series, low: pd.Series, order: int = 5
) -> dict:
    """
    極値検出（scipy.signal.argrelextrema）。

    ピーク（swing high）とバレー（swing low）を検出し、
    Higher Highs / Lower Lows のトレンド構造を判定する。

    Returns:
        {"peaks": list, "valleys": list, "signal": str}
    """
    from scipy.signal import argrelextrema

    high_arr = high.values
    low_arr = low.values

    peak_indices = argrelextrema(high_arr, np.greater, order=order)[0]
    valley_indices = argrelextrema(low_arr, np.less, order=order)[0]

    recent_peaks = [(int(i), float(high_arr[i])) for i in peak_indices[-5:]]
    recent_valleys = [(int(i), float(low_arr[i])) for i in valley_indices[-5:]]

    signal = "unknown"
    if len(recent_peaks) >= 2 and len(recent_valleys) >= 2:
        hh = recent_peaks[-1][1] > recent_peaks[-2][1]
        hl = recent_valleys[-1][1] > recent_valleys[-2][1]
        lh = recent_peaks[-1][1] < recent_peaks[-2][1]
        ll = recent_valleys[-1][1] < recent_valleys[-2][1]

        if hh and hl:
            signal = "higher_highs"
        elif lh and ll:
            signal = "lower_lows"
        else:
            signal = "range"

    return {"peaks": recent_peaks, "valleys": recent_valleys, "signal": signal}


def detect_candlestick_patterns(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    rsi: float = 50.0,
    bb_position: str = "中間",
) -> dict:
    """
    ローソク足パターン認識（pandas-ta）。

    実用的な10パターンに絞り、RSI/BB位置でフィルタリングして誤検出を抑制する。

    Returns:
        {"patterns": list[dict], "summary": str, "score_adjustment": float}
    """
    try:
        import importlib.util

        if importlib.util.find_spec("pandas_ta") is None:
            raise ImportError
        import pandas_ta as ta  # noqa: F401
    except ImportError:
        return {"patterns": [], "summary": "ライブラリなし", "score_adjustment": 0.0}

    target_patterns = [
        "engulfing",
        "hammer",
        "invertedhammer",
        "morningstar",
        "eveningstar",
        "3whitesoldiers",
        "3blackcrows",
        "doji",
        "shootingstar",
        "hangingman",
    ]

    df = pd.DataFrame(
        {
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
        }
    )

    detected: list[dict] = []
    for pattern_name in target_patterns:
        try:
            result = df.ta.cdl_pattern(name=pattern_name)
            if result is not None and not result.empty:
                last_val = int(result.iloc[-1].iloc[0])
                if last_val != 0:
                    detected.append({"name": pattern_name, "signal": last_val})
        except Exception:
            continue

    if not detected:
        return {"patterns": [], "summary": "パターンなし", "score_adjustment": 0.0}

    score_adj = 0.0
    for p in detected:
        raw = 0.3 if p["signal"] > 0 else -0.3
        if p["signal"] > 0 and rsi < 35:
            raw *= 1.5
        elif p["signal"] > 0 and rsi > 65:
            raw *= 0.3
        if p["signal"] > 0 and bb_position in ("下限突破", "下半分"):
            raw *= 1.3
        elif p["signal"] < 0 and bb_position in ("上限突破", "上半分"):
            raw *= 1.3
        score_adj += raw

    bullish_count = sum(1 for p in detected if p["signal"] > 0)
    bearish_count = sum(1 for p in detected if p["signal"] < 0)

    if bullish_count > bearish_count:
        summary = "bullish"
    elif bearish_count > bullish_count:
        summary = "bearish"
    else:
        summary = "neutral"

    return {
        "patterns": detected,
        "summary": summary,
        "score_adjustment": max(-0.5, min(0.5, score_adj)),
    }
