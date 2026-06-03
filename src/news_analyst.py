"""
ニュース分析モジュール
Gemini APIを使用して市場ニュースの要約・分析レポートを生成します。
"""

from datetime import datetime

from src.gemini_client import configure_gemini as _configure_gemini
from src.gemini_client import generate_content, get_gemini_client
from src.log_config import get_logger

logger = get_logger(__name__)

# 後方互換: 他モジュールが GEMINI_AVAILABLE と configure_gemini を参照している
GEMINI_AVAILABLE = True


def configure_gemini(api_key: str | None = None) -> bool:
    """後方互換ラッパー: gemini_client.configure_gemini に委譲"""
    return _configure_gemini(api_key)


def generate_flash_summary(
    market_data: dict, news_headlines: list[str], option_summary: str | None = None
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

    # 指数（market_config.py のキー名に合わせる）
    if "S&P 500" in market_data:
        sp = market_data["S&P 500"]
        lines.append(f"■ S&P500 {sp.get('change', 0):+.2f}%")
    if "Nasdaq 100" in market_data:
        nq = market_data["Nasdaq 100"]
        lines.append(f"■ ナスダック {nq.get('change', 0):+.2f}%")

    # 金利（market_config.py のキー名に合わせる）
    treasury_line = []
    if "US 10Y Yield" in market_data:
        treasury_line.append(f"10y {market_data['US 10Y Yield'].get('price', 0):.3f}%")
    if "US 30Y Yield" in market_data:
        treasury_line.append(f"30y {market_data['US 30Y Yield'].get('price', 0):.3f}%")
    if treasury_line:
        lines.append(f"■ {', '.join(treasury_line)}")

    # 為替・商品
    fx_commodity = []
    if "USD/JPY" in market_data:
        fx_commodity.append(f"ドル円 {market_data['USD/JPY'].get('price', 0):.2f}")
    if "WTI Oil" in market_data:
        fx_commodity.append(f"WTI {market_data['WTI Oil'].get('change', 0):+.2f}%")
    if "Bitcoin" in market_data:
        fx_commodity.append(f"₿ {market_data['Bitcoin'].get('change', 0):+.2f}%")
    if "Gold" in market_data:
        fx_commodity.append(f"金 {market_data['Gold'].get('change', 0):+.2f}%")
    if "Silver" in market_data:
        fx_commodity.append(f"銀 {market_data['Silver'].get('change', 0):+.2f}%")
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
    theme_analysis: str | None = None,
    advanced_tech_analysis: str | None = None,
    custom_focus: str | None = None,
) -> str:
    """
    Gemini APIを使用してMarket Recap（ナラティブ解説）を生成します。

    Args:
        market_data: 市場指数データ
        news_data: ニュース記事データ
        option_analysis: オプション分析結果
        theme_analysis: テーマ分析文字列
        advanced_tech_analysis: 高度なテクニカル分析文字列

    Returns:
        ナラティブ形式の市況解説
    """
    if get_gemini_client() is None:
        return "Gemini APIが利用できません。APIキーを設定してください。"

    # コンテキストの構築
    today_str = datetime.now().strftime("%Y-%m-%d")
    context_parts = [f"【レポート生成日: {today_str}】"]

    # 市場データ（5日変動）
    # メタデータキーと非dict値をフィルタして安全にイテレート
    context_parts.append("【短期変動 (5日)】")
    _meta_keys = ("trend_1mo", "weekly_performance", "market_monitor")
    for name, data in market_data.items():
        if name in _meta_keys or not isinstance(data, dict):
            continue
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
    for news in news_data[:20]:  # 負荷軽減のため20件に制限
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
            quality = opt.get("data_quality", "unknown")
            context_parts.append(f"- {ticker}: {sentiment} (data_quality={quality})")
            for warning in opt.get("quality_warnings", [])[:4]:
                context_parts.append(f"  - Data warning: {warning}")
            for a in analysis:
                context_parts.append(f"  - {a}")

    # テーマ別トレンド
    if theme_analysis:
        context_parts.append(f"\n{theme_analysis}")

    # 高度なテクニカル・ボラティリティ分析
    if advanced_tech_analysis:
        context_parts.append(f"\n{advanced_tech_analysis}")

    if custom_focus and custom_focus.strip():
        context_parts.append("\n【ユーザー指定の追加分析項目】")
        context_parts.append(custom_focus.strip()[:2000])

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

    result = generate_content(prompt)
    if result:
        return result
    return "レポート生成エラー: Gemini APIが利用できません"


def generate_company_summary_ja(ticker: str, english_summary: str) -> str:
    """
    英語の企業概要を日本語に翻訳・要約します。
    """
    if not english_summary:
        return english_summary

    from src.prompts.analysis_prompts import COMPANY_SUMMARY_JA_PROMPT_TEMPLATE

    prompt = COMPANY_SUMMARY_JA_PROMPT_TEMPLATE.format(
        ticker=ticker, english_summary=english_summary[:8000]
    )

    result = generate_content(prompt)
    if result:
        return result
    return english_summary
