"""
市場構造・デリバティブ動向計算モジュール (Market Microstructure)
ゴールド急落事例などで見られる「板の薄さ」「VRP縮小」「CTAの過剰ポジション」を
疑似的に算出・数値化し、AIレポート用のコンテキストを提供します。
"""

import numpy as np
import pandas as pd

from src.cache import ttl_cache
from src.data_provider import DataProvider
from src.log_config import get_logger
from src.option_analyst import analyze_option_sentiment

logger = get_logger(__name__)


def calculate_historical_volatility(df: pd.DataFrame, window: int = 20) -> float | None:
    """ヒストリカル・ボラティリティ（HV）を年率換算で計算"""
    if df is None or len(df) < window + 1:
        return None

    # 終値の対数収益率を計算
    df = df.copy()
    df["log_ret"] = np.log(df["Close"] / df["Close"].shift(1))

    # 直近window日間の標準偏差 × sqrt(252)
    hv = df["log_ret"].tail(window).std() * np.sqrt(252)
    return float(hv)


def analyze_liquidity(df: pd.DataFrame, window: int = 10) -> dict | None:
    """
    Amihud非流動性比率のプロキシおよび出来高枯渇状況をチェック。
    Amihud = |Return| / (Volume * Price)
    """
    if df is None or len(df) < 50:  # 比較用に十分なデータが必要
        return None

    df = df.copy()
    df["return"] = df["Close"].pct_change()
    # 出来高×価格（ドルの取引額）
    df["dollar_volume"] = df["Volume"] * df["Close"]

    # Volumeが0のケースを避ける
    df["dollar_volume"] = df["dollar_volume"].replace(0, np.nan)

    df["amihud"] = df["return"].abs() / df["dollar_volume"] * 1e9  # スケール調整

    recent_amihud = df["amihud"].tail(window).mean()
    historical_amihud = df["amihud"].tail(50).head(40).mean()  # 過去40日の平均

    recent_vol = df["Volume"].tail(window).mean()
    historical_vol = df["Volume"].tail(50).head(40).mean()

    # 流動性枯渇度（1.0以上なら通常より流動性が低い）
    liquidity_dryup_ratio = (
        (recent_amihud / historical_amihud) if historical_amihud > 0 else 1.0
    )
    vol_dryup_ratio = (historical_vol / recent_vol) if recent_vol > 0 else 1.0

    status = "正常"
    if liquidity_dryup_ratio > 1.5 or vol_dryup_ratio > 1.5:
        status = "枯渇気味（急変動リスク高）"

    return {
        "recent_amihud": float(recent_amihud),
        "liquidity_dryup_ratio": float(liquidity_dryup_ratio),
        "vol_dryup_ratio": float(vol_dryup_ratio),
        "status": status,
    }


def estimate_cta_positioning(df: pd.DataFrame) -> dict | None:
    """
    トレンドフォロー系ファンド（CTA等）のポジションの偏りを推定。
    -100 (Max Short) から +100 (Max Long) までのスコア。
    """
    if df is None or len(df) < 50:
        return None

    current_price = df["Close"].iloc[-1]
    ma20 = df["Close"].rolling(window=20).mean().iloc[-1]
    ma50 = df["Close"].rolling(window=50).mean().iloc[-1]

    score = 0
    # Price vs 20MA (短期トレンド)
    if current_price > ma20:
        score += 30
    else:
        score -= 30

    # Price vs 50MA (中期トレンド)
    if current_price > ma50:
        score += 40
    else:
        score -= 40

    # 20MA vs 50MA (モメンタム)
    if ma20 > ma50:
        score += 30
    else:
        score -= 30

    # 行き過ぎの判定（乖離率）
    dev_50 = (current_price - ma50) / ma50
    extremity = "ニュートラル"
    if score >= 80 and dev_50 > 0.05:
        extremity = "過剰ロング（巻き戻し警戒）"
    elif score <= -80 and dev_50 < -0.05:
        extremity = "過剰ショート（踏み上げ警戒）"

    return {"score": score, "extremity": extremity, "deviation_50ma": float(dev_50)}


@ttl_cache(ttl=600)  # 10分間キャッシュ
def analyze_market_structure(
    ticker: str = "SPY", option_analysis: dict | None = None
) -> dict | None:
    """
    ターゲット銘柄（主にSPY想定）の市場構造を総合分析する。
    """
    try:
        # 1. 過去データの取得（3ヶ月分でHVやMAを計算）
        df = DataProvider.get_historical_data(ticker, period="3mo")
        if df.empty:
            logger.warning(f"Failed to fetch local histoical data for {ticker}")
            return None

        # 2. オプション分析データ取得 (IV, GEX等)
        opt_data = option_analysis or analyze_option_sentiment(ticker)

        # --- VRP (Volatility Risk Premium) の算出 ---
        hv20 = calculate_historical_volatility(df, window=20)
        vrp = None
        vrp_narrative = "データ不足"
        iv = opt_data.get("iv") if opt_data else None
        if iv and hv20:
            vrp = iv - hv20
            if vrp < -0.02:
                vrp_narrative = f"VRPマイナス幅大 ({vrp:+.2%})：オプションによる下値支持力が極めて弱く、ショック時に脆弱"
            elif vrp < 0.01:
                vrp_narrative = f"VRP縮小 ({vrp:+.2%})：ヘッジ需要が弱く、トレンド追随の動きが出やすい"
            else:
                vrp_narrative = f"VRP正常 ({vrp:+.2%})：オプションプロバイダーからの流動性提供が期待できる"

        # --- Liquidity (流動性) の算出 ---
        liq = analyze_liquidity(df)

        # --- CTA Proxy (トレンドポジショニング) の算出 ---
        cta = estimate_cta_positioning(df)

        # --- OPEX (Gamma) Impact ---
        opex_narrative = "通常状態"
        if opt_data:
            dte = opt_data.get("dte", 30.0)
            if dte <= 3.0:
                opex_narrative = (
                    "SQ(OPEX)直前：ガンマ消失によるボラティリティ急拡大に警戒"
                )
            elif dte >= 25.0:  # SQ直後
                opex_narrative = (
                    "SQ(OPEX)通過直後：ピン留め効果が消え、新たなトレンドが発生しやすい"
                )

        # --- Unwind Risk Score の総合算出 (0-100) ---
        unwind_score = 0
        risk_flags = []

        if cta and abs(cta["score"]) >= 80:
            unwind_score += 40
            risk_flags.append(cta["extremity"])

        if liq and liq["liquidity_dryup_ratio"] > 1.5:
            unwind_score += 30
            risk_flags.append("板の薄さ(流動性枯渇)")

        if vrp is not None and vrp < 0.0:
            unwind_score += 30
            risk_flags.append("VRPマイナス(下支え脆弱)")

        unwind_level = (
            "高（急変に警戒）"
            if unwind_score >= 70
            else "中（注視が必要）"
            if unwind_score >= 40
            else "低（安定状態）"
        )

        # AIレポートに渡すナラティブ用の文字列作成
        narrative_parts = []
        narrative_parts.append(f"【{ticker}の市場構造・デリバティブ内部力学分析】")

        if cta:
            narrative_parts.append(
                f"・CTA/トレンドフォロー陣のポジション推定: スコア {cta['score']} ({cta['extremity']})"
            )
        if liq:
            narrative_parts.append(
                f"・市場流動性（板の状況）: {liq['status']} (枯渇レシオ {liq['liquidity_dryup_ratio']:.2f})"
            )
        if opt_data and vrp is not None:
            narrative_parts.append(
                f"・VRP(ボラティリティ・リスク・プレミアム): {vrp_narrative} (IV: {iv:.1%} / HV20: {hv20:.1%})"
            )
        narrative_parts.append(f"・オプション需給/OPEXイベント: {opex_narrative}")
        narrative_parts.append(
            f"・総合巻き戻し(Unwind)リスクスコア: {unwind_score}/100 - {unwind_level}"
        )

        if risk_flags:
            narrative_parts.append(
                f"※現在発火しているリスクシグナル: {', '.join(risk_flags)}"
            )

        return {
            "ticker": ticker,
            "unwind_score": unwind_score,
            "unwind_level": unwind_level,
            "cta_proxy": cta,
            "liquidity": liq,
            "vrp": vrp,
            "hv20": hv20,
            "iv": opt_data.get("iv") if opt_data else None,
            "opex_narrative": opex_narrative,
            "narrative_text": "\n".join(narrative_parts),
        }
    except Exception as e:
        logger.error(f"Error in analyze_market_structure for {ticker}: {e}")
        return None
