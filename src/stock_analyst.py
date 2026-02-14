"""
銘柄分析AIモジュール
テクニカル分析を統合した詳細な銘柄分析を提供します。
"""
from typing import Optional
import streamlit as st
import google.generativeai as genai
from src.advisor.technical import analyze_technical, get_technical_summary_for_ai

from src.constants import GEMINI_MODEL_NAME


def _get_model():
    """モデルインスタンスを取得（session_stateで管理）"""
    if "_stock_analyst_model" not in st.session_state:
        st.session_state["_stock_analyst_model"] = genai.GenerativeModel(GEMINI_MODEL_NAME)
    return st.session_state["_stock_analyst_model"]


def analyze_stock(
    ticker: str,
    stock_info: dict,
    historical_data: Optional[dict] = None,
    news_headlines: Optional[list[str]] = None
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
    model = _get_model()
    
    # 基本情報の抽出
    company_name = stock_info.get("longName", ticker)
    sector = stock_info.get("sector", "不明")
    industry = stock_info.get("industry", "不明")
    market_cap = stock_info.get("marketCap", 0)
    pe_ratio = stock_info.get("trailingPE", "N/A")
    forward_pe = stock_info.get("forwardPE", "N/A")
    price = stock_info.get("currentPrice", stock_info.get("regularMarketPrice", 0))
    target_price = stock_info.get("targetMeanPrice", "N/A")
    
    # テクニカル分析を取得
    technical_summary = get_technical_summary_for_ai(ticker)
    
    # ユーザー参照知識を取得
    from src.knowledge_storage import get_knowledge_for_ai_context
    knowledge_context = get_knowledge_for_ai_context(max_items=5)
    
    # プロンプト構築
    from src.prompts.analysis_prompts import STOCK_ANALYSIS_PROMPT_TEMPLATE
    
    prompt = STOCK_ANALYSIS_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        market_cap=market_cap,
        price=price,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        target_price=target_price,
        technical_summary=technical_summary,
        news_headlines=chr(10).join(news_headlines[:5]) if news_headlines else "ニュースなし",
        knowledge_context=knowledge_context if knowledge_context else "特になし"
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"分析エラー: {str(e)}"


def get_quick_summary(ticker: str, stock_info: dict) -> str:
    """
    銘柄のクイックサマリーを生成します。
    """
    model = _get_model()
    
    company_name = stock_info.get("longName", ticker)
    sector = stock_info.get("sector", "不明")
    market_cap = stock_info.get("marketCap", 0)
    pe_ratio = stock_info.get("trailingPE", "N/A")
    
    from src.prompts.analysis_prompts import QUICK_SUMMARY_PROMPT_TEMPLATE
    
    prompt = QUICK_SUMMARY_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        market_cap=market_cap,
        pe_ratio=pe_ratio
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"{company_name} ({ticker}) - {sector}"
