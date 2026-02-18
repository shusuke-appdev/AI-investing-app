"""
テクニカル指標（スコアリング・オプション統合）モジュール

各テクニカル指標の結果を集約してカテゴリ別スコアを算出するロジックと、
オプション分析データの統合機能を提供します。
"""


def analyze_options_data(ticker: str, current_price: float) -> dict:
    """
    オプションデータを取得し、GEXレジームと需給スコア調整値を返す。

    Returns:
        dict: {
            "gex_regime": str,
            "gex_positive_wall": float,
            "gex_negative_wall": float,
            "pcr_ratio": float,
            "pcr_signal": str,
            "atm_iv": float,
            "max_pain": float,
            "score_adj": float
        }
    """
    res = {
        "gex_regime": "unknown",
        "gex_positive_wall": 0.0,
        "gex_negative_wall": 0.0,
        "pcr_ratio": 0.0,
        "pcr_signal": "中立",
        "atm_iv": 0.0,
        "max_pain": 0.0,
        "score_adj": 0.0,
    }

    try:
        from src.option_analyst import (
            calculate_atm_iv,
            calculate_gex,
            calculate_max_pain,
            calculate_pcr,
        )

        # GEX
        gex = calculate_gex(ticker)
        if gex and "nearby_net_gex" in gex:
            gex_val = gex["nearby_net_gex"]
            res["gex_regime"] = "positive_gamma" if gex_val > 0 else "negative_gamma"

            # Wall判定
            if gex.get("positive_wall"):
                res["gex_positive_wall"] = gex["positive_wall"].get("strike", 0.0)
                if current_price >= res["gex_positive_wall"] * 0.99:
                    res["score_adj"] -= 0.3

            if gex.get("negative_wall"):
                res["gex_negative_wall"] = gex["negative_wall"].get("strike", 0.0)
                if current_price <= res["gex_negative_wall"] * 1.01:
                    res["score_adj"] += 0.3

        # PCR
        pcr = calculate_pcr(ticker)
        if pcr:
            res["pcr_ratio"] = pcr.get("oi_pcr", 0.0)
            if res["pcr_ratio"] > 1.2:
                res["score_adj"] -= 0.5
                res["pcr_signal"] = "弱気"
            elif res["pcr_ratio"] < 0.7:
                res["score_adj"] += 0.5
                res["pcr_signal"] = "強気"

        # IV
        iv = calculate_atm_iv(ticker)
        if iv:
            res["atm_iv"] = iv
            if iv > 0.4:
                res["score_adj"] -= 0.2

        # Max Pain
        mp = calculate_max_pain(ticker)
        if mp:
            res["max_pain"] = mp
            if current_price < mp * 0.95:
                res["score_adj"] += 0.3
            elif current_price > mp * 1.05:
                res["score_adj"] -= 0.3

    except ImportError:
        pass
    except Exception:
        pass

    res["score_adj"] = max(-1.0, min(1.0, res["score_adj"]))
    return res


def calc_trend_score(ma, macd, ichi, adx) -> float:
    score = 0.0
    # MACD
    if macd["signal"] == "強気":
        score += 1.0 if macd["zero_filter"] == "above_zero" else 0.5
    elif macd["signal"] == "弱気":
        score -= 1.0 if macd["zero_filter"] == "below_zero" else 0.5

    slope_bonus = {"bottoming": 0.3, "topping": -0.3}
    score += slope_bonus.get(macd["hist_slope"], 0)

    # Ichimoku
    if ichi["sannyaku"]:
        score += 1.0
    elif ichi["regime"] == "above_cloud":
        score += 0.5
    elif ichi["regime"] == "below_cloud":
        score -= 0.7
    elif ichi["regime"] == "in_cloud":
        score *= 0.5

    # MA
    if ma == "上昇トレンド":
        score += 0.5
    elif ma == "下降トレンド":
        score -= 0.5

    # ADX Boost
    if adx >= 25:
        score *= 1.3

    return max(-2.0, min(2.0, score))


def calc_momentum_score(dyn_rsi, stoch, div) -> float:
    score = 0.0
    # Dynamic RSI
    if dyn_rsi["signal"] == "売られすぎ":
        score += 1.0
    elif dyn_rsi["signal"] == "買われすぎ":
        score -= 1.0

    # Stoch RSI
    if stoch <= 20:
        score += 0.5
    elif stoch >= 80:
        score -= 0.5

    # Divergence
    if div == "bullish":
        score += 0.8
    elif div == "bearish":
        score -= 0.8

    return max(-2.0, min(2.0, score))


def calc_pattern_score(bb_sq, bb, ma_dev, pv, cdl) -> float:
    score = 0.0
    # BB Squeeze
    if bb_sq["signal"] == "expansion_breakout":
        score += 1.0
    elif bb_sq["squeeze"]:
        score += 0.2

    # BB Position
    if bb["position"] == "下限突破":
        score += 0.5
    elif bb["position"] == "上限突破":
        score -= 0.5

    # Peak/Valley Structure
    if pv["signal"] == "higher_highs":
        score += 0.5
    elif pv["signal"] == "lower_lows":
        score -= 0.5

    # Candlestick
    score += cdl["score_adjustment"]

    # MA Deviation Reversion
    if ma_dev < -15:
        score += 0.7
    elif ma_dev < -5:
        score += 0.3
    elif ma_dev > 15:
        score -= 0.7
    elif ma_dev > 5:
        score -= 0.3

    return max(-2.0, min(2.0, score))


def calc_flow_score(obv, option_adj) -> float:
    score = 0.0
    # OBV
    if obv["divergence"] == "bullish":
        score += 1.0
    elif obv["divergence"] == "bearish":
        score -= 1.0
    if obv["trend"] == "上昇":
        score += 0.3
    elif obv["trend"] == "下降":
        score -= 0.3

    # Option Analysis Integration
    score += option_adj

    return max(-2.0, min(2.0, score))
