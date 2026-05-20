"""
市場監視モジュール (Market Monitor)

Distribution Day (売り抜け日) のトラッキング、
市場天井の複合検知、イールドスプレッドの判定を行います。
"""

import pandas as pd


def track_distribution_days(df: pd.DataFrame) -> dict:
    """
    指定された指数のDistribution Day (売り抜け日) をトラッキングします。

    加算条件: 前日の出来高を上回り、かつ指数が0.2%以上下落して引けた日
    減算条件: 売り抜け日の終値から5%上昇、または25営業日経過
    """
    if df is None or len(df) < 26:
        return {"count": 0, "status": "データ不足", "level": "normal"}

    # カラム名の正規化（外部データソース由来の小文字カラム対応）
    col_map = {"close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if "Close" not in df.columns or "Volume" not in df.columns:
        return {"count": 0, "status": "カラム不足", "level": "normal"}

    count = 0
    distribution_days = []  # [(index, close_price), ...]

    for i in range(1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i - 1]

        # 25営業日経過した古い日を削除
        distribution_days = [d for d in distribution_days if i - d[0] <= 25]

        # 5%上昇によるリセット判定
        # 過去の売り抜け日の終値から現在の終値が5%以上高ければ、その売り抜け日はキャンセルされる
        valid_days = []
        for d in distribution_days:
            if current["Close"] >= d[1] * 1.05:
                pass  # キャンセル
            else:
                valid_days.append(d)
        distribution_days = valid_days

        # 新規の売り抜け日判定
        vol_increase = current["Volume"] > prev["Volume"]
        price_drop = (current["Close"] - prev["Close"]) / prev["Close"] <= -0.002

        if vol_increase and price_drop:
            distribution_days.append((i, current["Close"]))

    count = len(distribution_days)

    if count >= 8:
        level = "red"
        status = "警戒警報 (新規株式購入停止・出口戦略発動)"
    elif count >= 6:
        level = "yellow"
        status = "注意体制 (新規購入に慎重に)"
    else:
        level = "green"
        status = "正常"

    return {
        "count": count,
        "status": status,
        "level": level,
    }


def detect_market_climax(
    spy_df: pd.DataFrame, ndx_df: pd.DataFrame, opt_pcr: float
) -> dict:
    """
    市場天井（ファイナルクライマックス）の複合検知を行います。
    """
    warnings = []

    if len(spy_df) < 5 or len(ndx_df) < 5:
        return {"is_climax": False, "warnings": warnings}

    spy_recent = spy_df.iloc[-5:]

    # 1. 株価と出来高の乖離 (Chugging / Stalling)
    # 出来高が増加しているが、価格がほとんど上がっていない
    vol_trend = spy_recent["Volume"].is_monotonic_increasing
    price_trend = (
        spy_recent["Close"].iloc[-1] - spy_recent["Close"].iloc[0]
    ) / spy_recent["Close"].iloc[0]
    if vol_trend and price_trend < 0.005:
        warnings.append("株価と出来高の乖離 (出来高増も価格上昇伴わず)")

    # 2. ダイバージェンス (SPYとNDXの逆行)
    spy_ret = (spy_df["Close"].iloc[-1] - spy_df["Close"].iloc[-5]) / spy_df[
        "Close"
    ].iloc[-5]
    ndx_ret = (ndx_df["Close"].iloc[-1] - ndx_df["Close"].iloc[-5]) / ndx_df[
        "Close"
    ].iloc[-5]

    if (spy_ret > 0 and ndx_ret < 0) or (spy_ret < 0 and ndx_ret > 0):
        warnings.append(
            f"指数間ダイバージェンス (SPY {spy_ret:+.1%}, NDX {ndx_ret:+.1%})"
        )

    # 3. PCR悪化
    if opt_pcr >= 1.0:
        warnings.append(f"プット・コールレシオ悪化 (PCR: {opt_pcr:.2f})")

    # リーディング銘柄変調はここでは個別データがないためモック
    # warnings.append("リーディング銘柄の変調 (モック)")

    is_climax = len(warnings) >= 3

    return {
        "is_climax": is_climax,
        "warnings": warnings,
        "level": "critical" if is_climax else "normal",
    }


def evaluate_yield_spread(yield_10y: float, index_pe_dict: dict[str, float]) -> dict:
    """
    株式益回りと債券利回りのイールドスプレッドを評価します。
    """
    results = {}
    overall_status = "neutral"
    warnings = []

    for idx, pe in index_pe_dict.items():
        if pe <= 0:
            continue

        earnings_yield = (1 / pe) * 100
        spread = earnings_yield - yield_10y

        status = "neutral"
        level = "neutral"
        if idx == "NDX":
            if spread >= 2.3:
                status = "株式優位 (上昇余地あり)"
            elif spread <= 1.5:
                status = "債券優位 (天井警戒)"
                warnings.append("ナスダックのイールドスプレッドが1.5%以下 (割高警戒)")
        elif idx == "SPY":
            if spread >= 3.8:
                status = "株式優位 (上昇余地あり)"
            elif spread <= 3.0:
                status = "債券優位 (天井警戒)"
                warnings.append("S&P500のイールドスプレッドが3.0%以下 (割高警戒)")

        if idx == "NDX":
            level = "green" if spread >= 2.3 else "red" if spread <= 1.5 else "neutral"
        elif idx == "SPY":
            level = "green" if spread >= 3.8 else "red" if spread <= 3.0 else "neutral"

        results[idx] = {
            "earnings_yield": earnings_yield,
            "spread": spread,
            "status": status,
            "level": level,
        }

    if len(warnings) > 0:
        overall_status = "caution"

    return {
        "yield_10y": yield_10y,
        "spreads": results,
        "overall_status": overall_status,
        "warnings": warnings,
    }
