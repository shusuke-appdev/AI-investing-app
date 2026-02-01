"""
ニュース分析モジュール
Gemini APIを使用して市場ニュースの要約・分析レポートを生成します。
"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

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
    market_data: dict,
    news_headlines: list[str],
    option_summary: Optional[str] = None
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
    theme_analysis: Optional[str] = None
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
    context_parts = []
    
    # 市場データ
    context_parts.append("【短期変動 (5日)】")
    for name, data in market_data.items():
        if name != "trend_1mo":
            context_parts.append(f"- {name}: {data.get('price', 'N/A')}, 変化: {data.get('change', 0):+.2f}%")
            
    # 中期トレンド (1ヶ月)
    if "trend_1mo" in market_data:
        context_parts.append("\n【中期トレンド (1ヶ月)】")
        for name, data in market_data["trend_1mo"].items():
            context_parts.append(f"- {name}: {data['trend']} ({data['change_1mo']})期間: {data['start_date']}~{data['end_date']}")

    # ニュース
    context_parts.append("\n【ニュースヘッドライン (AI・テック・市場全体)】")
    for news in news_data[:35]: # 件数を少し増やす
        related = f"[{news.get('related_ticker', '')}] " if news.get('related_ticker') else ""
        title = news.get("title", "")
        summary = news.get("summary", "")
        # Summaryがある場合は追加（あまりに長い場合はカットする等の処理も考えられるが、まずはそのまま）
        if summary:
            context_parts.append(f"- {related}{title}\n  (Summary: {summary})")
        else:
            context_parts.append(f"- {related}{title}")
    
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
    
    context = "\n".join(context_parts)
    


    prompt = f"""
ROLE: Elite Hedge Fund Strategist AI.
TASK: Synthesize market data & news into a Deep Market Analysis Report for institutional investors.
OUTPUT LANGUAGE: **JAPANESE** (Professional/Technical tone).

DATA: {context}

GUIDELINES:
1. **High Density**: Maximize specific metrics, growth rates, specs, product names, and proper nouns. usage. No abstract fluff.
2. **Connectivity**: Analyze supply chains (upstream/downstream) and macro links (rates/valuation).
3. **Data-Driven Inference**: Deduce dominant themes from data using your domain knowledge. No hallucinations.

OUTPUT STRUCTURE (STRICTLY FOLLOW):

I. Market Environment & Macro Deep Dive
1. **Market Trends**:
   - **Short (Days)**: Volatility, sector rotation, trends of recent hot themes.
   - **Medium (1 Mo)**: Trend strength, dip-buying pressure, transition of hot investment themes.
   - **Long (YTD/Trend)**: Major trendline deviation, market fundamentals (macro/policy trends).
   - **Options**: Upside/downside risks based on GEX/PCR implication, understanding of market direction and sentiment.
2. **Rates/Credit**: Yields, spreads, funding conditions. changes in yield curve.
3. **Macro**: Fundamentals (Jobs, Inflation, GDP).
4. **Risks**: Policy, Elections, Geopolitics.

II. Growth Ecosystem Structural Analysis (Universal Framework)
Analyze the dominant theme (e.g., AI) identified from data using these 5 lenses:
1. **Core Infra & Innovation**: Dominant compute platforms/infrastructure. Tech roadmap.
2. **Capital Cycle**: Who is spending Capex? Scale & Sustainability. ROI outlook.
3. **Supply Chain Constraints**: Bottlenecks (components, process, power) limiting supply.
4. **Barriers & Geopolitics**: Tech sovereignty, export controls, legal risks.
5. **Diffusion**: Spread to Edge, Robotics, non-tech sectors.

III. Outlook
- Investment Stance (Risk On/Off), Asset Allocation.
- Historical Analogs (critical comprison to past cycles while paying attention to differences)
- Key Catalysts (Upcoming events such as earnings, key metrics, FRB decisions).

FORMAT:
- Tone: Professional, authoritative ("da/dearu").
- Escape dollar signs ($) for LaTeX compatibility.
"""
    
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview") # Use 3 Flash Preview
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
    
    prompt = f"""
以下の企業概要を、投資家向けに日本語で簡潔に要約してください（3-5文程度）。
主な事業内容、競争優位性、注目すべきポイントを含めてください。

銘柄: {ticker}
英語概要:
{english_summary}
"""
    
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return english_summary
