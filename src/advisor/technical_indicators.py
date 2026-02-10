"""
基本テクニカル指標モジュール

RSI, MA乖離率, MAトレンド, MACD, ボリンジャーバンド, ATR,
サポート/レジスタンス, 逆張りゾーンの計算関数を提供します。
"""
import pandas as pd
import numpy as np
from typing import Optional


def calculate_rsi(close_prices: pd.Series, period: int = 14) -> float:
    """RSIを計算する。"""
    delta = close_prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else 50.0


def calculate_ma_deviation(close_prices: pd.Series, period: int = 50) -> float:
    """移動平均乖離率(%)を計算する。"""
    ma = close_prices.rolling(window=period).mean()
    if ma.iloc[-1] == 0 or pd.isna(ma.iloc[-1]):
        return 0.0
    deviation = (close_prices.iloc[-1] - ma.iloc[-1]) / ma.iloc[-1] * 100
    return float(deviation)


def calculate_ma_trend(close_prices: pd.Series) -> str:
    """移動平均トレンドを判定（20/50/200日）。"""
    if len(close_prices) < 200:
        return "データ不足"
    
    ma20 = close_prices.rolling(20).mean().iloc[-1]
    ma50 = close_prices.rolling(50).mean().iloc[-1]
    ma200 = close_prices.rolling(200).mean().iloc[-1]
    
    if ma20 > ma50 > ma200:
        return "上昇トレンド"
    elif ma20 < ma50 < ma200:
        return "下降トレンド"
    return "横ばい"


def calculate_macd_signal(close_prices: pd.Series) -> dict:
    """
    MACD高度化シグナルを判定する。

    ヒストグラムの傾き（1階微分）によるボトムアウト/トッピング検出と、
    ゼロラインフィルター（MACDライン > 0 でのGCのみ有効）を含む。

    Returns:
        {"signal": str, "hist_slope": str, "zero_filter": str}
    """
    exp12 = close_prices.ewm(span=12, adjust=False).mean()
    exp26 = close_prices.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal_line

    if macd.iloc[-1] > signal_line.iloc[-1]:
        basic_signal = "強気"
    elif macd.iloc[-1] < signal_line.iloc[-1]:
        basic_signal = "弱気"
    else:
        basic_signal = "中立"

    hist_slope = "neutral"
    if len(histogram) >= 3:
        h0, h1, h2 = histogram.iloc[-1], histogram.iloc[-2], histogram.iloc[-3]
        if h0 > h1 and h1 < h2:
            hist_slope = "bottoming"
        elif h0 < h1 and h1 > h2:
            hist_slope = "topping"
        elif h0 > h1:
            hist_slope = "rising"
        else:
            hist_slope = "falling"

    zero_filter = "above_zero" if macd.iloc[-1] > 0 else "below_zero"

    return {"signal": basic_signal, "hist_slope": hist_slope, "zero_filter": zero_filter}


def calculate_bollinger_bands(
    close_prices: pd.Series, period: int = 20, std_dev: float = 2.0
) -> dict:
    """ボリンジャーバンドを計算する。"""
    ma = close_prices.rolling(window=period).mean()
    std = close_prices.rolling(window=period).std()
    
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    
    current_price = close_prices.iloc[-1]
    upper_val = upper.iloc[-1]
    lower_val = lower.iloc[-1]
    ma_val = ma.iloc[-1]
    
    width = ((upper_val - lower_val) / ma_val * 100) if ma_val > 0 else 0

    if current_price > upper_val:
        position = "上限突破"
    elif current_price < lower_val:
        position = "下限突破"
    elif current_price > ma_val:
        position = "上半分"
    else:
        position = "下半分"
    
    return {
        "upper": float(upper_val),
        "lower": float(lower_val),
        "middle": float(ma_val),
        "width": float(width),
        "position": position,
    }


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> dict:
    """ATR（Average True Range）を計算する。"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low, abs(high - prev_close), abs(low - prev_close)
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    atr_val = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else 0.0
    current_price = close.iloc[-1]
    atr_percent = (atr_val / current_price * 100) if current_price > 0 else 0.0
    
    return {"atr": atr_val, "atr_percent": atr_percent}


def calculate_support_resistance(close_prices: pd.Series, window: int = 20) -> dict:
    """直近のサポート/レジスタンスを計算する。"""
    recent = close_prices.tail(window)
    return {"support": float(recent.min()), "resistance": float(recent.max())}


def calculate_contrarian_zone(close_prices: pd.Series, bb: dict, atr: float) -> tuple:
    """逆張り買いゾーンを計算する。"""
    zone_upper = bb["lower"]
    zone_lower = zone_upper - atr
    return (float(zone_lower), float(zone_upper))
