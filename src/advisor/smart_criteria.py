"""
SMART基準 評価モジュール

S (Sales): 過去3四半期連続で、対前年売上伸び率が25%超
M (Margin): 年間の税引き前利益率(Pretax Margin)が30〜50%
A (Acceleration): 過去3年連続で、年間EPS増加率が30〜50%以上
R (ROE): ROE（株主資本利益率）が定常的に25%以上
T (Timing): 市場トレンドが「Confirmed up trend」である時

※ 無料APIの制約により、過去複数年/四半期の連続データを完全に取得できない場合は、
直近のデータをベースにした近似判定（ベストエフォート）を行います。
"""

from typing import Any


def evaluate_smart_criteria(
    ticker: str, info: dict[str, Any], market_state_status: str = ""
) -> dict[str, Any]:
    """
    指定銘柄のSMART基準達成度を評価します。

    Args:
        ticker: 銘柄シンボル
        info: DataProvider.get_stock_info() などから得られた企業情報辞書
        market_state_status: 市場全体のトレンド状況（Timing判定用）

    Returns:
        dict: 各基準の達成状況と、全達成フラグを含む辞書
    """
    # 初期化
    results = {
        "S": {
            "met": False,
            "status": "unknown",
            "value": "データなし",
            "desc": "売上伸び率(>25%)",
        },
        "M": {
            "met": False,
            "status": "unknown",
            "value": "データなし",
            "desc": "利益率(30~50%)",
        },
        "A": {
            "met": False,
            "status": "unknown",
            "value": "データなし",
            "desc": "EPS増加率(>30%)",
        },
        "R": {
            "met": False,
            "status": "unknown",
            "value": "データなし",
            "desc": "ROE(>25%)",
        },
        "T": {
            "met": False,
            "status": "unknown",
            "value": market_state_status or "不明",
            "desc": "市場トレンド(上昇)",
        },
        "all_met": False,
    }

    # S (Sales) - 簡易判定: 直近のRevenue Growthが25%超か
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        results["S"]["status"] = "not_met"
        results["S"]["value"] = f"{rev_growth:.1f}%"
        if rev_growth >= 25.0:
            results["S"]["met"] = True
            results["S"]["status"] = "met"

    # M (Margin) - 簡易判定: Operating Margin または Profit Margin を使用
    # （yfinanceはPretax Marginを直接返さないことが多いため）
    margin = info.get("operatingMargins")
    if margin is not None:
        results["M"]["status"] = "not_met"
        results["M"]["value"] = f"{margin:.1f}%"
        # 30%以上であればOKとする（50%上限は厳密には設けない、高すぎても良しとする解釈）
        if margin >= 30.0:
            results["M"]["met"] = True
            results["M"]["status"] = "met"

    # A (Acceleration) - 簡易判定: 直近のEarnings Growthが30%超か
    earn_growth = info.get("earningsGrowth")
    if earn_growth is not None:
        results["A"]["status"] = "not_met"
        results["A"]["value"] = f"{earn_growth:.1f}%"
        if earn_growth >= 30.0:
            results["A"]["met"] = True
            results["A"]["status"] = "met"
    else:
        results["A"]["value"] = "入力データ不足: EPS成長加速を取得できません。"

    # R (ROE) - yfinanceの returnOnEquity を使用
    # infoディクショナリに入っていない可能性があるため、必要に応じて取得（既存infoにある前提）
    # APIから取得できない場合は returnOnAssets 等から推測するか、利用不可とする
    roe = info.get("returnOnEquity")
    if roe is not None:
        results["R"]["status"] = "not_met"
        # yfinance の ROE は 0.25 (25%) のような実数で来る場合と 25.0 で来る場合がある
        # DataProviderが % に直していない場合は注意。ここでは % 単位と仮定。
        # もし小数表記なら * 100 する必要があるが、ここでは 25.0 以上の比較とする
        # 0.25 のような値が来るのを防ぐため、値が小さい場合は100倍を考慮（適当なヒューリスティック）
        roe_val = roe * 100 if roe < 2.0 else roe
        results["R"]["value"] = f"{roe_val:.1f}%"
        if roe_val >= 25.0:
            results["R"]["met"] = True
            results["R"]["status"] = "met"
    else:
        # infoに無い場合は代替としてROAを見るか、データなしとする
        roa = info.get("returnOnAssets")
        if roa is not None:
            results["R"]["value"] = f"ROA: {roa:.1f}% (ROE不明)"
            results["R"]["value"] += "・参考値のため判定不能"
        else:
            results["R"]["value"] = "入力データ不足: ROEを取得できません。"

    # T (Timing)
    # market_state_status に "強気相場入り確認" や "UPTREND" などの文字が含まれていればOK
    if (
        "強気" in market_state_status
        or "UPTREND" in market_state_status.upper()
        or "上昇トレンド" in market_state_status
    ):
        results["T"]["met"] = True
        results["T"]["status"] = "met"
    elif not market_state_status or market_state_status.lower() in {
        "unknown",
        "不明",
    }:
        results["T"]["value"] = "市場状態未更新: Market詳細更新後に判定します。"
    elif market_state_status and market_state_status.lower() not in {"unknown", "不明"}:
        results["T"]["status"] = "not_met"

    # 全条件クリア判定
    results["all_met"] = all(
        [
            results["S"]["met"],
            results["M"]["met"],
            results["A"]["met"],
            results["R"]["met"],
            results["T"]["met"],
        ]
    )
    results["overall_status"] = (
        "all_clear"
        if results["all_met"]
        else "pending"
        if any(results[key]["status"] == "unknown" for key in ("S", "M", "A", "R", "T"))
        else "not_met"
    )

    return results
