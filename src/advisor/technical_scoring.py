"""価格・出来高指標を集約する参考スコアリング。"""


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


def calc_flow_score(obv) -> float:
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

    return max(-2.0, min(2.0, score))
