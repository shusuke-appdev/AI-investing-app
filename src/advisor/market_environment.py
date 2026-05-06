"""
市場環境の総合評価モジュール

各種インジケーター（トレンド、モメンタム、ボラティリティ、オシレーター、センチメント）
のシグナルを標準化スコア（-1.0 〜 +1.0）として定量化し、ウェイト付けによる
加重平均から現在の市場環境を「強気・中立・弱気」で総合判断します。
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.log_config import get_logger

logger = get_logger(__name__)


@dataclass
class MarketSignal:
    indicator_name: str
    raw_value: Any
    score: float  # -1.0 (極端な弱気) 〜 +1.0 (極端な強気)
    weight: float  # 重要度
    rationale: str  # 評価理由

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


def _evaluate_trend(prices: pd.Series) -> MarketSignal:
    """移動平均線(MA)のトレンド判定 (Weight: 1.0)"""
    if prices is None or len(prices) < 200:
        return MarketSignal("トレンド (MA)", None, 0.0, 1.0, "データ不足により判定不可")

    current_price = prices.iloc[-1]
    ma20 = prices.rolling(20).mean().iloc[-1]
    ma50 = prices.rolling(50).mean().iloc[-1]
    ma200 = prices.rolling(200).mean().iloc[-1]

    # 判定ロジック
    if current_price >= ma200 and current_price >= ma50 and current_price >= ma20:
        score = 1.0
        rationale = "全ての主要移動平均線を上回る（パーフェクトオーダー圏内）"
    elif current_price >= ma200 and current_price >= ma50 and current_price < ma20:
        score = 0.3
        rationale = "長期・中期線は上回るが、20日線を割り込み短期モメンタム低下"
    elif current_price >= ma200 and current_price < ma50:
        score = -0.3
        rationale = "200日線は維持するも、50日線を割り込み中期調整局面"
    elif current_price < ma200 and current_price < ma50 and current_price < ma20:
        score = -1.0
        rationale = "全ての主要移動平均線を下回る（完全な下落トレンド）"
    else:
        # その他の状態（200日線下だが短期線は上など、反発局面）
        if current_price < ma200 and current_price >= ma20:
            score = 0.0
            rationale = "200日線以下の長期下落トレンド内で、短期的な反発(20日線上)"
        else:
            score = -0.5
            rationale = "移動平均線が混在（弱気バイアス）"

    return MarketSignal("トレンド (MA)", current_price, score, 1.0, rationale)


def _evaluate_momentum(bm_data: pd.DataFrame) -> MarketSignal:
    """FTD(Follow-Through Day)によるモメンタム判定 (Weight: 0.8)"""
    from src.advisor.minervini_analyzer import detect_follow_through_day

    if bm_data is None or bm_data.empty:
        return MarketSignal("モメンタム (FTD)", None, 0.0, 0.8, "データ不足")

    ftd_result = detect_follow_through_day(bm_data)
    status = ftd_result.get("status", "")

    if ftd_result.get("is_ftd"):
        score = 1.0
        rationale = "強気相場入りの強力なシグナル（Follow-Through Day）点灯中"
    elif "ラリー試行中" in status:
        score = 0.5
        rationale = "下落からの反発ラリーを試行中（要警戒期間）"
    elif "下落トレンド" in status:
        score = -1.0
        rationale = "明確な下落トレンド中（底入れシグナルなし）"
    else:
        score = 0.0
        rationale = "明示的な強気・弱気のモメンタムシグナルなし"

    return MarketSignal("モメンタム (FTD)", ftd_result, score, 0.8, rationale)


def _evaluate_volatility(bm_data: pd.DataFrame) -> MarketSignal:
    """ボラティリティ・クラスタリング判定 (Weight: 2.0)"""
    from src.advisor.volatility import compute_volatility
    from src.advisor.volatility_clustering import generate_signals as gen_vol_signals

    try:
        v_df = compute_volatility(bm_data)
        vol_sig = gen_vol_signals(v_df, current_position=False)

        if vol_sig["clustering_state"]:
            score = -1.0
            rationale = f"【要警戒】{vol_sig['signal']} - ボラティリティ上昇によるリスクオフ環境"
        else:
            score = 0.5
            rationale = f"安定期 ({vol_sig['signal']}) - ボラティリティは落ち着いている"

        return MarketSignal("市場リスク (Vol)", vol_sig, score, 2.0, rationale)
    except Exception as e:
        logger.error(f"Volatility Evaluation Error: {e}")
        return MarketSignal("市場リスク (Vol)", None, 0.0, 2.0, "計算エラー")


def _evaluate_breadth(market_type: str) -> list[MarketSignal]:
    """S&PオシレーターとMcClellanオシレーターの判定 (各Weight: 0.5)"""
    signals: list[MarketSignal] = []
    if market_type != "US":
        return signals

    try:
        from src.advisor.technical_breadth import (
            calculate_mcclellan_oscillator,
            calculate_sp_oscillator,
            fetch_breadth_data,
        )

        b_df = fetch_breadth_data("1mo")
        if b_df.empty:
            return signals

        # 1. S&P Oscillator
        sp_osc = calculate_sp_oscillator(b_df)
        val = sp_osc.get("oscillator_percent", 0.0)

        if val > 4.0:
            sp_score = -1.0
            sp_rat = f"極端な買われすぎ({val}%)。反発下落（プルバック）を警戒。"
        elif val < -4.0:
            sp_score = 1.0
            sp_rat = f"極端な売られすぎ({val}%)。反発上昇の可能性あり。"
        elif val > 0:
            sp_score = 0.2
            sp_rat = f"買われ傾向({val}%)で推移。"
        else:
            sp_score = -0.2
            sp_rat = f"売られ傾向({val}%)で推移。"

        signals.append(MarketSignal("S&Pオシレーター", sp_osc, sp_score, 0.5, sp_rat))

        # 2. McClellan Oscillator
        mc_osc = calculate_mcclellan_oscillator(b_df)
        mc_val = mc_osc.get("mcclellan_value", 0.0)

        if mc_val > 100:
            mc_score = -0.8
            mc_rat = f"買われすぎ({mc_val:.0f})。過熱感からの調整リスク。"
        elif mc_val < -100:
            mc_score = 0.8
            mc_rat = f"売られすぎ({mc_val:.0f})からの反発期待。"
        elif mc_val > 0:
            mc_score = 0.2
            mc_rat = f"ゼロラインより上({mc_val:.0f})。短期上昇モメンタム。"
        else:
            mc_score = -0.2
            mc_rat = f"ゼロラインより下({mc_val:.0f})。短期下落モメンタム。"

        signals.append(MarketSignal("McClellan", mc_osc, mc_score, 0.5, mc_rat))

    except Exception as e:
        logger.error(f"Breadth Evaluation Error: {e}")

    return signals


def _evaluate_option_sentiment(
    market_type: str, option_state: Any
) -> MarketSignal | None:
    """オプションセンチメント判定 (Weight: 0.5)"""
    if market_type != "US" or not option_state:
        return None

    val_pcr = None
    sentiment = "中立"

    for opt in option_state:
        if opt["ticker"] == "SPY":
            sentiment = opt["sentiment"]
            if opt.get("pcr"):
                val_pcr = opt["pcr"]["volume_pcr"]
            break

    if val_pcr is None:
        return None

    if val_pcr > 1.2 or sentiment == "極端な弱気":
        score = -0.8
        rat = f"プット取引活発(PCR={val_pcr:.2f})。下落を警戒する動き。"
    elif val_pcr < 0.7 or "強気" in sentiment:
        score = 0.8
        rat = f"コール取引活発(PCR={val_pcr:.2f})。上昇を楽観視。"
    else:
        score = 0.0
        rat = f"中立的(PCR={val_pcr:.2f})。"

    return MarketSignal("オプションセンチメント", val_pcr, score, 0.5, rat)


def _evaluate_microstructure(market_type: str) -> list[MarketSignal]:
    """
    マーケットマイクロストラクチャー指標のシグナル化
    VRP, CTAポジショニング, 流動性(Amihud)
    """
    if market_type != "US":
        return []

    try:
        from src.market_microstructure import analyze_market_structure
        micro = analyze_market_structure("SPY")
        if not micro:
            return []

        signals = []
        
        # 1. VRP (Volatility Risk Premium)
        vrp_val = micro.get("vrp")
        if vrp_val is not None:
            if vrp_val < 0.0:
                signals.append(MarketSignal("VRP (ボラリスクプレミアム)", f"{vrp_val:.2%}", -0.6, 0.6, "VRP縮小。マーケットメーカーのプット売り意欲減退によりダウンサイドリスク増大。"))
            elif vrp_val > 0.05:
                signals.append(MarketSignal("VRP (ボラリスクプレミアム)", f"{vrp_val:.2%}", 0.5, 0.6, "VRP拡大。オプションの売り手が存在し、ダウンサイドは保護されやすい。"))
            else:
                signals.append(MarketSignal("VRP (ボラリスクプレミアム)", f"{vrp_val:.2%}", 0.0, 0.6, "VRPはニュートラル圏内。"))

        # 2. CTAポジショニング
        cta = micro.get("cta_proxy") or {}
        cta_val = cta.get("extremity", "")
        if "Extreme Long" in cta_val:
            signals.append(MarketSignal("CTAポジショニング", cta_val, -0.5, 0.4, "トレンドフォロー勢の過剰ロング。アンワインド時の急落リスクあり。"))
        elif "Extreme Short" in cta_val:
            signals.append(MarketSignal("CTAポジショニング", cta_val, 0.5, 0.4, "過剰ショート。ショートカバーによる急騰リスクあり。"))
        elif "Long" in cta_val:
            signals.append(MarketSignal("CTAポジショニング", cta_val, 0.2, 0.4, "CTAはロング基調。トレンド継続。"))
        elif "Short" in cta_val:
            signals.append(MarketSignal("CTAポジショニング", cta_val, -0.2, 0.4, "CTAはショート基調。"))
        else:
            signals.append(MarketSignal("CTAポジショニング", cta_val, 0.0, 0.4, "極端な偏りなし。"))

        # 3. 流動性 (Amihud Illiquidity)
        liq = micro.get("liquidity") or {}
        liq_val = liq.get("status", "")
        if "悪化" in liq_val or "枯渇" in liq_val:
            signals.append(MarketSignal("市場流動性", liq_val, -0.8, 0.5, "流動性が悪化。小さなフローで価格が飛びやすい脆弱な状態。"))
        elif "良好" in liq_val:
            signals.append(MarketSignal("市場流動性", liq_val, 0.3, 0.5, "流動性は十分。ショック吸収力あり。"))
        else:
            signals.append(MarketSignal("市場流動性", liq_val, 0.0, 0.5, "流動性は標準レベル。"))

        return signals
    except Exception as e:
        logger.warning(f"Microstructure evaluation failed: {e}")
        return []


def evaluate_market_environment(
    market_type: str, option_state: Any = None
) -> dict[str, Any]:
    """
    複数指標を統合し、現在の市場環境をスコアリングして総合判断を下します。

    Args:
        market_type: "US" または "JP"
        option_state: st.session_state.option_analysis の値（必要に応じて）

    Returns:
        総合判断結果を含む辞書
    """
    benchmarks = {"US": "SPY", "JP": "^N225"}
    target_bm = benchmarks.get(market_type, "SPY")

    from src.market_data import get_stock_data

    bm_data = get_stock_data(target_bm, "1y")

    signals: list[MarketSignal] = []

    if bm_data is not None and not bm_data.empty:
        signals.append(_evaluate_trend(bm_data["Close"]))
        signals.append(_evaluate_momentum(bm_data))
        signals.append(_evaluate_volatility(bm_data))

    signals.extend(_evaluate_breadth(market_type))

    opt_sig = _evaluate_option_sentiment(market_type, option_state)
    if opt_sig:
        signals.append(opt_sig)

    signals.extend(_evaluate_microstructure(market_type))

    if not signals:
        return {
            "status": "データなし",
            "score": 0.0,
            "signals": [],
            "error": "市場データが取得できませんでした。",
        }

    total_weight = sum(s.weight for s in signals)
    total_weighted_score = sum(s.weighted_score for s in signals)

    final_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

    # -1.0 〜 +1.0 の範囲で判定
    if final_score >= 0.3:
        status = "🟢 強気 (Bullish)"
        description = "複数のインジケーターが相場の強さを示唆しています。積極的なエクスポージャーが報われやすい環境です。"
    elif final_score <= -0.3:
        status = "🔴 弱気 (Bearish)"
        description = "複数のインジケーターがリスクの高まりを示唆しています。ポジションの縮小やヘッジの検討が推奨されます。"
    else:
        status = "⚪ 中立 (Neutral)"
        description = "強気・弱気のシグナルが混在、または明確な方向感に欠けています。無理なエントリーは控える局面です。"

    # 独自フォーマットの辞書を返す
    return {
        "status": status,
        "score": final_score,
        "description": description,
        "signals": [
            {
                "name": s.indicator_name,
                "score": s.score,
                "weight": s.weight,
                "rationale": s.rationale,
            }
            for s in signals
        ],
    }
