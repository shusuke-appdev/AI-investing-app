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
        if (
            p["signal"] > 0
            and bb_position in ("下限突破", "下半分")
            or p["signal"] < 0
            and bb_position in ("上限突破", "上半分")
        ):
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


def detect_pinbar(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, threshold_ratio: float = 0.6
) -> dict:
    """
    ローソク足の日足に対して、上髭または下髭が異常な割合を占めているか検知する。
    """
    latest_open = open_.iloc[-1]
    latest_high = high.iloc[-1]
    latest_low = low.iloc[-1]
    latest_close = close.iloc[-1]

    total_length = latest_high - latest_low
    if total_length == 0:
        return {"is_pinbar": False, "type": "none", "description": "値幅なし"}

    body_top = max(latest_open, latest_close)
    body_bottom = min(latest_open, latest_close)

    upper_shadow = latest_high - body_top
    lower_shadow = body_bottom - latest_low

    upper_ratio = upper_shadow / total_length
    lower_ratio = lower_shadow / total_length

    if lower_ratio >= threshold_ratio:
        return {"is_pinbar": True, "type": "bullish_pinbar", "description": f"長い下髭（全体の{lower_ratio:.0%}）。底打ち・買い向かいのサイン。"}
    elif upper_ratio >= threshold_ratio:
        return {"is_pinbar": True, "type": "bearish_pinbar", "description": f"長い上髭（全体の{upper_ratio:.0%}）。上値の重さを示唆。"}

    return {"is_pinbar": False, "type": "none", "description": "特筆すべきヒゲなし"}


def detect_volume_climax_vs_bleed(
    close: pd.Series, volume: pd.Series, window: int = 20
) -> dict:
    """
    出来高と価格下落の相関から、セリングクライマックス（投げ売り）か、
    だらだら下落（ナンピン厳禁）かを判定する。
    """
    if len(close) < window or volume.sum() == 0:
         return {"signal": "none", "description": "データ不足"}

    recent_vol = volume.iloc[-1]
    avg_vol = volume.iloc[-window:-1].mean()

    if avg_vol == 0:
        return {"signal": "none", "description": "出来高データなし"}

    vol_ratio = recent_vol / avg_vol
    price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]

    # 直近3日間のトレンド
    recent_trend = close.iloc[-3:].pct_change().sum()

    if price_change < -0.03 and vol_ratio >= 2.5:
        return {
            "signal": "selling_climax",
            "description": f"急激な下落と異常な出来高（平均の{vol_ratio:.1f}倍）。セリングクライマックス（投げ売り）の可能性があり、リバウンド買いの好機か。"
        }

    if recent_trend < -0.03 and vol_ratio < 1.0:
        return {
            "signal": "low_volume_bleed",
            "description": "出来高を伴わない継続的なだらだら下落。買い手不在（ナンピン厳禁）を示唆。"
        }

    return {"signal": "neutral", "description": "出来高・価格変動に異常なし"}


def detect_advanced_patterns(close: pd.Series, high: pd.Series, low: pd.Series) -> dict:
    """
    ヘッドアンドショルダー（H&S）やリバーサルアイランド等の高度なパターンを検知する。
    """
    pv = detect_peaks_valleys(close, high, low, order=3)
    peaks = pv["peaks"]

    patterns = []

    # ヘッドアンドショルダー検知 (簡易版)
    # 直近3つのPeakが存在し、 真ん中が一番高く、左右がそれより低い場合
    if len(peaks) >= 3:
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        # p2(Head) が p1, p3(Shoulders) より高いか
        if p2[1] > p1[1] and p2[1] > p3[1] and abs(p1[1] - p3[1]) / p1[1] < 0.05:
            # ネックラインの近さなどは厳密には計算しないが、形状として検知
            # 肩の高さがある程度近いか (2%以内)
            patterns.append("ヘッドアンドショルダー出現警戒（ナンピン厳禁）")

    # リバーサルアイランド（ギャップ）検知 (簡易版)
    # 直近5日間でギャップダウンして停滞後、ギャップアップしているか（またはその逆）
    if len(close) >= 5:
        recent_high = high.iloc[-5:]
        recent_low = low.iloc[-5:]

        # Bottom Island Reversal (買いシグナル)
        # Gap Down -> consolidation -> Gap Up
        gap_down = recent_high.iloc[1] < recent_low.iloc[0]
        gap_up = recent_low.iloc[4] > recent_high.iloc[3]
        if gap_down and gap_up:
             patterns.append("ボトム・リバーサルアイランド出現（強力な反転上昇サイン）")

        # Top Island Reversal (売りシグナル/ナンピン厳禁)
        gap_up_top = recent_low.iloc[1] > recent_high.iloc[0]
        gap_down_top = recent_high.iloc[4] < recent_low.iloc[3]
        if gap_up_top and gap_down_top:
             patterns.append("トップ・リバーサルアイランド出現（ナンピン厳禁・急落サイン）")

    return {
        "detected_patterns": patterns,
        "description": "、".join(patterns) if patterns else "特筆すべき高度パターンなし"
    }

