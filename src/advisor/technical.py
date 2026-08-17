"""
テクニカル分析モジュール（オーケストレーション）

基本指標・拡張指標・高度指標モジュールを統合し、
包括的なテクニカル分析とスコアリングを実行します。
skills準拠のため、ロジックは細分化されたモジュールに委譲しています。
"""

import pandas as pd

from src.advisor.base_recognition import detect_bases
from src.advisor.mean_reversion import MeanReversionAnalyzer
from src.advisor.minervini_analyzer import analyze_stage, detect_vcp
from src.advisor.mode_selector import determine_analysis_mode
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
    detect_advanced_patterns,
    detect_candlestick_patterns,
    detect_peaks_valleys,
    detect_pinbar,
    detect_volume_climax_vs_bleed,
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
from src.services.technical_strategy_service import build_technical_strategy_context
from src.stock_data_provider import is_japanese_stock

# スコアリングの重み付け定数
SCORE_WEIGHTS_DEFAULT = {
    "trend": 0.30,
    "mom": 0.20,
    "pat": 0.20,
    "flow": 0.20,
    "mtf": 0.10,
}
SCORE_WEIGHTS_POS_GAMMA = {
    "trend": 0.20,
    "mom": 0.30,
    "pat": 0.20,
    "flow": 0.20,
    "mtf": 0.10,
}
SCORE_WEIGHTS_NEG_GAMMA = {
    "trend": 0.40,
    "mom": 0.10,
    "pat": 0.20,
    "flow": 0.20,
    "mtf": 0.10,
}


def calculate_long_term_ma(close: pd.Series) -> dict:
    """長期MA(250, 500, 750日)を計算し、乖離率とシグナルを判定する。"""
    res = {
        "ma_250": None,
        "ma_500": None,
        "ma_750": None,
        "signal": "neutral",
        "description": "長期MA乖離なし",
    }
    if len(close) < 250:
        return {"signal": "neutral", "description": "データ不足（長期MA計算不可）"}

    latest = close.iloc[-1]

    ma250 = close.rolling(250).mean().iloc[-1]
    res["ma_250"] = ma250
    dev250 = (latest - ma250) / ma250 if ma250 else 0

    deviations = [dev250]
    if len(close) >= 500:
        ma500 = close.rolling(500).mean().iloc[-1]
        res["ma_500"] = ma500
        dev500 = (latest - ma500) / ma500 if ma500 else 0
        deviations.append(dev500)

    if len(close) >= 750:
        ma750 = close.rolling(750).mean().iloc[-1]
        res["ma_750"] = ma750
        dev750 = (latest - ma750) / ma750 if ma750 else 0
        deviations.append(dev750)

    # 判定：いずれかの長期MAから極端に下方に乖離しているか、または長期MA付近（サポート）にいるか
    if any(deviation < -0.3 for deviation in deviations):
        res["signal"] = "deep_discount"
        res["description"] = "長期移動平均から30%以上下方に乖離。歴史的売られすぎ水準。"
    elif any(abs(deviation) < 0.03 for deviation in deviations):
        res["signal"] = "near_support"
        res["description"] = "長期MA（1-3年）の強力なサポート水準に接近。"

    return res


def analyze_technical(
    ticker: str,
    period: str = "5y",
    price_df: pd.DataFrame | None = None,
) -> TechnicalScore | None:
    """銘柄の包括的テクニカル分析を実行します。"""
    df = price_df if price_df is not None else get_stock_data(ticker, period)
    if df.empty or len(df) < 50:
        return None

    close, high, low = df["Close"], df["High"], df["Low"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series([0] * len(df))
    open_ = df["Open"] if "Open" in df.columns else close
    current_price = float(close.iloc[-1])

    # --- 指標計算 ---
    rsi = calculate_rsi(close)
    ma_dev = calculate_ma_deviation(close, period=50)  # ここは既存のまま
    ma_trend = calculate_ma_trend(close)

    # 新規追加の移動平均線計算 (10, 20, 50, 200)
    ma_10 = float(close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else None
    ma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    macd_data = calculate_macd_signal(close)
    bb = calculate_bollinger_bands(close)
    atr_data = calculate_atr(high, low, close)
    sr = calculate_support_resistance(close)
    contrarian_zone = calculate_contrarian_zone(close, bb, atr_data["atr"])

    obv_data = calculate_obv(close, volume)
    adx_data = calculate_adx(high, low, close)
    stoch_data = calculate_stochastic_rsi(close)
    fib_data = calculate_fibonacci_levels(high, low)
    mtf_data = analyze_multi_timeframe(ticker, df)

    # ダイバージェンス
    _gain = close.diff().where(close.diff() > 0, 0).rolling(14).mean()
    _loss = (
        (-close.diff().where(close.diff() < 0, 0)).rolling(14).mean().clip(lower=1e-10)
    )
    _rsi_series = 100 - (100 / (1 + _gain / _loss))
    div_rsi = detect_divergence(close, _rsi_series)
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

    # Minervini分析
    stage_res = analyze_stage(df)
    is_vcp, vcp_res = detect_vcp(df)
    vcp_data_out = vcp_res if is_vcp and vcp_res else {"is_vcp": False}
    if is_vcp and vcp_res:
        vcp_data_out["is_vcp"] = True

    # Mean Reversion 分析
    mr_analyzer = MeanReversionAnalyzer(ticker)
    mr_data = mr_analyzer.analyze(df)
    strategy_context = build_technical_strategy_context(
        ticker,
        df,
        market_type="JP" if is_japanese_stock(ticker) else "US",
    )

    # 拡張下落判定 (Pinbar, Climax, Patterns, LongTerm MA)
    pinbar_data = detect_pinbar(open_, high, low, close)
    volume_data = detect_volume_climax_vs_bleed(close, volume)
    adv_patterns = detect_advanced_patterns(close, high, low)
    long_term_ma = calculate_long_term_ma(close)

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

    # モード判定とウェイト取得
    long_term_dev = (current_price - ma_200) / ma_200 if ma_200 and ma_200 > 0 else 0.0
    mode_info = determine_analysis_mode(close, stage_res["stage"], rsi, long_term_dev)
    analysis_mode = mode_info["mode"]
    weights = mode_info["weights"]

    # 重み付き集約
    weighted = (
        (trend_score / 2) * weights["trend"]
        + (momentum_score / 2) * weights["mom"]
        + (pattern_score / 2) * weights["pat"]
        + (flow_score / 2) * weights["flow"]
        + mtf_score * weights["mtf"]
    )

    # 0〜100に正規化（weightedが-1〜1の範囲を想定）
    raw_score = (weighted + 1) * 50
    score = int(max(0, min(100, raw_score)))

    # シグナル判定 (5段階評価)
    if score >= 80:
        overall = "Strong Buy"
    elif score >= 60:
        overall = "Buy"
    elif score >= 40:
        overall = "Hold"
    elif score >= 20:
        overall = "Sell"
    else:
        overall = "Strong Sell"

    # ベース認識
    base_data = detect_bases(df)

    # エントリー判定（ブレイク＋出来高）
    entry_signal = ""
    vol_ma50 = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else 0
    vol_today = volume.iloc[-1]
    # 出来高が平均の40%以上上回っているか
    vol_surge = vol_ma50 > 0 and (vol_today / vol_ma50) > 1.4

    if (
        base_data["detected"]
        and any(p["status"] == "breakout" for p in base_data["patterns"])
        and vol_surge
    ):
        entry_signal = "買いシグナル発火（出来高を伴うブレイクアウト）"

    # 損切りライン。利益目標は価格履歴だけでは根拠を作れないため未設定とする。
    stop_loss = current_price * 0.92  # 買値（現在値）から8%下落
    profit_line = None

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
        option_data_available=opt_data["available"],
        stage_data=stage_res,
        vcp_data=vcp_data_out,
        skew=opt_data.get("skew"),
        dte=opt_data.get("dte"),
        price_range=opt_data.get("price_range"),
        mr_parabolic_state=mr_data.get("parabolic_state", {}),
        mr_rebound_state=mr_data.get("rebound_state", {}),
        pinbar_data=pinbar_data,
        volume_climax_bleed_data=volume_data,
        advanced_patterns_data=adv_patterns,
        ma_long_term_data=long_term_ma,
        analysis_mode=analysis_mode,
        ma_10=ma_10,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_200=ma_200,
        base_recognition_data=base_data,
        entry_signal=entry_signal,
        stop_loss=stop_loss,
        profit_line=profit_line,
        strategy_context=strategy_context,
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

    option_line = "- オプション需給: データ未取得"
    if tech.option_data_available:
        option_line = (
            f"- オプション需給: GEX={tech.gex_regime}, "
            f"PCR={tech.pcr_ratio:.2f}({tech.pcr_signal}), "
            f"IV={tech.atm_iv:.1%}, MaxPain=${tech.max_pain:.0f}"
        )

    # Mean Reversion拡張テキスト構築
    mr_str = ""
    if tech.mr_parabolic_state.get("is_parabolic"):
        mr_str += f"[過熱警戒] {tech.mr_parabolic_state.get('description', '')} "
    if tech.mr_rebound_state.get("is_dip_buyable"):
        mr_str += f"[DipBuy好機] {tech.mr_rebound_state.get('description', '')} "

    # 暴落・下落時の対応強化用テキスト構築
    drop_str = ""
    if tech.volume_climax_bleed_data.get("signal") == "selling_climax":
        drop_str += f"【セリクラ示唆(買い場)】 {tech.volume_climax_bleed_data.get('description', '')} "
    elif tech.volume_climax_bleed_data.get("signal") == "low_volume_bleed":
        drop_str += f"【ナンピン厳禁(ダラダラ下落)】 {tech.volume_climax_bleed_data.get('description', '')} "

    if tech.pinbar_data.get("is_pinbar"):
        drop_str += f"【ヒゲ異常】 {tech.pinbar_data.get('description', '')} "

    if tech.advanced_patterns_data.get("detected_patterns"):
        drop_str += (
            f"【注意パターン】 {tech.advanced_patterns_data.get('description', '')} "
        )

    if tech.ma_long_term_data.get("signal") in ("deep_discount", "near_support"):
        drop_str += f"【長期MA】 {tech.ma_long_term_data.get('description', '')} "

    base_str = "未検出"
    if tech.base_recognition_data.get("detected"):
        base_str = ", ".join(
            [
                f"{p['type']} ({p['status']})"
                for p in tech.base_recognition_data.get("patterns", [])
            ]
        )

    return f"""【{ticker} テクニカル分析】
- 総合評価: {tech.overall_signal} ({tech.overall_score}点) | 分析モード: {tech.analysis_mode}
- トレンド: {tech.ma_trend}
- RSI: {tech.rsi:.1f} ({tech.rsi_signal}) | 動的: {tech.rsi_dynamic_signal} ({tech.rsi_regime})
- MACD: {tech.macd_signal} (Hist: {tech.macd_hist_slope})
- 一目均衡表: {tech.ichimoku_signal} ({tech.ichimoku_regime})
- ボリンジャー: {tech.bb_position}, スクイズ: {tech.bb_squeeze_signal}
{option_line}
- OBV: {tech.obv_trend} (Div: {tech.obv_divergence})
- パターン: 極値={tech.peak_valley_signal}, ローソク足={cdl_str}
- サポート/レジスタンス: ${tech.support_price:.2f} / ${tech.resistance_price:.2f}
- 平均回帰・過熱感: {mr_str if mr_str else "目立った過熱感・反発セットアップなし"}
- 下落時判定・特殊シグナル: {drop_str if drop_str else "特になし"}
- AVWAP(YTD): ${tech.avwap_ytd:.2f} (乖離 {tech.avwap_deviation:+.1f}%)
- ベース認識: {base_str}
- 戦略別テクニカル: {tech.strategy_context.get("summary", "未算出")}
- エントリーシグナル: {tech.entry_signal if tech.entry_signal else "なし"}
- 売買価格の判断: 売買計画機能で確認
"""
