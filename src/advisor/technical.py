import pandas as pd
from typing import Optional
from src.market_data import get_stock_data
from .models import TechnicalScore

def calculate_rsi(close_prices: pd.Series, period: int = 14) -> float:
    """RSIを計算"""
    delta = close_prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50.0


def calculate_ma_deviation(close_prices: pd.Series, period: int = 50) -> float:
    """移動平均乖離率を計算"""
    ma = close_prices.rolling(window=period).mean()
    if ma.iloc[-1] == 0:
        return 0.0
    deviation = (close_prices.iloc[-1] - ma.iloc[-1]) / ma.iloc[-1] * 100
    return deviation


def calculate_macd_signal(close_prices: pd.Series) -> str:
    """MACDシグナルを判定"""
    exp12 = close_prices.ewm(span=12, adjust=False).mean()
    exp26 = close_prices.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    if macd.iloc[-1] > signal.iloc[-1]:
        return "強気"
    elif macd.iloc[-1] < signal.iloc[-1]:
        return "弱気"
    return "中立"


def analyze_technical(ticker: str, period: str = "6mo") -> Optional[TechnicalScore]:
    """
    銘柄のテクニカル分析スコアを計算します。
    """
    df = get_stock_data(ticker, period)
    if df.empty:
        return None
    
    close = df["Close"]
    
    # RSI計算
    rsi = calculate_rsi(close)
    if rsi < 30:
        rsi_signal = "売られすぎ"
    elif rsi > 70:
        rsi_signal = "買われすぎ"
    else:
        rsi_signal = "中立"
    
    # MA乖離
    ma_dev = calculate_ma_deviation(close)
    if ma_dev > 10:
        ma_signal = "上方乖離"
    elif ma_dev < -10:
        ma_signal = "下方乖離"
    else:
        ma_signal = "中立"
    
    # MACD
    macd_signal = calculate_macd_signal(close)
    
    # 総合スコア計算 (-100 to 100)
    score = 0
    
    # RSIスコア
    if rsi < 30:
        score += 30
    elif rsi > 70:
        score -= 30
    
    # MA乖離スコア
    score -= int(ma_dev * 2)
    score = max(-100, min(100, score))
    
    # MACDスコア
    if macd_signal == "強気":
        score += 20
    elif macd_signal == "弱気":
        score -= 20
    
    score = max(-100, min(100, score))
    
    # 総合シグナル
    if score > 20:
        overall = "強気"
    elif score < -20:
        overall = "弱気"
    else:
        overall = "中立"
    
    return TechnicalScore(
        rsi=rsi,
        rsi_signal=rsi_signal,
        ma_deviation=ma_dev,
        ma_signal=ma_signal,
        macd_signal=macd_signal,
        overall_score=score,
        overall_signal=overall
    )


def analyze_market_technicals() -> dict:
    """主要指数のテクニカル分析を実行します"""
    indices = ["SPY", "QQQ", "IWM"]
    results = {}
    
    for ticker in indices:
        tech = analyze_technical(ticker, "3mo")
        if tech:
            results[ticker] = {
                "rsi": tech.rsi,
                "signal": tech.overall_signal,
                "score": tech.overall_score,
                "macd": tech.macd_signal,
            }
    
    return results
