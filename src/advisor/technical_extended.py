"""
拡張テクニカル指標モジュール

OBV, ADX, Stochastic RSI, フィボナッチ, ダイバージェンス検出,
MTF分析の計算関数を提供します。
"""
import pandas as pd
import numpy as np
from typing import Optional
from src.market_data import get_stock_data


def calculate_obv(close: pd.Series, volume: pd.Series) -> dict:
    """
    OBV (On Balance Volume) を計算する。

    Returns:
        {"obv": pd.Series, "trend": str, "divergence": str}
    """
    obv = pd.Series(index=close.index, dtype=float)
    obv.iloc[0] = 0
    
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    obv_ma = obv.rolling(20).mean()
    if obv.iloc[-1] > obv_ma.iloc[-1] * 1.02:
        trend = "上昇"
    elif obv.iloc[-1] < obv_ma.iloc[-1] * 0.98:
        trend = "下降"
    else:
        trend = "横ばい"
    
    price_change = close.iloc[-1] - close.iloc[-20] if len(close) >= 20 else 0
    obv_change = obv.iloc[-1] - obv.iloc[-20] if len(obv) >= 20 else 0
    
    if price_change < 0 and obv_change > 0:
        divergence = "bullish"
    elif price_change > 0 and obv_change < 0:
        divergence = "bearish"
    else:
        divergence = "none"
    
    return {"obv": obv, "trend": trend, "divergence": divergence}


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> dict:
    """
    ADX (Average Directional Index) を計算する。

    Returns:
        {"adx": float, "plus_di": float, "minus_di": float, "signal": str}
    """
    tr = pd.concat([
        high - low, abs(high - close.shift(1)), abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(span=period, adjust=False).mean()
    
    adx_val = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0.0
    
    if adx_val >= 25:
        signal = "強トレンド"
    elif adx_val >= 15:
        signal = "弱トレンド"
    else:
        signal = "レンジ"
    
    return {
        "adx": adx_val,
        "plus_di": float(plus_di.iloc[-1]) if pd.notna(plus_di.iloc[-1]) else 0.0,
        "minus_di": float(minus_di.iloc[-1]) if pd.notna(minus_di.iloc[-1]) else 0.0,
        "signal": signal,
    }


def calculate_stochastic_rsi(
    close: pd.Series, rsi_period: int = 14, stoch_period: int = 14
) -> dict:
    """
    Stochastic RSI を計算する。

    Returns:
        {"stoch_rsi": float, "signal": str}
    """
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    stoch_rsi = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    
    stoch_val = float(stoch_rsi.iloc[-1]) if pd.notna(stoch_rsi.iloc[-1]) else 50.0
    
    if stoch_val >= 80:
        signal = "買われすぎ"
    elif stoch_val <= 20:
        signal = "売られすぎ"
    else:
        signal = "中立"
    
    return {"stoch_rsi": stoch_val, "signal": signal}


def calculate_fibonacci_levels(high: pd.Series, low: pd.Series) -> dict:
    """
    フィボナッチ・リトレースメントレベルを計算する。

    Returns:
        {"levels": dict, "nearest": str}
    """
    swing_high = float(high.max())
    swing_low = float(low.min())
    diff = swing_high - swing_low
    
    fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = {ratio: swing_low + diff * (1 - ratio) for ratio in fib_ratios}
    
    current_price = float(high.iloc[-1])
    nearest_ratio = min(fib_ratios, key=lambda r: abs(levels[r] - current_price))
    
    return {"levels": levels, "nearest": f"{nearest_ratio*100:.1f}%"}


def detect_divergence(
    close: pd.Series, indicator: pd.Series, lookback: int = 20
) -> str:
    """
    価格と指標の間のダイバージェンスを検出する。

    Returns:
        "bullish" | "bearish" | "none"
    """
    if len(close) < lookback or len(indicator) < lookback:
        return "none"
    
    price_rising = close.iloc[-1] > close.iloc[-lookback]
    ind_rising = indicator.iloc[-1] > indicator.iloc[-lookback]
    
    if not price_rising and ind_rising:
        return "bullish"
    if price_rising and not ind_rising:
        return "bearish"
    return "none"


def analyze_multi_timeframe(ticker: str) -> dict:
    """
    複数タイムフレームでの分析を実行する。

    Returns:
        {"alignment": str, "details": dict}
    """
    timeframes = {"daily": "1mo", "weekly": "3mo", "monthly": "1y"}
    signals: dict[str, str] = {}
    
    for tf_name, period in timeframes.items():
        try:
            df = get_stock_data(ticker, period)
            if df.empty or len(df) < 20:
                signals[tf_name] = "データ不足"
                continue
            
            close = df["Close"]
            ma20 = close.rolling(20).mean().iloc[-1]
            current = close.iloc[-1]
            
            if current > ma20 * 1.02:
                signals[tf_name] = "強気"
            elif current < ma20 * 0.98:
                signals[tf_name] = "弱気"
            else:
                signals[tf_name] = "中立"
        except Exception:
            signals[tf_name] = "エラー"
    
    bullish_count = sum(1 for s in signals.values() if s == "強気")
    bearish_count = sum(1 for s in signals.values() if s == "弱気")
    
    if bullish_count >= 2:
        alignment = "aligned_bullish"
    elif bearish_count >= 2:
        alignment = "aligned_bearish"
    else:
        alignment = "mixed"
    
    return {"alignment": alignment, "details": signals}
