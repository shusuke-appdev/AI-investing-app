"""
Portfolio Advisor Tab Module
ポートフォリオ管理、分析、可視化、AIアドバイスを提供します。

サイドバーのサブモードに応じて表示を切り替えます:
- input: 入力・管理
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
    elif submode == "advice":
        _render_advice_section()


def _render_input_section():
    """入力・管理セクション"""
    # Lazy imports
    from src.ui.portfolio_input import (
        render_file_import,
        render_manual_input,
        render_portfolio_manager,
        render_save_portfolio,
        render_saved_portfolios,
        render_text_paste,
    )

    if "portfolio_input_mode" not in st.session_state:
        st.session_state.portfolio_input_mode = "manage"

    # 階層化UIによる入力方式の選択
    st.markdown("### ⚙️ 入力・管理メニュー")
    main_action = st.radio(
        "操作を選択",
        options=["📊 ポートフォリオ管理", "➕ 新規入力", "📁 データ読込"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if main_action == "📊 ポートフォリオ管理":
        mode = "manage"
    elif main_action == "➕ 新規入力":
        sub_action = st.radio(
            "入力方法", options=["✏️ 手動", "📋 貼付"], horizontal=True
        )
        mode = "manual" if sub_action == "✏️ 手動" else "paste"
    else:  # 📁 データ読込
        sub_action = st.radio(
            "読込方法",
            options=["📁 ファイル", "💾 保存済みポートフォリオ"],
            horizontal=True,
        )
        mode = "file" if sub_action == "📁 ファイル" else "saved"

    st.session_state.portfolio_input_mode = mode

    st.divider()

    # 入力モードに応じた表示
    holdings = []

    if mode == "manage":
        holdings = render_portfolio_manager()
    elif mode == "manual":
        holdings = render_manual_input()
    elif mode == "paste":
        holdings = render_text_paste()
    elif mode == "file":
        holdings = render_file_import()
    elif mode == "saved":
        holdings = render_saved_portfolios()

    if not holdings:
        st.info("💡 ポートフォリオを入力してください")
        return

    # 保存機能
    render_save_portfolio(holdings)


def _render_analysis_section():
    """分析・可視化セクション"""
    # Lazy imports
    from src.ui.portfolio_analysis import render_analysis_results
    from src.ui.portfolio_views import (
        render_comparison_view,
        render_history_view,
    )

    analysis = st.session_state.get("portfolio_analysis")

    if not analysis:
        st.info("📈 「入力・管理」でポートフォリオを入力し、分析を実行してください")
        if st.button("← 入力・管理に戻る"):
            st.session_state.portfolio_submode = "input"
            st.rerun()
        return

    # 分析サブタブ
    analysis_tabs = st.tabs(["📊 構成分析", "📈 資産推移", "⚖️ ポートフォリオ比較"])

    with analysis_tabs[0]:
        render_analysis_results(analysis)

    with analysis_tabs[1]:
        render_history_view()

    with analysis_tabs[2]:
        render_comparison_view()


def _render_advice_section():
    """AIアドバイスセクション"""
    # Lazy imports
    from src.portfolio_advisor import generate_portfolio_advice

    st.markdown("### 🤖 AIアドバイス")

    analysis = st.session_state.get("portfolio_analysis")

    if not analysis:
        st.info("📊 先にポートフォリオを分析してからAIアドバイスを受けてください")
        if st.button("← 入力・管理に戻る"):
            st.session_state.portfolio_submode = "input"
            st.rerun()
        return

    # ポートフォリオサマリー表示
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

    st.divider()

    # AIアドバイス生成
    if st.button(
        "📝 AIアドバイスを生成（マクロ分析含む）",
        use_container_width=True,
        type="primary",
    ):
        if not st.session_state.get("gemini_configured"):
            st.warning("⚠️ Gemini APIキーを設定してください")
        else:
            with st.spinner("マクロ環境を分析中..."):
                # マーケットセンチメント取得
                market_sentiment = "中立"
                opt = st.session_state.get("option_analysis")
                if opt:
                    bullish = sum(1 for o in opt if o.get("sentiment") == "強気")
                    bearish = sum(1 for o in opt if o.get("sentiment") == "弱気")
                    if bearish > bullish:
                        market_sentiment = "弱気"
                    elif bullish > bearish:
                        market_sentiment = "強気"

                # オプション分析サマリー
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

    # 生成済みアドバイスの表示
    if st.session_state.get("portfolio_advice"):
        with st.container(border=True):
            st.markdown(st.session_state.portfolio_advice)
