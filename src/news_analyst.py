"""
ニュース分析モジュール
Gemini APIを使用して市場ニュースの要約・分析レポートを生成します。
"""

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from src.log_config import get_logger

logger = get_logger(__name__)

load_dotenv()

# Gemini APIの初期化
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def configure_gemini(api_key: Optional[str] = None) -> bool:
    """
    Gemini APIを設定します。

    Args:
        api_key: APIキー（省略時はStreamlit secrets/環境変数から取得）

    Returns:
        設定成功時True
    """
    if not GEMINI_AVAILABLE:
        return False

    # 1. 引数で渡された場合
    key = api_key

    # 2. Streamlit Cloud secrets から取得
    if not key:
        try:
            import streamlit as st

            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    # 3. 環境変数から取得
    if not key:
        key = os.getenv("GEMINI_API_KEY")

    if not key:
        return False

    genai.configure(api_key=key)
    return True


def generate_flash_summary(
    market_data: dict, news_headlines: list[str], option_summary: Optional[str] = None
) -> str:
    """
    Flash Summary（速報箇条書き）を生成します。

    Args:
        market_data: 市場指数データ
        news_headlines: ニュースヘッドライン
        option_summary: オプション分析の要約

    Returns:
        フォーマット済みのFlash Summary
    """
    lines = []

    # 指数
    if "S&P 500" in market_data:
        sp = market_data["S&P 500"]
        lines.append(f"■ S&P500 {sp['change']:+.2f}%")
    if "Nasdaq" in market_data:
        nq = market_data["Nasdaq"]
        lines.append(f"■ ナスダック {nq['change']:+.2f}%")

    # 金利
    treasury_line = []
    if "2Y Treasury" in market_data:
        treasury_line.append(f"2y {market_data['2Y Treasury']['price']:.3f}%")
    if "10Y Treasury" in market_data:
        treasury_line.append(f"10y {market_data['10Y Treasury']['price']:.3f}%")
    if "30Y Treasury" in market_data:
        treasury_line.append(f"30y {market_data['30Y Treasury']['price']:.3f}%")
    if treasury_line:
        lines.append(f"■ {', '.join(treasury_line)}")

    # 為替・商品
    fx_commodity = []
    if "USD/JPY" in market_data:
        fx_commodity.append(f"ドル円 {market_data['USD/JPY']['price']:.2f}")
    if "WTI Crude" in market_data:
        fx_commodity.append(f"WTI {market_data['WTI Crude']['change']:+.2f}%")
    if "Bitcoin" in market_data:
        fx_commodity.append(f"₿ {market_data['Bitcoin']['change']:+.2f}%")
    if "Gold" in market_data:
        fx_commodity.append(f"金 {market_data['Gold']['change']:+.2f}%")
    if "Silver" in market_data:
        fx_commodity.append(f"銀 {market_data['Silver']['change']:+.2f}%")
    if "Copper" in market_data:
        fx_commodity.append(f"銅 {market_data['Copper']['change']:+.2f}%")
    if fx_commodity:
        lines.append(f"■ {', '.join(fx_commodity)}")

    # ニュースヘッドライン
    for headline in news_headlines[:8]:
        lines.append(f"■ {headline}")

    return "\n".join(lines)


def generate_market_recap(
    market_data: dict,
    news_data: list[dict],
    option_analysis: list[dict],
    theme_analysis: Optional[str] = None,
) -> str:
    """
    Gemini APIを使用してMarket Recap（ナラティブ解説）を生成します。

    Args:
        market_data: 市場指数データ
        news_data: ニュース記事データ
        option_analysis: オプション分析結果

    Returns:
        ナラティブ形式の市況解説
    """
    if not GEMINI_AVAILABLE:
        return "Gemini APIが利用できません。APIキーを設定してください。"

    # コンテキストの構築
    today_str = datetime.now().strftime("%Y-%m-%d")
    context_parts = [f"【レポート生成日: {today_str}】"]

    # 市場データ（5日変動）
    context_parts.append("【短期変動 (5日)】")
    for name, data in market_data.items():
        if name not in ("trend_1mo", "weekly_performance"):
            context_parts.append(
                f"- {name}: {data.get('price', 'N/A')}, 変化: {data.get('change', 0):+.2f}%"
            )

    # 週次パフォーマンス（アセットクラス横断）
    if "weekly_performance" in market_data:
        context_parts.append("\n【週次パフォーマンス (1週間) - アセットクラス横断】")
        for name, change in market_data["weekly_performance"].items():
            context_parts.append(f"- {name}: {change}")

    # 中期トレンド (1ヶ月)
    if "trend_1mo" in market_data:
        context_parts.append("\n【中期トレンド (1ヶ月)】")
        for name, data in market_data["trend_1mo"].items():
            context_parts.append(
                f"- {name}: {data['trend']} ({data['change_1mo']})期間: {data['start_date']}~{data['end_date']}"
            )

    # ニュース（件数拡大、カテゴリ表示）
    context_parts.append(
        "\n【ニュースヘッドライン (AI・テック・市場・マクロ・コモディティ・暗号資産)】"
    )
    for news in news_data[:60]:  # 60件に拡大
        related = (
            f"[{news.get('related_ticker', '')}] " if news.get("related_ticker") else ""
        )
        category = f"({news.get('category', '')})" if news.get("category") else ""
        source = f"[{news.get('source', '')}]" if news.get("source") else ""
        title = news.get("title", "")
        summary = news.get("summary", "")
        if summary:
            context_parts.append(
                f"- {source}{related}{title} {category}\n  (Summary: {summary[:200]})"
            )
        else:
            context_parts.append(f"- {source}{related}{title} {category}")

    # オプション分析
    if option_analysis:
        context_parts.append("\n【オプション市場構造】")
        for opt in option_analysis:
            ticker = opt.get("ticker", "")
            sentiment = opt.get("sentiment", "")
            analysis = opt.get("analysis", [])
            context_parts.append(f"- {ticker}: {sentiment}")
            for a in analysis:
                context_parts.append(f"  - {a}")

    # テーマ別トレンド
    if theme_analysis:
        context_parts.append(f"\n{theme_analysis}")

    # ユーザー参照知識
    try:
        from src.knowledge_storage import get_knowledge_for_ai_context

        knowledge_context = get_knowledge_for_ai_context(max_items=10)
        if knowledge_context:
            context_parts.append(f"\n{knowledge_context}")
    except Exception as e:
        logger.error(f"Knowledge context error: {e}")

    context = "\n".join(context_parts)

    # 決算データの取得と追加
    earnings_section = ""
    try:
        from src.earnings_data import get_earnings_context_for_recap

        earnings_context = get_earnings_context_for_recap()
        if earnings_context:
            context += f"\n\n{earnings_context}"
            earnings_section = """
### Ⅴ. 主要決算サマリー (Earnings Highlights)
Context: 直近発表された主要企業の決算結果。
- EPS Beat/Miss、サプライズ率を分析
- ガイダンスの強弱と市場反応
- セクター別の決算トレンド
- 決算を受けた株価反応と今後の見通し

*(決算データがない場合、このセクションは省略)*
"""
    except Exception as e:
        logger.error(f"Earnings context error: {e}")

    from src.prompts.analysis_prompts import MARKET_RECAP_PROMPT_TEMPLATE

    prompt = MARKET_RECAP_PROMPT_TEMPLATE.format(
        context=context, today_str=today_str, earnings_section=earnings_section
    )

    try:
        from src.constants import GEMINI_MODEL_NAME

        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"レポート生成エラー: {str(e)}"


def generate_company_summary_ja(ticker: str, english_summary: str) -> str:
    """
    英語の企業概要を日本語に翻訳・要約します。

    Args:
        ticker: 銘柄コード
        english_summary: 英語の企業概要

    Returns:
        日本語の企業概要
    """
    if not GEMINI_AVAILABLE or not english_summary:
        return english_summary

    # APIキーを設定
    from src.settings_storage import get_gemini_api_key

    api_key = get_gemini_api_key()
    if not api_key:
        return english_summary

    genai.configure(api_key=api_key)

    from src.prompts.analysis_prompts import COMPANY_SUMMARY_JA_PROMPT_TEMPLATE

    prompt = COMPANY_SUMMARY_JA_PROMPT_TEMPLATE.format(
        ticker=ticker, english_summary=english_summary
    )

    try:
        from src.constants import GEMINI_MODEL_NAME

        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return english_summary
