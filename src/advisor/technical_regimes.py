"""
テクニカル指標（レジーム判定）モジュール

一目均衡表, BBスクイズ, 動的RSI, Anchored VWAP の計算関数を提供します。
"""

import pandas as pd


def calculate_ichimoku(close: pd.Series, high: pd.Series, low: pd.Series) -> dict:
    """
    一目均衡表を計算する。雲レジーム判定と三役好転の定量化。

    Returns:
        {"regime": str, "sannyaku": bool, "signal": str,
         "tenkan": float, "kijun": float, "cloud_top": float, "cloud_bottom": float}
    """
    if len(close) < 52:
        return {
            "regime": "データ不足",
            "sannyaku": False,
            "signal": "中立",
            "tenkan": 0.0,
            "kijun": 0.0,
            "cloud_top": 0.0,
            "cloud_bottom": 0.0,
        }

    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high.rolling(52).max() + low.rolling(52).min()) / 2

    current_price = close.iloc[-1]
    tenkan_val = float(tenkan.iloc[-1])
    kijun_val = float(kijun.iloc[-1])
    cloud_top = float(max(senkou_a.iloc[-1], senkou_b.iloc[-1]))
    cloud_bottom = float(min(senkou_a.iloc[-1], senkou_b.iloc[-1]))

    if current_price > cloud_top:
        regime = "above_cloud"
    elif current_price < cloud_bottom:
        regime = "below_cloud"
    else:
        regime = "in_cloud"

    cond1 = tenkan_val > kijun_val
    cond2 = current_price > close.iloc[-26] if len(close) >= 26 else False
    cond3 = regime == "above_cloud"
    sannyaku = cond1 and cond2 and cond3

    if sannyaku:
        signal = "強気"
    elif regime == "below_cloud" and not cond1:
        signal = "弱気"
    else:
        signal = "中立"

    return {
        "regime": regime,
        "sannyaku": sannyaku,
        "signal": signal,
        "tenkan": tenkan_val,
        "kijun": kijun_val,
        "cloud_top": cloud_top,
        "cloud_bottom": cloud_bottom,
    }


def calculate_bb_squeeze(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    bb_period: int = 20,
    bb_std: float = 2.0,
    atr_period: int = 20,
    kc_mult: float = 1.5,
) -> dict:
    """
    BBスクイズ検出（ケルトナーチャネル比較方式）。

    Returns:
        {"squeeze": bool, "signal": str, "bandwidth_percentile": float}
    """
    if len(close) < max(bb_period, atr_period) + 20:
        return {"squeeze": False, "signal": "データ不足", "bandwidth_percentile": 50.0}

    bb_ma = close.rolling(bb_period).mean()
    bb_std_val = close.rolling(bb_period).std()
    bb_upper = bb_ma + bb_std * bb_std_val
    bb_lower = bb_ma - bb_std * bb_std_val

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    kc_ma = close.rolling(atr_period).mean()
    kc_upper = kc_ma + kc_mult * atr
    kc_lower = kc_ma - kc_mult * atr

    squeeze = bool(
        bb_upper.iloc[-1] < kc_upper.iloc[-1] and bb_lower.iloc[-1] > kc_lower.iloc[-1]
    )

    bandwidth = (bb_upper - bb_lower) / bb_ma * 100
    bw_series = bandwidth.dropna().tail(120)
    if len(bw_series) > 0:
        percentile = float(
            (bw_series < bandwidth.iloc[-1]).sum() / len(bw_series) * 100
        )
    else:
        percentile = 50.0

    current_price = close.iloc[-1]
    if squeeze:
        signal = "squeeze"
    elif percentile < 10 and current_price > bb_upper.iloc[-1]:
        signal = "expansion_breakout"
    elif percentile > 80:
        signal = "expansion"
    else:
        signal = "normal"

    return {"squeeze": squeeze, "signal": signal, "bandwidth_percentile": percentile}


def calculate_dynamic_rsi(close: pd.Series, period: int = 14) -> dict:
    """
    動的RSI（レジーム別閾値調整）。

    Returns:
        {"rsi": float, "regime": str, "signal": str,
         "oversold_threshold": int, "overbought_threshold": int}
    """
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_val = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50.0

    if len(close) >= 200:
        ma200 = close.rolling(200).mean().iloc[-1]
        is_bullish = close.iloc[-1] > ma200
    else:
        is_bullish = True

    if is_bullish:
        regime, oversold, overbought = "bullish_regime", 40, 80
    else:
        regime, oversold, overbought = "bearish_regime", 20, 60

    if rsi_val <= oversold:
        signal = "売られすぎ"
    elif rsi_val >= overbought:
        signal = "買われすぎ"
    else:
        signal = "中立"

    return {
        "rsi": rsi_val,
        "regime": regime,
        "signal": signal,
        "oversold_threshold": oversold,
        "overbought_threshold": overbought,
    }


def calculate_anchored_vwap(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
    anchor_type: str = "ytd",
) -> dict:
    """
    アンカーVWAP（Anchored VWAP）を計算する。

    Returns:
        {"avwap": float, "deviation_pct": float, "anchor_type": str}
    """
    if len(close) < 20 or volume.sum() == 0:
        return {"avwap": 0.0, "deviation_pct": 0.0, "anchor_type": anchor_type}

    typical_price = (high + low + close) / 3

    if anchor_type == "ytd":
        try:
            current_year = close.index[-1].year
            ytd_mask = close.index.year == current_year
            if ytd_mask.any():
                tp, vol = typical_price[ytd_mask], volume[ytd_mask]
            else:
                tp, vol = typical_price, volume
        except (AttributeError, TypeError):
            tp, vol = typical_price, volume
    elif anchor_type == "quarter":
        tp, vol = typical_price.tail(63), volume.tail(63)
    else:
        loc = close.index.get_loc(low.idxmin())
        tp, vol = typical_price.iloc[loc:], volume.iloc[loc:]

    avwap = (tp * vol).cumsum() / (vol.cumsum() + 1e-10)
    avwap_val = float(avwap.iloc[-1]) if len(avwap) > 0 else 0.0
    current_price = float(close.iloc[-1])

    deviation_pct = 0.0
    if avwap_val > 0:
        deviation_pct = (current_price - avwap_val) / avwap_val * 100

    return {
        "avwap": avwap_val,
        "deviation_pct": deviation_pct,
        "anchor_type": anchor_type,
    }
