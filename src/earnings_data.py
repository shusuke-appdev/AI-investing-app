"""
決算データ取得モジュール
主要企業の決算情報を取得し、AIレポート用にフォーマットします。
"""

from datetime import datetime, timedelta
from typing import Optional

from src.data_provider import DataProvider
from src.finnhub_client import is_configured

# 主要決算対象銘柄（時価総額上位・市場インパクト大）
MAJOR_EARNINGS_TICKERS = [
    # Mega Tech
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "NVDA",
    "TSLA",
    # Semiconductor
    "TSM",
    "AVGO",
    "AMD",
    "INTC",
    "QCOM",
    "MU",
    "ASML",
    "LRCX",
    "AMAT",
    # AI/Cloud
    "CRM",
    "ORCL",
    "NOW",
    "PLTR",
    "SMCI",
    # Financials
    "JPM",
    "BAC",
    "GS",
    "MS",
    "WFC",
    # Consumer
    "WMT",
    "HD",
    "MCD",
    "NKE",
    "SBUX",
    # Healthcare
    "UNH",
    "JNJ",
    "PFE",
    "LLY",
    "ABBV",
    # Energy
    "XOM",
    "CVX",
    # Industrial
    "CAT",
    "BA",
    "UPS",
    "FDX",
]


def get_recent_earnings(lookback_days: int = 3) -> list[dict]:
    """
    直近の主要決算を取得します。
    Finnhub Calendar APIを使用。

    Args:
        lookback_days: 何日前まで遡るか

    Returns:
        決算データのリスト
    """
    if not is_configured():
        # Finnhub未設定時は空リスト（yfinanceフォールバックは実装複雑なため省略）
        return []

    results = []
    today = datetime.now()
    start_date = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    # DataProvider経由で取得
    calendar_data = DataProvider.get_earnings_calendar(
        from_date=start_date, to_date=end_date
    )

    # 対象銘柄のみフィルタリング
    # Finnhub Calendar returns: date, epsActual, epsEstimate, hour, quarter, revenueActual, revenueEstimate, symbol, year

    target_tickers = set(MAJOR_EARNINGS_TICKERS)

    for item in calendar_data:
        ticker = item.get("symbol")
        if ticker not in target_tickers:
            continue

        try:
            earnings_date = item.get("date")  # YYYY-MM-DD
            eps_act = item.get("epsActual")
            eps_est = item.get("epsEstimate")

            # Beat/Miss判定
            beat_miss = "N/A"
            surprise_pct = 0

            if eps_act is not None and eps_est is not None:
                if eps_act > eps_est:
                    beat_miss = "Beat"
                elif eps_act < eps_est:
                    beat_miss = "Miss"
                else:
                    beat_miss = "Inline"

                if eps_est != 0:
                    surprise_pct = ((eps_act - eps_est) / abs(eps_est)) * 100

            results.append(
                {
                    "ticker": ticker,
                    "company_name": ticker,  # Finnhub Calendar doesn't provide name
                    "date": earnings_date,
                    "timing": item.get("hour", ""),  # bmo, amc, etc
                    "eps_estimate": eps_est,
                    "eps_actual": eps_act,
                    "beat_miss": beat_miss,
                    "surprise_pct": surprise_pct,
                }
            )

        except Exception:
            continue

    # 日付順にソート（新しい順）
    results.sort(key=lambda x: x["date"], reverse=True)
    return results


def is_earnings_season() -> bool:
    """
    現在が決算シーズンか判定します。

    決算シーズン: 1月中旬〜2月中旬, 4月中旬〜5月中旬, 7月中旬〜8月中旬, 10月中旬〜11月中旬

    Returns:
        決算シーズンの場合True
    """
    today = datetime.now()
    month = today.month
    day = today.day

    # 各四半期の決算シーズン（概算）
    earnings_periods = [
        (1, 15, 2, 20),  # Q4決算: 1/15 ~ 2/20
        (4, 10, 5, 15),  # Q1決算: 4/10 ~ 5/15
        (7, 10, 8, 15),  # Q2決算: 7/10 ~ 8/15
        (10, 10, 11, 15),  # Q3決算: 10/10 ~ 11/15
    ]

    for start_month, start_day, end_month, end_day in earnings_periods:
        if start_month == end_month:
            if month == start_month and start_day <= day <= end_day:
                return True
        else:
            # 月をまたぐ場合
            if (month == start_month and day >= start_day) or (
                month == end_month and day <= end_day
            ):
                return True

    return False


def format_earnings_for_prompt(earnings: list[dict]) -> str:
    """
    AIプロンプト用に決算データをフォーマットします。

    Args:
        earnings: 決算データのリスト

    Returns:
        フォーマット済み文字列（決算がない場合は空文字）
    """
    if not earnings:
        return ""

    lines = ["【直近の主要決算】"]

    for e in earnings[:10]:  # 最大10件
        ticker = e["ticker"]
        beat_miss = e["beat_miss"]
        eps_actual = e.get("eps_actual", "N/A")
        eps_estimate = e.get("eps_estimate", "N/A")
        surprise = e.get("surprise_pct", 0)

        # Beat/Missのアイコン
        icon = "✅" if beat_miss == "Beat" else "❌" if beat_miss == "Miss" else "➖"

        # EPS情報
        try:
            # None check before formatting
            act_val = float(eps_actual) if eps_actual is not None else 0.0
            est_val = float(eps_estimate) if eps_estimate is not None else 0.0

            eps_str = f"EPS: ${act_val:.2f} (予想: ${est_val:.2f}, {surprise:+.1f}%)"
        except (ValueError, TypeError):
            eps_str = f"EPS: {eps_actual}"

        lines.append(f"- {icon} {ticker}: {beat_miss} - {eps_str}")

    return "\n".join(lines)


def get_earnings_context_for_recap() -> Optional[str]:
    """
    AIレポート用の決算コンテキストを取得します。
    決算シーズン外または決算がない場合はNoneを返します。

    Returns:
        決算コンテキスト文字列 または None
    """
    # 決算シーズンでなくても、直近の決算があれば表示
    # Finnhubの場合はAPIコール制限もあるため、呼び出し頻度に注意が必要だが
    # finnhub_client側でcache制御していない（get_earnings_calendarは都度呼ぶ）。
    # ただし今回はレポート生成時のみ呼ばれるので許容範囲。
    try:
        earnings = get_recent_earnings(lookback_days=3)

        if not earnings:
            return None

        return format_earnings_for_prompt(earnings)
    except Exception:
        return None
