"""
Stock Analysis Tab Module
Coordinator for individual stock analysis components.
Refactored to improve maintainability and separate concerns.
"""
import streamlit as st
# Imports moved inside functions to avoid circular import issues
import streamlit as st

# Components are imported inside render_stock_tab to avoid top-level circular dependencies
# from src.ui.components.stock import ...

def render_stock_tab():
    """Renders the Stock Analysis tab."""
    # グローバル市場タイプを取得
    market_type = st.session_state.get("market_type", "US")
    
    # Lazy imports to prevent circular dependencies
    from src.market_data import get_stock_info
    from src.market_config import get_market_config
    
    # Import separated components locally
    from src.ui.components.stock import (
        render_chart,
        render_company_overview,
        render_integrated_metrics,
        render_quarterly_financials_graph,
        render_recent_earnings,
        render_news_full_width,
        render_ai_stock_analysis,
        render_technical_analysis,
        render_option_analysis
    )
    config = get_market_config(market_type)
    
    default_ticker = config["default_ticker"]
    sample_tickers = ", ".join(config["sample_tickers"][:3])
    market_label = "🇯🇵 日本市場" if market_type == "JP" else "🇺🇸 米国市場"
    
    st.markdown(f"## 🔍 個別銘柄分析 ({market_label})")
    
    # 銘柄入力
    col_input, _ = st.columns([1, 2])
    with col_input:
        ticker = st.text_input(
            "銘柄コードを入力",
            value=default_ticker,
            placeholder=f"例: {sample_tickers}"
        ).upper()
    
    if not ticker:
        st.info("銘柄コードを入力してください")
        return
    
    # 企業情報を取得
    with st.spinner("企業情報を取得中..."):
        info = get_stock_info(ticker)
    
    # === 上段: チャート + 企業概要 ===
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_chart(ticker)
        # チャート下にAI銘柄分析を配置
        render_ai_stock_analysis(ticker, info)
    
    with col2:
        render_company_overview(ticker, info)
    
    st.divider()
    
    # === テクニカル分析セクション ===
    render_technical_analysis(ticker)
    
    st.divider()

    # === オプション分析セクション ===
    render_option_analysis(ticker)
    
    st.divider()
    
    # === 中段: 基本指標（統合・充実版）===
    render_integrated_metrics(info)
    
    st.divider()
    
    # === 下段: 財務情報・決算情報 ===
    st.markdown("### 💰 財務情報・決算")
    tab1, tab2 = st.tabs(["📈 損益計算書 (四半期)", "📋 直近決算サプライズ"])
    
    with tab1:
        render_quarterly_financials_graph(ticker)
    
    with tab2:
        render_recent_earnings(ticker)
    
    st.divider()
    
    # === 最下段: ニュース（横幅いっぱい）===
    render_news_full_width(ticker)
