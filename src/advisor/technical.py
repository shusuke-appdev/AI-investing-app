"""
テクニカル分析モジュール（拡張版）
RSI, MACD, ボリンジャーバンド, ATR, サポート/レジスタンス等を計算します。
"""
import pandas as pd
import numpy as np
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
    return float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else 50.0


def calculate_ma_deviation(close_prices: pd.Series, period: int = 50) -> float:
    """移動平均乖離率を計算"""
    ma = close_prices.rolling(window=period).mean()
    if ma.iloc[-1] == 0 or pd.isna(ma.iloc[-1]):
        return 0.0
    deviation = (close_prices.iloc[-1] - ma.iloc[-1]) / ma.iloc[-1] * 100
    return float(deviation)


def calculate_ma_trend(close_prices: pd.Series) -> str:
    """移動平均トレンドを判定（20/50/200日）"""
    if len(close_prices) < 200:
        return "データ不足"
    
    ma20 = close_prices.rolling(20).mean().iloc[-1]
    ma50 = close_prices.rolling(50).mean().iloc[-1]
    ma200 = close_prices.rolling(200).mean().iloc[-1]
    
    if ma20 > ma50 > ma200:
        return "上昇トレンド"
    elif ma20 < ma50 < ma200:
        return "下降トレンド"
    else:
        return "横ばい"


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


def calculate_bollinger_bands(close_prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    """ボリンジャーバンドを計算"""
    ma = close_prices.rolling(window=period).mean()
    std = close_prices.rolling(window=period).std()
    
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    
    current_price = close_prices.iloc[-1]
    upper_val = upper.iloc[-1]
    lower_val = lower.iloc[-1]
    ma_val = ma.iloc[-1]
    
    # バンド幅（ボラティリティ指標）
    width = ((upper_val - lower_val) / ma_val * 100) if ma_val > 0 else 0
    
    # 位置判定
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
        "position": position
    }


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> dict:
    """ATR（Average True Range）を計算"""
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    atr_val = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else 0.0
    current_price = close.iloc[-1]
    atr_percent = (atr_val / current_price * 100) if current_price > 0 else 0.0
    
    return {
        "atr": atr_val,
        "atr_percent": atr_percent
    }


def calculate_support_resistance(close_prices: pd.Series, window: int = 20) -> dict:
    """直近のサポート/レジスタンスを計算"""
    recent = close_prices.tail(window)
    
    support = float(recent.min())
    resistance = float(recent.max())
    
    return {
        "support": support,
        "resistance": resistance
    }


def calculate_contrarian_zone(close_prices: pd.Series, bb: dict, atr: float) -> tuple:
    """逆張り買いゾーンを計算"""
    current_price = close_prices.iloc[-1]
    
    # ボリンジャー下限とATRを考慮した逆張りゾーン
    zone_upper = bb["lower"]  # ボリンジャー下限
    zone_lower = zone_upper - atr  # さらにATR分下
    
    return (float(zone_lower), float(zone_upper))


def analyze_technical(ticker: str, period: str = "1y") -> Optional[TechnicalScore]:
    """
    銘柄の包括的テクニカル分析を実行します。
    
    Args:
        ticker: 銘柄コード
        period: 分析期間（デフォルト1年）
    
    Returns:
        TechnicalScore または None
    """
    df = get_stock_data(ticker, period)
    if df.empty or len(df) < 50:
        return None
    
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    current_price = float(close.iloc[-1])
    
    # === 各指標の計算 ===
    
    # RSI
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
    
    # MAトレンド
    ma_trend = calculate_ma_trend(close)
    
    # MACD
    macd_signal = calculate_macd_signal(close)
    
    # ボリンジャーバンド
    bb = calculate_bollinger_bands(close)
    
    # ATR
    atr_data = calculate_atr(high, low, close)
    
    # サポート/レジスタンス
    sr = calculate_support_resistance(close)
    
    # 逆張りゾーン
    contrarian_zone = calculate_contrarian_zone(close, bb, atr_data["atr"])
    
    # === 総合スコア計算 (-100 to 100) ===
    score = 0
    
    # RSIスコア（売られすぎ=買いシグナル）
    if rsi < 30:
        score += 25
    elif rsi < 40:
        score += 10
    elif rsi > 70:
        score -= 25
    elif rsi > 60:
        score -= 10
    
    # MA乖離スコア（下方乖離=買いシグナル）
    if ma_dev < -15:
        score += 20
    elif ma_dev < -5:
        score += 10
    elif ma_dev > 15:
        score -= 20
    elif ma_dev > 5:
        score -= 10
    
    # MACDスコア
    if macd_signal == "強気":
        score += 15
    elif macd_signal == "弱気":
        score -= 15
    
    # ボリンジャースコア（下限=買いシグナル）
    if bb["position"] == "下限突破":
        score += 20
    elif bb["position"] == "下半分":
        score += 5
    elif bb["position"] == "上限突破":
        score -= 20
    elif bb["position"] == "上半分":
        score -= 5
    
    # トレンドスコア
    if ma_trend == "上昇トレンド":
        score += 10
    elif ma_trend == "下降トレンド":
        score -= 10
    
    score = max(-100, min(100, score))
    
    # 総合シグナル
    if score > 30:
        overall = "強気"
    elif score > 10:
        overall = "やや強気"
    elif score < -30:
        overall = "弱気"
    elif score < -10:
        overall = "やや弱気"
    else:
        overall = "中立"
    
    # 逆張りシグナル
    if current_price <= contrarian_zone[1]:
        contrarian_signal = "買い検討ゾーン"
    elif rsi > 70 and bb["position"] == "上限突破":
        contrarian_signal = "過熱警戒"
    else:
        contrarian_signal = "様子見"
    
    return TechnicalScore(
        rsi=rsi,
        rsi_signal=rsi_signal,
        ma_deviation=ma_dev,
        ma_signal=ma_signal,
        ma_trend=ma_trend,
        macd_signal=macd_signal,
        bb_position=bb["position"],
        bb_width=bb["width"],
        atr=atr_data["atr"],
        atr_percent=atr_data["atr_percent"],
        support_price=sr["support"],
        resistance_price=sr["resistance"],
        overall_score=score,
        overall_signal=overall,
        contrarian_buy_zone=contrarian_zone,
        contrarian_signal=contrarian_signal
    )


def analyze_market_technicals() -> dict:
    """主要指数のテクニカル分析を実行します"""
    indices = ["SPY", "QQQ", "IWM"]
    results = {}
    
    for ticker in indices:
        tech = analyze_technical(ticker, "6mo")
        if tech:
            results[ticker] = {
                "rsi": tech.rsi,
                "signal": tech.overall_signal,
                "score": tech.overall_score,
                "macd": tech.macd_signal,
                "trend": tech.ma_trend,
            }
    
    return results


def get_technical_summary_for_ai(ticker: str) -> str:
    """AI分析用のテクニカルサマリーを生成"""
    tech = analyze_technical(ticker)
    if not tech:
        return "テクニカルデータ取得失敗"
    
    summary = f"""【{ticker} テクニカル分析】
- RSI: {tech.rsi:.1f} ({tech.rsi_signal})
- 50日MA乖離: {tech.ma_deviation:+.1f}% ({tech.ma_signal})
- トレンド: {tech.ma_trend}
- MACD: {tech.macd_signal}
- ボリンジャー: {tech.bb_position} (幅: {tech.bb_width:.1f}%)
- サポート: ${tech.support_price:.2f} / レジスタンス: ${tech.resistance_price:.2f}
- 逆張り買いゾーン: ${tech.contrarian_buy_zone[0]:.2f} - ${tech.contrarian_buy_zone[1]:.2f}
- 総合スコア: {tech.overall_score} ({tech.overall_signal})
- 逆張りシグナル: {tech.contrarian_signal}"""
    
    return summary
