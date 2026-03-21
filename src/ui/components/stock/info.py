import streamlit as st

from src.market_data import get_stock_info, get_stock_news
from src.news_analyst import generate_company_summary_ja


def render_company_overview(ticker: str, info: dict):
    """企業概要を描画"""
    st.markdown("### 🏢 企業概要")

    # 企業名
    st.markdown(
        f"""
    <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); margin-bottom: 0.5rem;">
        {info.get("name", ticker)}
    </div>
    """,
        unsafe_allow_html=True,
    )

    # セクター
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")

    st.markdown(
        f"""
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
    """,
        unsafe_allow_html=True,
    )

    # 自動翻訳サマリー
    summary = info.get("summary") or "情報なし"
    cache_key = f"summary_ja_{ticker}"

    # キャッシュがあればそれを使用
    if cache_key in st.session_state:
        summary = st.session_state[cache_key]
    else:
        # 英語サマリーがあれば翻訳を試行
        if summary and summary != "情報なし" and len(summary) > 10:
            from src.settings_storage import get_gemini_api_key

            api_key = get_gemini_api_key()
            if api_key:
                with st.spinner("日本語に翻訳中..."):
                    try:
                        summary_ja = generate_company_summary_ja(ticker, summary)
                        if summary_ja and len(summary_ja) > 10:
                            st.session_state[cache_key] = summary_ja
                            summary = summary_ja
                    except Exception as e:
                        st.warning(f"翻訳エラー: {e}")

    st.markdown(
        f"""
    <div style="font-size: 1rem; line-height: 1.6; color: var(--color-text-primary);
                background-color: var(--color-bg-secondary); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--color-border);">
        <strong>事業内容:</strong><br>
        {summary[:500] + "..." if len(summary) > 500 else summary}
    </div>
    """,
        unsafe_allow_html=True,
    )


@st.fragment
def render_ai_stock_analysis(ticker: str, info: dict = None):
    """AI銘柄分析ボタン（フル幅版）"""

    if st.button(
        "🤖 AI銘柄分析を実行",
        type="primary",
        use_container_width=True,
        key="ai_analysis_btn",
    ):
        if not st.session_state.get("gemini_configured"):
            st.warning("⚠️ Gemini APIキーを設定してください")
            return

        with st.spinner("テクニカル分析とAI分析を実行中..."):
            from src.stock_analyst import analyze_stock

            if info is None:
                try:
                    info = get_stock_info(ticker)
                except Exception:
                    info = {}

            news = get_stock_news(ticker)
            headlines = [n.get("title", "") for n in (news or [])]

            try:
                analysis = analyze_stock(ticker, info, news_headlines=headlines)
                st.markdown(analysis)
            except Exception as e:
                st.error(f"分析エラー: {e}")


@st.fragment
def render_news_full_width(ticker: str):
    """関連ニュースを横幅いっぱいで描画"""
    st.markdown("### 📰 関連ニュース")

    with st.spinner("ニュースを取得中..."):
        news = get_stock_news(ticker)

    if news:
        # 3列でニュースを表示
        cols = st.columns(3)
        for i, item in enumerate(news[:6]):
            with cols[i % 3]:
                st.markdown(f"**[{item['title']}]({item['link']})**")
                st.caption(f"{item['publisher']} - {item['published']}")
    else:
        st.info("ニュースがありません")


def render_news_and_analysis(ticker: str, info: dict = None):
    """ニュースをフル幅で描画（互換性維持用）"""
    render_news_full_width(ticker)
