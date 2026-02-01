import streamlit as st
import plotly.graph_objects as go
from src.market_data import get_stock_data, get_stock_info

def render_chart(ticker: str):
    """株価チャートを描画します（現在価格・変動率付き）"""
    
    with st.spinner("データ取得中..."):
        df = get_stock_data(ticker, "6mo")
        info = get_stock_info(ticker)
    
    # 現在価格を取得（get_stock_infoの独自キー）
    current_price = info.get("current_price", 0)
    
    # 前日終値から変動を計算（データがある場合のみ）
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
        st.markdown(f"""
        <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
            <span style="font-size: 1.8rem; font-weight: 700;">${current_price:,.2f}</span>
            <span style="font-size: 1.1rem; color: {color}; font-weight: 600;">
                {arrow} ${abs(change):,.2f} ({change_pct:+.2f}%)
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("### 📈 株価チャート")
    
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
            xaxis_title="日付",
            yaxis_title="価格 ($)",
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            height=350,
            margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("株価データを取得できませんでした")
