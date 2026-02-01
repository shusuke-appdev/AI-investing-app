import streamlit as st
from src.market_data import get_stock_news, get_stock_info
from src.news_analyst import generate_company_summary_ja

def render_company_overview(ticker: str, info: dict):
    """企業概要を描画"""
    st.markdown("### 🏢 企業概要")
    
    # 企業名
    st.markdown(f"""
    <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); margin-bottom: 0.5rem;">
        {info.get('name', ticker)}
    </div>
    """, unsafe_allow_html=True)
    
    # セクター
    sector = info.get('sector', 'N/A')
    industry = info.get('industry', 'N/A')
    
    st.markdown(f"""
    <div style="margin-bottom: 1rem;">
        <span style="background-color: var(--color-accent); color: white; padding: 0.25rem 0.5rem; 
                     border-radius: var(--radius-sm); font-size: 0.875rem; margin-right: 0.5rem;">
            {sector}
        </span>
        <span style="background-color: var(--color-neutral); color: white; padding: 0.25rem 0.5rem; 
                     border-radius: var(--radius-sm); font-size: 0.875rem;">
            {industry}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # 自動翻訳サマリー
    summary = info.get("summary", "情報なし")
    cache_key = f"summary_ja_{ticker}"
    
    if cache_key in st.session_state:
        summary = st.session_state[cache_key]
    elif st.session_state.get("gemini_configured") and summary != "情報なし":
        with st.spinner("翻訳中..."):
            try:
                summary_ja = generate_company_summary_ja(ticker, summary)
                st.session_state[cache_key] = summary_ja
                summary = summary_ja
            except Exception:
                pass
    
    st.markdown(f"""
    <div style="font-size: 1rem; line-height: 1.6; color: var(--color-text-primary); 
                background-color: var(--color-bg-secondary); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--color-border);">
        <strong>事業内容:</strong><br>
        {summary[:500] + '...' if len(summary) > 500 else summary}
    </div>
    """, unsafe_allow_html=True)


def render_news_and_analysis(ticker: str, info: dict = None):
    """ニュースとAI分析を描画"""
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📰 関連ニュース")
        with st.spinner("ニュースを取得中..."):
            news = get_stock_news(ticker)
        
        if news:
            for item in news[:5]:
                st.markdown(f"**[{item['title']}]({item['link']})**")
                st.caption(f"{item['publisher']} - {item['published']}")
        else:
            st.info("ニュースがありません")
    
    with col2:
        st.markdown("### 🤖 AI銘柄分析")
        
        if st.button("📊 AI分析を生成", use_container_width=True, type="primary"):
            if not st.session_state.get("gemini_configured"):
                st.warning("⚠️ Gemini APIキーを設定してください")
                return
            
            with st.spinner("分析中..."):
                from src.stock_analyst import analyze_stock
                
                # Use passed info or fetch if None
                if info is None:
                    try:
                        info = get_stock_info(ticker)
                    except:
                        info = {}

                headlines = [n.get("title", "") for n in (news or [])]
                try:
                    analysis = analyze_stock(ticker, info, news_headlines=headlines)
                    st.markdown(analysis)
                except Exception as e:
                    st.error(f"分析中にエラーが発生しました: {e}")
