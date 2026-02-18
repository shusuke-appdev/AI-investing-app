"""
テクニカル分析モジュール（オーケストレーション）

基本指標・拡張指標・高度指標モジュールを統合し、
包括的なテクニカル分析とスコアリングを実行します。
skills準拠のため、ロジックは細分化されたモジュールに委譲しています。
"""

from typing import Optional

import pandas as pd

from src.advisor.models import TechnicalScore
from src.advisor.technical_extended import (
    analyze_multi_timeframe,
    calculate_adx,
    calculate_fibonacci_levels,
    calculate_obv,
    calculate_stochastic_rsi,
    detect_divergence,
)
from src.advisor.technical_indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_contrarian_zone,
    calculate_ma_deviation,
    calculate_ma_trend,
    calculate_macd_signal,
    calculate_rsi,
    calculate_support_resistance,
)
from src.advisor.technical_patterns import (
    detect_candlestick_patterns,
    detect_peaks_valleys,
)
from src.advisor.technical_regimes import (
    calculate_anchored_vwap,
    calculate_bb_squeeze,
    calculate_dynamic_rsi,
    calculate_ichimoku,
)
from src.advisor.technical_scoring import (
    analyze_options_data,
    calc_flow_score,
    calc_momentum_score,
    calc_pattern_score,
    calc_trend_score,
)
from src.market_data import get_stock_data


def analyze_technical(ticker: str, period: str = "1y") -> Optional[TechnicalScore]:
    """銘柄の包括的テクニカル分析を実行します。"""
    df = get_stock_data(ticker, period)
    if df.empty or len(df) < 50:
        return None

    close, high, low = df["Close"], df["High"], df["Low"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series([0] * len(df))
    open_ = df["Open"] if "Open" in df.columns else close
    current_price = float(close.iloc[-1])

    # --- 指標計算 ---
    rsi = calculate_rsi(close)
    ma_dev = calculate_ma_deviation(close)
    ma_trend = calculate_ma_trend(close)
    macd_data = calculate_macd_signal(close)
    bb = calculate_bollinger_bands(close)
    atr_data = calculate_atr(high, low, close)
    sr = calculate_support_resistance(close)
    contrarian_zone = calculate_contrarian_zone(close, bb, atr_data["atr"])

    obv_data = calculate_obv(close, volume)
    adx_data = calculate_adx(high, low, close)
    stoch_data = calculate_stochastic_rsi(close)
    fib_data = calculate_fibonacci_levels(high, low)
    mtf_data = analyze_multi_timeframe(ticker)

    # ダイバージェンス
    div_rsi = detect_divergence(
        close,
        100
        - (
            100
            / (
                1
                + (
                    close.diff().where(close.diff() > 0, 0).rolling(14).mean()
                    / (
                        -close.diff().where(close.diff() < 0, 0).rolling(14).mean()
                        + 1e-10
                    )
                )
            )
        ),
    )
    div_macd = detect_divergence(
        close, close.ewm(span=12).mean() - close.ewm(span=26).mean()
    )

    # Phase 1-3 高度指標
    ichimoku = calculate_ichimoku(close, high, low)
    bb_sq = calculate_bb_squeeze(close, high, low)
    dyn_rsi = calculate_dynamic_rsi(close)
    avwap = calculate_anchored_vwap(close, high, low, volume, "ytd")
    peaks_valleys = detect_peaks_valleys(close, high, low)
    candlestick = detect_candlestick_patterns(
        open_, high, low, close, rsi, bb["position"]
    )

    # オプション分析 & スコアリング
    opt_data = analyze_options_data(ticker, current_price)

    trend_score = calc_trend_score(ma_trend, macd_data, ichimoku, adx_data["adx"])
    momentum_score = calc_momentum_score(dyn_rsi, stoch_data["stoch_rsi"], div_rsi)
    pattern_score = calc_pattern_score(bb_sq, bb, ma_dev, peaks_valleys, candlestick)
    flow_score = calc_flow_score(obv_data, opt_data["score_adj"])
    mtf_score = (
        1.0
        if mtf_data["alignment"] == "aligned_bullish"
        else -1.0
        if mtf_data["alignment"] == "aligned_bearish"
        else 0.0
    )

    # 重み付き集約 (Pattern 20%, Flow 20%)
    w_trend, w_mom, w_pat, w_flow, w_mtf = 0.30, 0.20, 0.20, 0.20, 0.10
    if opt_data["gex_regime"] == "positive_gamma":
        w_trend, w_mom, w_pat = 0.20, 0.30, 0.20
    elif opt_data["gex_regime"] == "negative_gamma":
        w_trend, w_mom, w_pat = 0.40, 0.10, 0.20

    weighted = (
        trend_score * w_trend
        + momentum_score * w_mom
        + pattern_score * w_pat
        + flow_score * w_flow
        + mtf_score * w_mtf
    )
    score = int(max(-100, min(100, weighted * 50)))

    # シグナル判定
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

    if current_price <= contrarian_zone[1]:
        c_sig = "買い検討ゾーン"
    elif rsi > 70 and bb["position"] == "上限突破":
        c_sig = "過熱警戒"
    else:
        c_sig = "様子見"

    ma_sig = "上方乖離" if ma_dev > 10 else "下方乖離" if ma_dev < -10 else "中立"
    rsi_sig = "売られすぎ" if rsi < 30 else "買われすぎ" if rsi > 70 else "中立"

    return TechnicalScore(
        rsi=rsi,
        rsi_signal=rsi_sig,
        ma_deviation=ma_dev,
        ma_signal=ma_sig,
        ma_trend=ma_trend,
        macd_signal=macd_data["signal"],
        bb_position=bb["position"],
        bb_width=bb["width"],
        atr=atr_data["atr"],
        atr_percent=atr_data["atr_percent"],
        support_price=sr["support"],
        resistance_price=sr["resistance"],
        overall_score=score,
        overall_signal=overall,
        contrarian_buy_zone=contrarian_zone,
        contrarian_signal=c_sig,
        obv_trend=obv_data["trend"],
        obv_divergence=obv_data["divergence"],
        adx=adx_data["adx"],
        adx_signal=adx_data["signal"],
        stoch_rsi=stoch_data["stoch_rsi"],
        stoch_rsi_signal=stoch_data["signal"],
        fib_levels=fib_data["levels"],
        fib_nearest_level=fib_data["nearest"],
        mtf_alignment=mtf_data["alignment"],
        mtf_details=mtf_data["details"],
        divergence_rsi=div_rsi,
        divergence_macd=div_macd,
        macd_hist_slope=macd_data["hist_slope"],
        macd_zero_filter=macd_data["zero_filter"],
        rsi_regime=dyn_rsi["regime"],
        rsi_dynamic_signal=dyn_rsi["signal"],
        bb_squeeze=bb_sq["squeeze"],
        bb_squeeze_signal=bb_sq["signal"],
        ichimoku_regime=ichimoku["regime"],
        ichimoku_sannyaku=ichimoku["sannyaku"],
        ichimoku_signal=ichimoku["signal"],
        avwap_ytd=avwap["avwap"],
        avwap_deviation=avwap["deviation_pct"],
        recent_peaks=peaks_valleys["peaks"],
        recent_valleys=peaks_valleys["valleys"],
        peak_valley_signal=peaks_valleys["signal"],
        candlestick_patterns=candlestick["patterns"],
        candlestick_summary=candlestick["summary"],
        gex_regime=opt_data["gex_regime"],
        gex_positive_wall=opt_data["gex_positive_wall"],
        gex_negative_wall=opt_data["gex_negative_wall"],
        pcr_ratio=opt_data["pcr_ratio"],
        pcr_signal=opt_data["pcr_signal"],
        atm_iv=opt_data["atm_iv"],
        max_pain=opt_data["max_pain"],
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
    """AI分析用のテクニカルサマリーを生成（Phase 1-3 + Option統合版）"""
    tech = analyze_technical(ticker)
    if not tech:
        return "テクニカルデータ取得失敗"

    cdl_str = (
        ", ".join(
            f"{p['name']}({'買' if p['signal'] > 0 else '売'})"
            for p in tech.candlestick_patterns
        )
        if tech.candlestick_patterns
        else "なし"
    )

    return f"""【{ticker} テクニカル分析】
- 総合: {tech.overall_score}点 ({tech.overall_signal}) | トレンド: {tech.ma_trend}
- RSI: {tech.rsi:.1f} ({tech.rsi_signal}) | 動的: {tech.rsi_dynamic_signal} ({tech.rsi_regime})
- MACD: {tech.macd_signal} (Hist: {tech.macd_hist_slope})
- 一目均衡表: {tech.ichimoku_signal} ({tech.ichimoku_regime})
- ボリンジャー: {tech.bb_position}, スクイズ: {tech.bb_squeeze_signal}
- 需給環境: GEX={tech.gex_regime}, PCR={tech.pcr_ratio:.2f}({tech.pcr_signal}), IV={tech.atm_iv:.1%}, MaxPain=${tech.max_pain:.0f}
- OBV: {tech.obv_trend} (Div: {tech.obv_divergence})
- パターン: 極値={tech.peak_valley_signal}, ローソク足={cdl_str}
- サポート/レジスタンス: ${tech.support_price:.2f} / ${tech.resistance_price:.2f}
- AVWAP(YTD): ${tech.avwap_ytd:.2f} (乖離 {tech.avwap_deviation:+.1f}%)
"""
