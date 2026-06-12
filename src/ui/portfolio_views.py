"""
Portfolio Views Module
資産推移、比較などのビュー機能を提供します。
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.portfolio_history import (
    calculate_returns,
    compare_portfolios,
    get_value_series,
    list_portfolios_with_history,
    save_snapshot,
)


def render_history_view():
    """資産推移グラフ表示"""
    st.markdown("### 📈 資産推移")

    portfolios = list_portfolios_with_history()

    if not portfolios:
        st.info(
            "履歴データがありません。ポートフォリオを分析して保存すると履歴が記録されます。"
        )
        return

    selected = st.selectbox("ポートフォリオを選択", portfolios)

    if not selected:
        return

    days = st.slider("表示期間（日）", 7, 365, 30)

    dates, values = get_value_series(selected, days)

    if len(dates) < 2:
        st.warning("履歴データが不足しています（最低2日分必要）")
        return

    # 資産推移チャート
    df = pd.DataFrame({"日付": dates, "資産額": values})

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["日付"],
            y=df["資産額"],
            mode="lines+markers",
            name=selected,
            line=dict(width=2, color="#4CAF50"),
            fill="tozeroy",
            fillcolor="rgba(76, 175, 80, 0.1)",
        )
    )

    fig.update_layout(
        title=f"資産推移: {selected}",
        xaxis_title="日付",
        yaxis_title="資産額 ($)",
        height=400,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # リターン表示
    returns = calculate_returns(selected, days)
    if returns.get("period_return") is not None:
        cols = st.columns(4)
        with cols[0]:
            st.metric("開始時点", f"${returns['start_value']:,.0f}")
        with cols[1]:
            st.metric("現在", f"${returns['end_value']:,.0f}")
        with cols[2]:
            change = returns["end_value"] - returns["start_value"]
            st.metric("変動額", f"${change:+,.0f}")
        with cols[3]:
            st.metric(
                f"{returns['days']}日間リターン", f"{returns['period_return']:+.2f}%"
            )

    # スナップショット保存ボタン
    st.divider()
    st.markdown("#### 💾 現在の状態を記録")

    if st.button("📸 スナップショットを保存", use_container_width=True):
        analysis = st.session_state.get("portfolio_analysis")
        if analysis:
            success = save_snapshot(
                selected, analysis.get("total_value", 0), analysis.get("holdings", [])
            )
            if success:
                st.success("✅ スナップショットを保存しました")
                st.rerun()
            else:
                st.error("保存に失敗しました")
        else:
            st.warning("先にポートフォリオを分析してください")


def render_comparison_view():
    """ポートフォリオ比較表示"""
    st.markdown("### ⚖️ ポートフォリオ比較")

    portfolios = list_portfolios_with_history()

    if len(portfolios) < 2:
        st.info("比較するには2つ以上の履歴データが必要です")
        return

    selected = st.multiselect(
        "比較するポートフォリオを選択（2-5個）",
        portfolios,
        default=portfolios[:2] if len(portfolios) >= 2 else portfolios,
    )

    if len(selected) < 2:
        st.warning("2つ以上選択してください")
        return

    days = st.slider("比較期間（日）", 7, 365, 30, key="compare_days")

    comparison = compare_portfolios(selected, days)

    fig = go.Figure()
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336"]

    for i, pf in enumerate(comparison["portfolios"]):
        if pf["dates"] and pf["normalized"]:
            fig.add_trace(
                go.Scatter(
                    x=pf["dates"],
                    y=pf["normalized"],
                    mode="lines",
                    name=pf["name"],
                    line=dict(width=2, color=colors[i % len(colors)]),
                )
            )

    fig.update_layout(
        title="パフォーマンス比較（開始時点=100）",
        xaxis_title="日付",
        yaxis_title="相対値",
        height=400,
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 📊 比較サマリー")

    summary_data = []
    for pf in comparison["portfolios"]:
        summary_data.append(
            {
                "ポートフォリオ": pf["name"],
                "現在評価額": f"${pf['current_value']:,.0f}"
                if pf["current_value"]
                else "-",
                f"{days}日間リターン": f"{pf['period_return']:+.2f}%"
                if pf.get("period_return") is not None
                else "-",
            }
        )

    st.dataframe(summary_data, use_container_width=True, hide_index=True)
