"""
Portfolio History Graph Component
ポートフォリオ評価額推移グラフを描画します。
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_provider import DataProvider
from src.market_data import get_stock_info
from src.portfolio_history import get_value_series


def render_history_graph(portfolio_name: str, holdings_data: list) -> None:
    """上部の評価額推移グラフを描画"""
    dates, values = get_value_series(portfolio_name, 30)

    current_val = 0.0
    total_cost = 0.0

    # 現在の合計評価額と取得原価の計算
    for h in holdings_data:
        info = get_stock_info(h["ticker"])
        quote = DataProvider.get_quote(h["ticker"]) or {}
        price = quote.get("c") or info.get("current_price") or 0.0
        shares = h["shares"]
        current_val += price * shares

        avg_cost = h.get("avg_cost")
        if avg_cost and avg_cost > 0:
            total_cost += avg_cost * shares
        else:
            total_cost += (
                price * shares
            )  # 取得価格不明な場合は現在の価格を取得価格として扱い損益を0とする

    total_return_val = current_val - total_cost
    total_return_pct = (total_return_val / total_cost * 100) if total_cost > 0 else 0.0

    # 履歴がない場合、現在の保有株数 × 過去30日の株価推移を仮想的に構成する
    if not dates or len(dates) < 2:
        if not holdings_data:
            st.markdown(
                f"<h1 style='margin-bottom:0px;'>${current_val:,.2f}</h1>",
                unsafe_allow_html=True,
            )
            st.caption("ポートフォリオに銘柄がありません。")
            return

        # 仮想推移を構成
        price_series_list = []
        for h in holdings_data:
            df = DataProvider.get_historical_data(h["ticker"], "1mo")
            if not df.empty and "Close" in df.columns:
                s = df["Close"] * h["shares"]
                s = s.tz_localize(None) if getattr(s.index, "tzinfo", None) else s
                s.name = h["ticker"]
                price_series_list.append(s)

        if price_series_list:
            combined_df = pd.concat(price_series_list, axis=1)
            combined_df = combined_df.ffill().fillna(0)
            combined_val = combined_df.sum(axis=1)

            try:
                dates = [d.strftime("%Y-%m-%d") for d in combined_val.index]
                values = combined_val.tolist()
            except Exception:
                dates = []
                values = []

    if not dates or len(dates) < 2:
        # フォールバック表示
        c1, c2 = st.columns([1, 4])
        with c1:
            st.markdown(
                f"<h1 style='margin-bottom:0px;'>${current_val:,.2f}</h1>",
                unsafe_allow_html=True,
            )
        with c2:
            _render_total_return_header(total_return_val, total_return_pct)
        st.caption(
            "評価額の推移データがありません。スナップショットを記録するとグラフが表示されます。"
        )
        return

    df = pd.DataFrame({"Date": dates, "Value": values})
    fig = go.Figure(
        go.Scatter(
            x=df["Date"],
            y=df["Value"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#1a73e8", width=2),
            fillcolor="rgba(26, 115, 232, 0.1)",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=250,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True),
        hovermode="x unified",
    )

    # リアルタイムの現在の評価額を最終値として優先表示
    prev_val = values[-2] if len(values) > 1 else current_val
    diff = current_val - prev_val
    diff_pct = (diff / prev_val * 100) if prev_val else 0.0

    color = "green" if diff >= 0 else "red"
    bg_color = "rgba(0,128,0,0.1)" if color == "green" else "rgba(255,0,0,0.1)"
    sign = "+" if diff >= 0 else ""

    # ヘッダーレイアウト（評価額 と 総合収益）
    c1, c2 = st.columns([1, 4])
    with c1:
        st.markdown(
            f"<h1 style='margin-bottom:0px;'>${current_val:,.2f}</h1>",
            unsafe_allow_html=True,
        )
    with c2:
        _render_total_return_header(total_return_val, total_return_pct)

    st.markdown(
        f"<span style='color:{color}; font-weight:bold; background-color: {bg_color}; padding: 5px; border-radius: 5px;'>"
        f"{sign}{diff_pct:.2f}% ({sign}${diff:,.2f}) 今日</span>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_total_return_header(total_return_val: float, total_return_pct: float) -> None:
    """ヘッダー横の総合収益表示用"""
    total_color = "green" if total_return_val >= 0 else "red"
    total_sign = "+" if total_return_val >= 0 else ""
    st.markdown(
        f"<div style='margin-top:20px; font-size:1.1rem; color:#555;'>"
        f"総合収益: <span style='color:{total_color}; font-weight:bold;'>{total_sign}${total_return_val:,.2f} ({total_sign}{total_return_pct:.2f}%)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
