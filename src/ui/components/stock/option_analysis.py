"""
オプション分析UIコンポーネント
個別銘柄のオプション市場構造（PCR, GEX, Max Pain, IV）を可視化します。
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.option_analyst import analyze_option_sentiment


def render_option_analysis(ticker: str) -> None:
    """
    指定銘柄のオプション市場分析セクションを描画します。

    Args:
        ticker: 銘柄コード（例: "SPY", "AAPL"）
    """
    st.markdown("### 🎲 オプション市場分析")

    market_type = st.session_state.get("market_type", "US")
    if market_type == "JP":
        st.info("日本株のオプション分析データは現在サポートされていません。")
        return

    with st.spinner(f"{ticker} のオプションデータを分析中..."):
        try:
            analysis = analyze_option_sentiment(ticker)
        except Exception as e:
            st.error(f"データ取得中にエラーが発生しました: {e}")
            return

    if not analysis:
        st.info(
            "オプションデータが見つかりませんでした（非対象銘柄またはデータ不足）。"
        )
        return

    _render_sentiment_metrics(analysis)
    _render_analysis_comments(analysis)
    _render_charts(analysis)


def _render_sentiment_metrics(analysis: dict) -> None:
    """センチメント判定と主要メトリクスを表示します。"""
    st.markdown(f"#### 市場センチメント: **{analysis['sentiment']}**")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        pcr = analysis.get("pcr")
        if pcr:
            st.metric(
                "Put/Call Ratio (OI)",
                f"{pcr['oi_pcr']:.2f}",
                help="1.0超: 弱気 (ヘッジ多), 0.7未満: 強気",
            )
            st.caption(f"Vol PCR: {pcr['volume_pcr']:.2f}")

    with col2:
        gex = analysis.get("gex")
        if gex:
            net_gex = gex["nearby_net_gex"] / 1_000_000
            st.metric(
                "Net GEX (近傍)",
                f"${net_gex:.1f}M",
                delta="正 (抑制)" if net_gex > 0 else "負 (拡大)",
                help="正: ボラ抑制, 負: ボラ拡大",
            )

    with col3:
        max_pain = analysis.get("max_pain")
        if max_pain:
            current_price = analysis.get("current_price", 0)
            delta_str = ""
            if current_price > 0:
                diff_pct = (max_pain - current_price) / current_price * 100
                delta_str = f"{diff_pct:+.1f}% vs 現在値"
            st.metric(
                "Max Pain",
                f"${max_pain:.0f}",
                delta=delta_str if delta_str else None,
                help="オプション売り手が最も利益を得る（株価が収束しやすい）価格",
            )

    with col4:
        iv = analysis.get("iv")
        if iv:
            st.metric(
                "ATM IV",
                f"{iv:.1%}",
                help="At-The-Money のインプライド・ボラティリティ",
            )


def _render_analysis_comments(analysis: dict) -> None:
    """詳細分析コメントをExpander内に表示します。"""
    comments: list[str] = analysis.get("analysis", [])
    if not comments:
        return
    with st.expander("詳細分析コメント", expanded=False):
        for item in comments:
            st.markdown(f"- {item}")


def _render_charts(analysis: dict) -> None:
    """GEXとOI分布チャートをタブ形式で表示します。"""
    gex_data = analysis.get("gex")
    if not gex_data or not gex_data.get("strike_gex"):
        st.caption("チャートデータが取得できませんでした。")
        return

    st.divider()
    tab1, tab2 = st.tabs(["📊 Gamma Exposure (GEX)", "📈 Open Interest 分布"])

    df_gex = pd.DataFrame(gex_data["strike_gex"])
    current_price: float = analysis.get("current_price", 0)
    max_pain: float | None = analysis.get("max_pain")

    # 現在価格 ±15% に絞って表示
    if current_price > 0:
        range_min = current_price * 0.85
        range_max = current_price * 1.15
        df_view = df_gex[
            (df_gex["strike"] >= range_min) & (df_gex["strike"] <= range_max)
        ]
    else:
        df_view = df_gex

    if df_view.empty:
        with tab1:
            st.info("表示範囲内のデータがありません")
        return

    with tab1:
        _draw_gex_chart(df_view, current_price, max_pain)

    with tab2:
        _draw_oi_chart(df_view, current_price)


def _draw_gex_chart(
    df: pd.DataFrame, current_price: float, max_pain: float | None
) -> None:
    """GEX棒グラフを描画します。"""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["strike"],
            y=df["gex"],
            name="GEX",
            marker_color=[
                "rgba(34,197,94,0.8)" if x > 0 else "rgba(239,68,68,0.8)"
                for x in df["gex"]
            ],
        )
    )
    fig.add_vline(
        x=current_price,
        line_dash="dash",
        line_color="white",
        annotation_text="現在値",
    )
    if max_pain:
        fig.add_vline(
            x=max_pain,
            line_dash="dot",
            line_color="yellow",
            annotation_text="Max Pain",
        )
    fig.update_layout(
        title="ストライク別 Gamma Exposure",
        xaxis_title="ストライク価格",
        yaxis_title="GEX ($)",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _draw_oi_chart(df: pd.DataFrame, current_price: float) -> None:
    """OI棒グラフを描画します。"""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["strike"],
            y=df["oi"],
            name="Total OI",
            marker_color="rgba(59,130,246,0.8)",
        )
    )
    fig.add_vline(
        x=current_price,
        line_dash="dash",
        line_color="white",
        annotation_text="現在値",
    )
    fig.update_layout(
        title="ストライク別 Open Interest",
        xaxis_title="ストライク価格",
        yaxis_title="枚数",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
