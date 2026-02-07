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


# === 拡張テクニカル指標 ===

def calculate_obv(close: pd.Series, volume: pd.Series) -> dict:
    """
    OBV (On Balance Volume) を計算
    
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
    
    # OBVのトレンド判定（20日MA比較）
    obv_ma = obv.rolling(20).mean()
    if obv.iloc[-1] > obv_ma.iloc[-1] * 1.02:
        trend = "上昇"
    elif obv.iloc[-1] < obv_ma.iloc[-1] * 0.98:
        trend = "下降"
    else:
        trend = "横ばい"
    
    # ダイバージェンス検出（価格とOBVの方向性比較）
    price_change = close.iloc[-1] - close.iloc[-20] if len(close) >= 20 else 0
    obv_change = obv.iloc[-1] - obv.iloc[-20] if len(obv) >= 20 else 0
    
    if price_change < 0 and obv_change > 0:
        divergence = "bullish"
    elif price_change > 0 and obv_change < 0:
        divergence = "bearish"
    else:
        divergence = "none"
    
    return {"obv": obv, "trend": trend, "divergence": divergence}


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> dict:
    """
    ADX (Average Directional Index) を計算
    
    Returns:
        {"adx": float, "plus_di": float, "minus_di": float, "signal": str}
    """
    # True Range
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    
    # +DM, -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # Smoothed values
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    # DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(span=period, adjust=False).mean()
    
    adx_val = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0.0
    
    # シグナル判定
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
        "signal": signal
    }


def calculate_stochastic_rsi(close: pd.Series, rsi_period: int = 14, stoch_period: int = 14) -> dict:
    """
    Stochastic RSI を計算
    
    Returns:
        {"stoch_rsi": float, "signal": str}
    """
    # RSIを計算
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    # RSIのStochasticを計算
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    stoch_rsi = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    
    stoch_val = float(stoch_rsi.iloc[-1]) if pd.notna(stoch_rsi.iloc[-1]) else 50.0
    
    # シグナル判定
    if stoch_val >= 80:
        signal = "買われすぎ"
    elif stoch_val <= 20:
        signal = "売られすぎ"
    else:
        signal = "中立"
    
    return {"stoch_rsi": stoch_val, "signal": signal}


def calculate_fibonacci_levels(high: pd.Series, low: pd.Series) -> dict:
    """
    フィボナッチ・リトレースメントレベルを計算
    
    Returns:
        {"levels": dict, "nearest": str}
    """
    # 直近の高値・安値を使用
    swing_high = float(high.max())
    swing_low = float(low.min())
    diff = swing_high - swing_low
    
    fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = {ratio: swing_low + diff * (1 - ratio) for ratio in fib_ratios}
    
    # 現在価格に最も近いレベルを特定
    current_price = float(high.iloc[-1])
    nearest_ratio = min(fib_ratios, key=lambda r: abs(levels[r] - current_price))
    nearest = f"{nearest_ratio*100:.1f}%"
    
    return {"levels": levels, "nearest": nearest}


def detect_divergence(close: pd.Series, indicator: pd.Series, lookback: int = 20) -> str:
    """
    価格と指標の間のダイバージェンスを検出
    
    Returns:
        "bullish" | "bearish" | "none"
    """
    if len(close) < lookback or len(indicator) < lookback:
        return "none"
    
    # 直近の期間での価格と指標の変化
    price_start = close.iloc[-lookback]
    price_end = close.iloc[-1]
    ind_start = indicator.iloc[-lookback]
    ind_end = indicator.iloc[-1]
    
    price_rising = price_end > price_start
    ind_rising = ind_end > ind_start
    
    if not price_rising and ind_rising:
        return "bullish"  # 価格下落、指標上昇 → 反転の可能性
    elif price_rising and not ind_rising:
        return "bearish"  # 価格上昇、指標下落 → 反転の可能性
    
    return "none"


def analyze_multi_timeframe(ticker: str) -> dict:
    """
    複数タイムフレームでの分析を実行
    
    Returns:
        {"alignment": str, "details": dict}
    """
    timeframes = {
        "daily": "1mo",
        "weekly": "3mo",
        "monthly": "1y"
    }
    
    signals = {}
    
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
    
    # アラインメント判定
    bullish_count = sum(1 for s in signals.values() if s == "強気")
    bearish_count = sum(1 for s in signals.values() if s == "弱気")
    
    if bullish_count >= 2:
        alignment = "aligned_bullish"
    elif bearish_count >= 2:
        alignment = "aligned_bearish"
    else:
        alignment = "mixed"
    
    return {"alignment": alignment, "details": signals}


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
    volume = df["Volume"] if "Volume" in df.columns else pd.Series([0] * len(df))
    current_price = float(close.iloc[-1])
    
    # === 既存指標の計算 ===
    
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
    
    # === 拡張指標の計算 ===
    
    # OBV
    obv_data = calculate_obv(close, volume)
    obv_trend = obv_data["trend"]
    obv_divergence = obv_data["divergence"]
    
    # ADX
    adx_data = calculate_adx(high, low, close)
    adx = adx_data["adx"]
    adx_signal = adx_data["signal"]
    
    # Stochastic RSI
    stoch_data = calculate_stochastic_rsi(close)
    stoch_rsi = stoch_data["stoch_rsi"]
    stoch_rsi_signal = stoch_data["signal"]
    
    # フィボナッチ
    fib_data = calculate_fibonacci_levels(high, low)
    fib_levels = fib_data["levels"]
    fib_nearest = fib_data["nearest"]
    
    # MTF分析
    mtf_data = analyze_multi_timeframe(ticker)
    mtf_alignment = mtf_data["alignment"]
    mtf_details = mtf_data["details"]
    
    # ダイバージェンス検出（RSI）
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    rsi_series = 100 - (100 / (1 + rs))
    divergence_rsi = detect_divergence(close, rsi_series)
    
    # ダイバージェンス検出（MACD）
    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp12 - exp26
    divergence_macd = detect_divergence(close, macd_line)
    
    # === 総合スコア計算 (-100 to 100) ===
    score = 0
    
    # RSIスコア（売られすぎ=買いシグナル）
    if rsi < 30:
        score += 20
    elif rsi < 40:
        score += 8
    elif rsi > 70:
        score -= 20
    elif rsi > 60:
        score -= 8
    
    # MA乖離スコア（下方乖離=買いシグナル）
    if ma_dev < -15:
        score += 15
    elif ma_dev < -5:
        score += 8
    elif ma_dev > 15:
        score -= 15
    elif ma_dev > 5:
        score -= 8
    
    # MACDスコア
    if macd_signal == "強気":
        score += 12
    elif macd_signal == "弱気":
        score -= 12
    
    # ボリンジャースコア（下限=買いシグナル）
    if bb["position"] == "下限突破":
        score += 15
    elif bb["position"] == "下半分":
        score += 4
    elif bb["position"] == "上限突破":
        score -= 15
    elif bb["position"] == "上半分":
        score -= 4
    
    # トレンドスコア
    if ma_trend == "上昇トレンド":
        score += 8
    elif ma_trend == "下降トレンド":
        score -= 8
    
    # === 拡張指標によるスコア調整 ===
    
    # ADXスコア（トレンド方向と強度）
    if adx >= 25:
        if macd_signal == "強気":
            score += 10  # 強いトレンド + 強気
        elif macd_signal == "弱気":
            score -= 10  # 強いトレンド + 弱気
    
    # Stochastic RSI スコア
    if stoch_rsi <= 20:
        score += 8  # 売られすぎ
    elif stoch_rsi >= 80:
        score -= 8  # 買われすぎ
    
    # OBVダイバージェンススコア
    if obv_divergence == "bullish":
        score += 10  # 強気ダイバージェンス
    elif obv_divergence == "bearish":
        score -= 10  # 弱気ダイバージェンス
    
    # RSIダイバージェンススコア
    if divergence_rsi == "bullish":
        score += 8
    elif divergence_rsi == "bearish":
        score -= 8
    
    # MTF整合性スコア
    if mtf_alignment == "aligned_bullish":
        score += 10
    elif mtf_alignment == "aligned_bearish":
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
        contrarian_signal=contrarian_signal,
        # 拡張指標
        obv_trend=obv_trend,
        obv_divergence=obv_divergence,
        adx=adx,
        adx_signal=adx_signal,
        stoch_rsi=stoch_rsi,
        stoch_rsi_signal=stoch_rsi_signal,
        fib_levels=fib_levels,
        fib_nearest_level=fib_nearest,
        mtf_alignment=mtf_alignment,
        mtf_details=mtf_details,
        divergence_rsi=divergence_rsi,
        divergence_macd=divergence_macd
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
    
    # 基本指標
    summary = f"""【{ticker} テクニカル分析】
- RSI: {tech.rsi:.1f} ({tech.rsi_signal})
- 50日MA乖離: {tech.ma_deviation:+.1f}% ({tech.ma_signal})
- トレンド: {tech.ma_trend}
- MACD: {tech.macd_signal}
- ボリンジャー: {tech.bb_position} (幅: {tech.bb_width:.1f}%)
- サポート: ${tech.support_price:.2f} / レジスタンス: ${tech.resistance_price:.2f}
- 逆張り買いゾーン: ${tech.contrarian_buy_zone[0]:.2f} - ${tech.contrarian_buy_zone[1]:.2f}
- 総合スコア: {tech.overall_score} ({tech.overall_signal})
- 逆張りシグナル: {tech.contrarian_signal}

【拡張指標】
- OBV: {tech.obv_trend} (ダイバージェンス: {tech.obv_divergence})
- ADX: {tech.adx:.1f} ({tech.adx_signal})
- Stochastic RSI: {tech.stoch_rsi:.1f} ({tech.stoch_rsi_signal})
- MTF整合性: {tech.mtf_alignment}
- RSIダイバージェンス: {tech.divergence_rsi}
- MACDダイバージェンス: {tech.divergence_macd}
- フィボナッチ最寄り: {tech.fib_nearest_level}"""
    
    return summary

