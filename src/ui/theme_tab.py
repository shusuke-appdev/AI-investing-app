"""
Thematic Trends Tab Module
Displays thematic performance rankings.
"""
import streamlit as st
import pandas as pd
from themes_config import PERIODS
from src.theme_analyst import get_ranked_themes

def render_theme_tab():
    """Renders the Thematic Trends tab."""
    # グローバル市場タイプを取得
    market_type = st.session_state.get("market_type", "US")
    market_label = "🇯🇵 日本市場" if market_type == "JP" else "🇺🇸 米国市場"
    
    st.markdown(f"## 🎯 テーマ別トレンド ({market_label})")
    
    # 期間選択（タブ形式）
    period_names = list(PERIODS.keys())
    tabs = st.tabs(period_names)
    
    for i, tab in enumerate(tabs):
        with tab:
            period = period_names[i]
            # ランキング取得
            with st.spinner(f"{period}のパフォーマンスを計算中..."):
                ranked_themes = get_ranked_themes(period, market_type)
            
            if not ranked_themes:
                st.warning("テーマデータを取得できませんでした")
                continue
            
            # Top 10 & Bottom 10 Split Layout
            col_top, col_bottom = st.columns(2)
            
            # --- Top 10 ---
            with col_top:
                st.markdown(f"### 🏆 Top 10 Winners ({period})")
                top_10 = ranked_themes[:10]
                for rank, theme_data in enumerate(top_10, 1):
                    _render_theme_item(rank, theme_data)

            # --- Bottom 10 ---
            with col_bottom:
                st.markdown(f"### 📉 Top 10 Losers ({period})")
                # Bottom 10 (reverse order for display: Worst 1st)
                bottom_10 = ranked_themes[-10:]
                # Sort explicitly by performance ascending (worst first) just in case
                bottom_10.sort(key=lambda x: x["performance"]) 
                
                for rank, theme_data in enumerate(bottom_10, 1):
                    _render_theme_item(rank, theme_data)


def _render_theme_item(rank: int, theme_data: dict):
    """テーマ項目のレンダリングヘルパー"""
    from themes_config import get_ticker_name
    
    market_type = st.session_state.get("market_type", "US")
    theme_name = theme_data["theme"]
    perf = theme_data["performance"]
    stocks = theme_data["stocks"]
    
    # パフォーマンスによる色分け
    perf_color = "green" if perf >= 0 else "red"
    perf_icon = "📈" if perf >= 0 else "📉"
    
    with st.expander(f"**{rank}. {theme_name}** {perf_icon} :{perf_color}[{perf:+.2f}%]"):
        # 構成銘柄のパフォーマンス
        if stocks:
            st.markdown("**構成銘柄:**")
            # 銘柄名を取得して表示用データを作成
            display_data = []
            for s in stocks:
                ticker = s["ticker"]
                name = get_ticker_name(ticker, market_type)
                # 日本株は「銘柄名 (証券コード)」形式
                if market_type == "JP" and name != ticker:
                    display_name = f"{name} ({ticker.replace('.T', '')})"
                else:
                    display_name = ticker
                display_data.append({
                    "銘柄": display_name,
                    "騰落率": f"{s['performance']:+.2f}%"
                })
            stock_df = pd.DataFrame(display_data)
            st.dataframe(stock_df, use_container_width=True, hide_index=True)
        else:
            st.caption("銘柄データなし")
    

