"""
銘柄分析AIモジュール
テクニカル分析を統合した詳細な銘柄分析を提供します。
"""

from src.advisor.technical import get_technical_summary_for_ai
from src.gemini_client import generate_content


def analyze_stock(
    ticker: str,
    stock_info: dict,
    historical_data: dict | None = None,
    news_headlines: list[str] | None = None,
) -> str:
    """
    銘柄の詳細分析を生成します（テクニカル分析統合版）。

    Args:
        ticker: 銘柄コード
        stock_info: yfinanceから取得した銘柄情報
        historical_data: 過去の株価データ
        news_headlines: 関連ニュースのヘッドライン

    Returns:
        分析レポート（マークダウン形式）
    """
    # 基本情報の抽出
    company_name = stock_info.get("name", ticker)
    sector = stock_info.get("sector", "不明")
    industry = stock_info.get("industry", "不明")
    market_cap = stock_info.get("market_cap", 0)
    pe_ratio = stock_info.get("pe_ratio", "N/A")
    forward_pe = stock_info.get("forward_pe", "N/A")
    price = stock_info.get("current_price", 0)
    target_price = stock_info.get("target_price", "N/A")

    # テクニカル分析を取得
    technical_summary = get_technical_summary_for_ai(ticker)

    # ユーザー参照知識を取得
    from src.knowledge_storage import get_knowledge_for_ai_context

    knowledge_context = get_knowledge_for_ai_context(max_items=5)

    # プロンプト構築
    from src.prompts.analysis_prompts import STOCK_ANALYSIS_PROMPT_TEMPLATE

    market_cap_b = market_cap / 1e9 if isinstance(market_cap, (int, float)) else 0

    prompt = STOCK_ANALYSIS_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        market_cap_b=market_cap_b,
        price=price,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        target_price=target_price,
        technical_summary=technical_summary,
        news_headlines=chr(10).join(news_headlines[:5])
        if news_headlines
        else "ニュースなし",
        knowledge_context=knowledge_context if knowledge_context else "特になし",
    )

    result = generate_content(prompt)
    if result:
        return result
    return "分析エラー: Gemini APIが利用できません"


def get_quick_summary(ticker: str, stock_info: dict) -> str:
    """
    銘柄のクイックサマリーを生成します。
    """
    company_name = stock_info.get("name", ticker)
    sector = stock_info.get("sector", "不明")
    market_cap = stock_info.get("market_cap", 0)
    pe_ratio = stock_info.get("pe_ratio", "N/A")

    market_cap_b = market_cap / 1e9 if isinstance(market_cap, (int, float)) else 0

    from src.prompts.analysis_prompts import QUICK_SUMMARY_PROMPT_TEMPLATE

    prompt = QUICK_SUMMARY_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        market_cap_b=market_cap_b,
        pe_ratio=pe_ratio,
    )

    result = generate_content(prompt)
    if result:
        return result.strip()
    return f"{company_name} ({ticker}) - {sector}"
