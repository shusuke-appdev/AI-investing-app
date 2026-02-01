import streamlit as st
import plotly.graph_objects as go
from src.market_data import get_stock_data

def render_chart(ticker: str):
    """株価チャートを描画します"""
    st.markdown("### 📈 株価チャート")
    period = "6mo" # 固定
    
    with st.spinner("データ取得中..."):
        df = get_stock_data(ticker, period)
    
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=ticker
        ))
        fig.update_layout(
            title=f"{ticker} 株価",
            xaxis_title="日付",
            yaxis_title="価格 ($)",
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("株価データを取得できませんでした")
