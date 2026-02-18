"""
Portfolio Analysis Module
ポートフォリオ分析・可視化機能を提供します。
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.portfolio_advisor import (
    PortfolioHolding,
    analyze_portfolio,
    generate_portfolio_advice,
)


def run_analysis(holdings: list[PortfolioHolding]):
    """分析を実行して結果を表示"""
    with st.spinner("ポートフォリオを分析中..."):
        analysis = analyze_portfolio(holdings)

    if not analysis["holdings"]:
        st.error("分析に失敗しました")
        return

    # セッションに保存（他機能との連携用）
    st.session_state.portfolio_analysis = analysis

    # === サマリー ===
    st.markdown("### 📈 ポートフォリオ概要")

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

    # === 可視化 ===
    render_portfolio_charts(analysis)

    st.divider()

    # === 銘柄別分析 ===
    st.markdown("### 📊 銘柄別分析")

    for h in analysis["holdings"]:
        render_holding_card(h)

    st.divider()

    # === AIアドバイス ===
    render_ai_advice(analysis)


def render_portfolio_charts(analysis: dict):
    """ポートフォリオの可視化チャート"""
    st.markdown("### 📉 ポートフォリオ構成")

    holdings = analysis["holdings"]

    tab1, tab2, tab3 = st.tabs(["銘柄別", "セクター別", "テーマ別"])

    with tab1:
        df = pd.DataFrame(
            [
                {"銘柄": h["ticker"], "評価額": h["value"], "比率": h["weight"]}
                for h in holdings
            ]
        )

        fig = px.pie(
            df,
            values="評価額",
            names="銘柄",
            title="銘柄別構成比率",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=True, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        sector_data = {}
        for h in holdings:
            sector = h.get("sector", "不明")
            sector_data[sector] = sector_data.get(sector, 0) + h["value"]

        df_sector = pd.DataFrame(
            [{"セクター": k, "評価額": v} for k, v in sector_data.items()]
        )

        fig = px.bar(
            df_sector,
            x="セクター",
            y="評価額",
            title="セクター別配分",
            color="セクター",
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        render_theme_exposure(holdings)


def render_theme_exposure(holdings: list[dict]):
    """テーマ別エクスポージャー表示"""
    try:
        from themes_config import THEMES
    except ImportError:
        st.info("テーマ設定が見つかりません")
        return

    theme_exposure = {}

    for h in holdings:
        ticker = h["ticker"]
        value = h["value"]

        for theme_name, theme_tickers in THEMES.items():
            if ticker in theme_tickers:
                theme_exposure[theme_name] = theme_exposure.get(theme_name, 0) + value

    if not theme_exposure:
        st.info("保有銘柄に該当するテーマがありません")
        return

    sorted_themes = sorted(theme_exposure.items(), key=lambda x: x[1], reverse=True)[
        :10
    ]

    df_theme = pd.DataFrame(
        [{"テーマ": k, "エクスポージャー": v} for k, v in sorted_themes]
    )

    fig = px.bar(
        df_theme,
        y="テーマ",
        x="エクスポージャー",
        title="テーマ別エクスポージャー (上位10)",
        orientation="h",
        color="エクスポージャー",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render_holding_card(holding: dict):
    """銘柄カードを表示"""
    tech = holding.get("technical")

    if tech:
        icon = (
            "🟢"
            if tech.overall_signal == "強気"
            else "🔴"
            if tech.overall_signal == "弱気"
            else "⚪"
        )
    else:
        icon = "⚪"

    with st.expander(
        f"{icon} **{holding['ticker']}** - {holding['name']} ({holding['weight']:.1f}%)",
        expanded=False,
    ):
        cols = st.columns(4)

        with cols[0]:
            st.metric("現在価格", f"${holding['current_price']:.2f}")
        with cols[1]:
            st.metric("評価額", f"${holding['value']:,.0f}")
        with cols[2]:
            if holding.get("pnl_pct") is not None:
                st.metric("損益", f"{holding['pnl_pct']:+.1f}%")
            else:
                st.metric("損益", "-")
        with cols[3]:
            if tech:
                st.metric("RSI", f"{tech.rsi:.1f}", delta=tech.rsi_signal)
            else:
                st.metric("RSI", "N/A")

        if tech:
            st.markdown(f"""
            **テクニカル分析**: {tech.overall_signal} (スコア: {tech.overall_score:+d})
            - RSI: {tech.rsi:.1f} ({tech.rsi_signal}) | MA乖離: {tech.ma_deviation:+.1f}% | MACD: {tech.macd_signal}
            """)


def render_ai_advice(analysis: dict):
    """AIアドバイスセクション"""
    st.markdown("### 🤖 AIアドバイス")

    if st.button("📝 AIアドバイスを生成（マクロ分析含む）", use_container_width=True):
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
                st.markdown(advice)


def render_analysis_results(analysis: dict):
    """分析結果の表示（構成分析タブ用）"""
    render_portfolio_charts(analysis)

    st.divider()

    st.markdown("### 📊 銘柄別詳細")

    for h in analysis["holdings"]:
        render_holding_card(h)
