"""
Stock Analysis Tab Module
Coordinator for individual stock analysis components.
Refactored to improve maintainability and separate concerns.
"""
import streamlit as st
from src.market_data import get_stock_info

# Import separated components
from src.ui.components.stock import (
    render_chart,
    render_company_overview,
    render_integrated_metrics,
    render_quarterly_financials_graph,
    render_recent_earnings,
    render_news_full_width,
    render_ai_stock_analysis,
    render_technical_analysis
)

def render_stock_tab():
    """Renders the Stock Analysis tab."""
    st.markdown("## 🔍 個別銘柄分析")
    
    # 銘柄入力
    col_input, _ = st.columns([1, 2])
    with col_input:
        ticker = st.text_input(
            "銘柄コードを入力",
            value="AAPL",
            placeholder="例: AAPL, NVDA, TSLA"
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
