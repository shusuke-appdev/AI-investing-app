"""
決算データ取得モジュール
主要企業の決算情報を取得し、AIレポート用にフォーマットします。
"""
from datetime import datetime, timedelta
from typing import Optional
import yfinance as yf


# 主要決算対象銘柄（時価総額上位・市場インパクト大）
MAJOR_EARNINGS_TICKERS = [
    # Mega Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Semiconductor
    "TSM", "AVGO", "AMD", "INTC", "QCOM", "MU", "ASML", "LRCX", "AMAT",
    # AI/Cloud
    "CRM", "ORCL", "NOW", "PLTR", "SMCI",
    # Financials
    "JPM", "BAC", "GS", "MS", "WFC",
    # Consumer
    "WMT", "HD", "MCD", "NKE", "SBUX",
    # Healthcare
    "UNH", "JNJ", "PFE", "LLY", "ABBV",
    # Energy
    "XOM", "CVX",
    # Industrial
    "CAT", "BA", "UPS", "FDX"
]


def get_recent_earnings(lookback_days: int = 3) -> list[dict]:
    """
    直近の主要決算を取得します。
    
    Args:
        lookback_days: 何日前まで遡るか
    
    Returns:
        決算データのリスト
    """
    results = []
    today = datetime.now().date()
    start_date = today - timedelta(days=lookback_days)
    
    for ticker in MAJOR_EARNINGS_TICKERS:
        try:
            stock = yf.Ticker(ticker)
            
            # 決算日程を取得
            calendar = getattr(stock, 'calendar', None)
            if calendar is None:
                continue
            
            # earnings_datesから直近の決算を確認
            earnings_dates = getattr(stock, 'earnings_dates', None)
            if earnings_dates is not None and not earnings_dates.empty:
                for date_idx in earnings_dates.index:
                    earnings_date = date_idx.date() if hasattr(date_idx, 'date') else date_idx
                    
                    # 直近の決算かチェック
                    if start_date <= earnings_date <= today:
                        row = earnings_dates.loc[date_idx]
                        
                        # EPS情報を抽出
                        eps_estimate = row.get('EPS Estimate', None)
                        eps_actual = row.get('Reported EPS', None)
                        
                        # 決算がまだ発表されていない（eps_actualがNaN）場合はスキップ
                        if eps_actual is None or (hasattr(eps_actual, '__float__') and str(eps_actual) == 'nan'):
                            continue
                        
                        # Beat/Miss判定
                        if eps_estimate and eps_actual:
                            try:
                                eps_est = float(eps_estimate)
                                eps_act = float(eps_actual)
                                beat_miss = "Beat" if eps_act > eps_est else "Miss" if eps_act < eps_est else "Inline"
                                surprise_pct = ((eps_act - eps_est) / abs(eps_est) * 100) if eps_est != 0 else 0
                            except (ValueError, TypeError):
                                beat_miss = "N/A"
                                surprise_pct = 0
                        else:
                            beat_miss = "N/A"
                            surprise_pct = 0
                        
                        # Pre/After market判定（簡易）
                        timing = "after" if earnings_date < today else "pre"
                        
                        results.append({
                            "ticker": ticker,
                            "company_name": stock.info.get("shortName", ticker),
                            "date": str(earnings_date),
                            "timing": timing,
                            "eps_estimate": eps_estimate,
                            "eps_actual": eps_actual,
                            "beat_miss": beat_miss,
                            "surprise_pct": surprise_pct
                        })
                        break  # 最新の決算のみ取得
                        
        except Exception as e:
            # 個別銘柄のエラーはスキップ
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
        (1, 15, 2, 20),   # Q4決算: 1/15 ~ 2/20
        (4, 10, 5, 15),   # Q1決算: 4/10 ~ 5/15
        (7, 10, 8, 15),   # Q2決算: 7/10 ~ 8/15
        (10, 10, 11, 15), # Q3決算: 10/10 ~ 11/15
    ]
    
    for start_month, start_day, end_month, end_day in earnings_periods:
        if start_month == end_month:
            if month == start_month and start_day <= day <= end_day:
                return True
        else:
            # 月をまたぐ場合
            if (month == start_month and day >= start_day) or \
               (month == end_month and day <= end_day):
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
            eps_str = f"EPS: ${float(eps_actual):.2f} (予想: ${float(eps_estimate):.2f}, {surprise:+.1f}%)"
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
    earnings = get_recent_earnings(lookback_days=3)
    
    if not earnings:
        return None
    
    return format_earnings_for_prompt(earnings)
