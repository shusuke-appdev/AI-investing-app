from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.market_data import get_stock_data, get_stock_info


def render_chart(ticker: str):
    """
    株価チャートを描画します（200日MA対応・3ヶ月表示・出来高付き）
    """

    with st.spinner("データ取得中..."):
        # 200日MA計算のために1年分取得
        df = get_stock_data(ticker, "1y")
        info = get_stock_info(ticker)

    # 現在価格を取得（get_stock_infoの独自キー）
    current_price = info.get("current_price", 0)

    # 前日終値から変動を計算
    prev_close = info.get("prev_close") or info.get("previousClose")

    # 前日終値がない場合、直近のチャートデータから取得
    if not prev_close and not df.empty and len(df) >= 2:
        prev_close = float(df["Close"].iloc[-2])

    change = 0
    change_pct = 0
    if current_price and prev_close:
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

    if current_price:
        # 色の決定
        if change >= 0:
            color = "#22c55e"  # 緑
            arrow = "▲"
        else:
            color = "#ef4444"  # 赤
            arrow = "▼"

        # 価格表示
        st.markdown(
            f"""
        <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
            <span style="font-size: 1.8rem; font-weight: 700;">${current_price:,.2f}</span>
            <span style="font-size: 1.1rem; color: {color}; font-weight: 600;">
                {arrow} ${abs(change):,.2f} ({change_pct:+.2f}%)
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 📈 株価チャート")

    if not df.empty:
        # 移動平均線の計算 (25日, 50日, 100日, 200日)
        df["SMA25"] = df["Close"].rolling(window=25).mean()
        df["SMA50"] = df["Close"].rolling(window=50).mean()
        df["SMA100"] = df["Close"].rolling(window=100).mean()
        df["SMA200"] = df["Close"].rolling(window=200).mean()

        # サブプロット作成 (上が価格、下が出来高)
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
        )

        # 1. ローソク足 (Row 1)
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="株価",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # 2. 移動平均線 (Row 1)
        # SMA25
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA25"],
                name="SMA 25",
                line=dict(color="#2962FF", width=1.5),
                opacity=0.8,
            ),
            row=1,
            col=1,
        )

        # SMA50 (紫)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA50"],
                name="SMA 50",
                line=dict(color="#9b51e0", width=1.5),
                opacity=0.8,
            ),
            row=1,
            col=1,
        )

        # SMA100 (青緑)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA100"],
                name="SMA 100",
                line=dict(color="#00BFA5", width=1.5),
                opacity=0.8,
            ),
            row=1,
            col=1,
        )

        # SMA200
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA200"],
                name="SMA 200",
                line=dict(color="#FF6D00", width=1.5),
                opacity=0.8,
            ),
            row=1,
            col=1,
        )

        # 3. 出来高 (Row 2)
        # 色分け: 前日比プラスなら緑、マイナスなら赤 (簡易的にClose比較で判定)
        # 厳密には (Close - Open) の方がローソク足の色と合うが、一般的には前日比も多い。
        # ここではローソク足に合わせて (Close >= Open) で色分け。
        colors = [
            "#22c55e" if c >= o else "#ef4444" for c, o in zip(df["Close"], df["Open"])
        ]

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="出来高",
                marker_color=colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # 表示範囲の初期設定（直近3ヶ月）
        last_date = df.index[-1]
        start_date = last_date - timedelta(days=90)

        fig.update_layout(
            autosize=True,
            xaxis_title="",
            yaxis_title="価格 ($)",
            yaxis2_title="出来高",
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            height=500,  # 高さを少し増やす
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(range=[start_date, last_date]),  # 初期表示範囲
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        # 休日をスキップ設定（隙間をなくす）
        # fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=["2024-01-01"])]) # 簡易設定
        # 注: rangebreaksは正確な休日リストがないとずれることがあるため、今回はデフォルトのままにする

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("株価データを取得できませんでした")
