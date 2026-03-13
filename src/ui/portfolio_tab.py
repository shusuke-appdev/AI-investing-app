"""
Portfolio Advisor Tab Module
ポートフォリオ管理、分析、可視化、AIアドバイスを提供します。

サイドバーのサブモードに応じて表示を切り替えます:
- input: 管理
- analysis: 分析・可視化
- advice: AIアドバイス
"""

import streamlit as st

# Imports moved inside functions to avoid circular import issues


def render_portfolio_tab():
    """Renders the Portfolio Advisor tab based on sidebar submode."""
    st.markdown("## 💼 ポートフォリオアドバイザー")

    # サイドバーで選択されたサブモードに応じて表示
    submode = st.session_state.get("portfolio_submode", "input")

    if submode == "input":
        _render_input_section()
    elif submode == "analysis":
        _render_analysis_section()


def _render_input_section():
    """管理セクション (単一画面・Google Financeライク)"""
    from src.portfolio_storage import delete_portfolio, list_portfolios, load_portfolio
    from src.ui.portfolio_input import render_portfolio_manager

    # ヘッダーUI: ポートフォリオ選択
    portfolios = list_portfolios()
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")

    st.markdown("### 💼 ポートフォリオ")

    # 選択されているポートフォリオが存在しない場合は新規扱いにする
    if current_name not in portfolios and current_name != "新規ポートフォリオ":
        current_name = "新規ポートフォリオ"
        st.session_state.current_portfolio_name = current_name
        st.session_state.managed_holdings = []

    header_col1, header_col2, header_col3 = st.columns([6, 2, 2])
    with header_col1:
        selected = st.pills(
            "ポートフォリオ選択",
            options=portfolios,
            selection_mode="single",
            default=current_name if current_name in portfolios else None,
            label_visibility="collapsed",
        )

        # 別のポートフォリオが選択された場合
        if selected and selected != current_name:
            data = load_portfolio(selected)
            if data:
                st.session_state.managed_holdings = data.get("holdings", [])
                st.session_state.current_portfolio_name = selected
            st.rerun()
        # 選択が解除された場合は「新規ポートフォリオ」画面にする
        elif not selected and current_name != "新規ポートフォリオ":
            st.session_state.managed_holdings = []
            st.session_state.current_portfolio_name = "新規ポートフォリオ"
            st.rerun()

    with header_col2:
        if st.button("＋ 新しいポートフォリオ", use_container_width=True):
            st.session_state.managed_holdings = []
            st.session_state.current_portfolio_name = "新規ポートフォリオ"
            st.rerun()

    with header_col3:
        if current_name != "新規ポートフォリオ":
            if st.button(
                "🗑️ 削除",
                help="ポートフォリオ全体を完全に削除します",
                type="tertiary",
                use_container_width=True,
            ):
                delete_portfolio(current_name)
                st.session_state.managed_holdings = []
                st.session_state.current_portfolio_name = "新規ポートフォリオ"
                st.rerun()

    st.divider()

    # メインの管理画面を描画
    render_portfolio_manager()


def _render_analysis_section():
    """分析・可視化セクション (AIアドバイス統合版)"""
    from src.portfolio_advisor import PortfolioHolding, analyze_portfolio
    from src.ui.portfolio_analysis import render_analysis_results
    from src.ui.portfolio_views import (
        render_comparison_view,
        render_history_view,
    )

    analysis = st.session_state.get("portfolio_analysis")
    holdings_data = st.session_state.get("managed_holdings", [])

    if not holdings_data:
        st.info("📈 先に「ポートフォリオ」画面で銘柄を追加してください")
        if st.button("← ポートフォリオに戻る"):
            st.session_state.portfolio_submode = "input"
            st.rerun()
        return

    # 分析が未実行、または強制再実行ボタンが押された場合
    if not analysis or st.button("🔄 最新の構成で再分析する", type="secondary"):
        with st.spinner("ポートフォリオを分析中..."):
            holdings = [PortfolioHolding(**h) for h in holdings_data if h["shares"] > 0]
            if holdings:
                analysis = analyze_portfolio(holdings)
                st.session_state.portfolio_analysis = analysis
            else:
                st.info("💡 有効な銘柄がありません")
                return

    st.markdown("---")

    # 分析とAIアドバイスサブタブ
    analysis_tabs = st.tabs(
        ["📊 構成分析", "🤖 AIアドバイス", "📈 資産推移", "⚖️ ポートフォリオ比較"]
    )

    with analysis_tabs[0]:
        render_analysis_results(analysis)

    with analysis_tabs[1]:
        # 旧アドバイスセクションのコードをインライン展開
        from src.portfolio_advisor import generate_portfolio_advice

        st.markdown("### 🤖 ポートフォリオへのAIアドバイス")

        with st.container(border=True):
            cols = st.columns(3)
            with cols[0]:
                st.metric("総資産", f"${analysis['total_value']:,.0f}")
            with cols[1]:
                st.metric("銘柄数", analysis["num_holdings"])
            with cols[2]:
                scores = [
                    h["technical"].overall_score
                    for h in analysis["holdings"]
                    if h.get("technical")
                ]
                avg_score = sum(scores) / len(scores) if scores else 0
                st.metric("テクニカルスコア", f"{avg_score:+.0f}")

        if st.button(
            "📝 AIアドバイスを生成（マクロ分析含む）",
            use_container_width=True,
            type="primary",
        ):
            if not st.session_state.get("gemini_configured"):
                st.warning("⚠️ Gemini APIキーを設定してください")
            else:
                with st.spinner("マクロ環境を分析中..."):
                    market_sentiment = "中立"
                    opt = st.session_state.get("option_analysis")
                    if opt:
                        bullish = sum(1 for o in opt if o.get("sentiment") == "強気")
                        bearish = sum(1 for o in opt if o.get("sentiment") == "弱気")
                        if bearish > bullish:
                            market_sentiment = "弱気"
                        elif bullish > bearish:
                            market_sentiment = "強気"

                    option_summary = None
                    if opt:
                        option_summary = "; ".join(
                            [f"{o['ticker']}: {o['sentiment']}" for o in opt[:3]]
                        )

                    advice = generate_portfolio_advice(
                        analysis,
                        market_sentiment=market_sentiment,
                        option_summary=option_summary,
                    )
                    st.session_state.portfolio_advice = advice

        if st.session_state.get("portfolio_advice"):
            with st.container(border=True):
                st.markdown(st.session_state.portfolio_advice)

    with analysis_tabs[2]:
        render_history_view()

    with analysis_tabs[3]:
        render_comparison_view()


# _render_advice_section は削除されました
