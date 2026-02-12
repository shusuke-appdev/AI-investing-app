"""
Market Analyst Service Module
Handles the orchestration of AI market analysis, aggregating data from multiple sources
and generating a comprehensive market report.
"""
import streamlit as st
import pandas as pd
from typing import Optional

from src.market_config import get_market_config
from src.finnhub_client import get_company_news
from src.market_data import get_stock_data
from src.theme_analyst import get_ranked_themes
from src.news_aggregator import get_aggregated_news, merge_with_finnhub_news
from src.news_analyst import generate_market_recap
from src.option_analyst import get_major_indices_options

def generate_market_analysis_report(market_type: str = "US") -> Optional[str]:
    """
    Generates a comprehensive AI market analysis report.
    
    Args:
        market_type: "US" or "JP"
    
    Returns:
        Markdown string of the analysis report, or None if generation failed.
    """
    if not st.session_state.get("gemini_configured"):
        return None

    config = get_market_config(market_type)
    
    # 1. Fetch Company News from Finnhub (using configured targets)
    target_tickers = config.get("ai_analysis_targets", [])
    
    # Limit to top 15 to avoid rate limits/timeouts
    limit_tickers = target_tickers[:15]
    
    finnhub_news = []
    seen_links = set()
    
    for ticker in limit_tickers:
        news_items = get_company_news(ticker)
        for item in news_items[:2]: # Latest 2 items per ticker
            link = item.get("url")
            if link not in seen_links:
                finnhub_news.append(item)
                seen_links.add(link)
    
    # 2. Fetch Macro/Sector News from Google News
    keywords = config.get("news_keywords", [])
    # Convert keywords list to format expected by get_aggregated_news if needed, 
    # but it seems it accepts list or string. Let's pass the list.
    
    gnews_articles = get_aggregated_news(
        categories=["BUSINESS", "TECHNOLOGY"],
        keywords=keywords,
        max_per_source=5,
        market_type=market_type
    )
    
    # 3. Merge News
    all_news = merge_with_finnhub_news(gnews_articles, finnhub_news, max_total=60)
    
    # 4. Market Context (Weekly Performance)
    weekly_performance = {}
    cross_asset_tickers = {
        # Indices
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "Russell 2000": "^RUT",
        "Dow Jones": "^DJI",
        # Bonds
        "TLT (20Y Bond)": "TLT",
        "US 10Y Yield": "^TNX",
        # Commodities
        "Gold": "GC=F",
        "WTI Crude": "CL=F",
        "Copper": "HG=F",
        # Crypto
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        # Forex
        "DXY (Dollar)": "DX-Y.NYB",
        "USD/JPY": "JPY=X",
    }
    
    # For JP market, we might want to adjust this, but cross-asset view is global.
    # Keeping it global is usually fine for macro analysis.
    
    try:
        for name, ticker in cross_asset_tickers.items():
            df = get_stock_data(ticker, period="5d")
            if not df.empty and len(df) >= 2:
                start_price = df["Close"].iloc[0]
                end_price = df["Close"].iloc[-1]
                change_1w = (end_price - start_price) / start_price * 100
                weekly_performance[name] = f"{change_1w:+.2f}%"
    except Exception as e:
        print(f"Weekly performance fetch error: {e}")
    
    # 5. Market Context (Monthly Trend)
    trend_context = {}
    try:
        indices = {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Russell 2000": "^RUT"}
        for name, ticker in indices.items():
            df = get_stock_data(ticker, period="1mo")
            if not df.empty and len(df) > 1:
                start_price = df["Close"].iloc[0]
                end_price = df["Close"].iloc[-1]
                change_1mo = (end_price - start_price) / start_price * 100
                
                trend = "上昇" if change_1mo > 2 else "下落" if change_1mo < -2 else "横ばい"
                trend_context[name] = {
                    "change_1mo": f"{change_1mo:+.2f}%",
                    "trend": trend,
                    "start_date": df.index[0].strftime("%Y-%m-%d"),
                    "end_date": df.index[-1].strftime("%Y-%m-%d")
                }
    except Exception as e:
        print(f"Trend fetch error: {e}")

    # 6. Theme Analysis
    theme_str_parts = ["【テーマ別トレンド分析 (資金循環)】"]
    try:
        # Short (5 days)
        short_themes = get_ranked_themes("5日")
        if short_themes:
            top5_s = [f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[:5]]
            bot5_s = [f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[-5:]]
            theme_str_parts.append(f"- 短期(5日) Top5: {', '.join(top5_s)}")
            theme_str_parts.append(f"- 短期(5日) Bottom5: {', '.join(bot5_s)}")
        
        # Medium (1 month)
        med_themes = get_ranked_themes("1ヶ月")
        if med_themes:
            top5_m = [f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[:5]]
            bot5_m = [f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[-5:]]
            if top5_m: theme_str_parts.append(f"- 中期(1ヶ月) Top5: {', '.join(top5_m)}")
            if bot5_m: theme_str_parts.append(f"- 中期(1ヶ月) Bottom5: {', '.join(bot5_m)}")
            
    except Exception as e:
        print(f"Theme data fetch error: {e}")
        theme_str_parts.append("- テーマデータの取得に失敗しました")
        
    theme_analysis_str = "\n".join(theme_str_parts)

    # 7. Prepare Market Data for Prompt
    # We reuse st.session_state.market_data if available for the summary
    market_data = st.session_state.market_data if hasattr(st, "session_state") and "market_data" in st.session_state else {}
    if not market_data:
        market_data = {} # Should query if not present, but usually present when calling this.
        
    market_data["trend_1mo"] = trend_context
    market_data["weekly_performance"] = weekly_performance
    
    # 8. Option Analysis
    option_analysis = st.session_state.option_analysis if hasattr(st, "session_state") and "option_analysis" in st.session_state else []
    if not option_analysis:
         # Try fetching if not in session
         try:
             option_analysis = get_major_indices_options(market_type)
         except Exception:
             option_analysis = []
    
    # 9. Generate Recap
    recap = generate_market_recap(
        market_data,
        all_news,
        option_analysis,
        theme_analysis=theme_analysis_str
    )
    
    return recap
