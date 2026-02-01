"""
Backtest Tab Module
Displays strategy selection and backtest results.
"""
import streamlit as st
from src.backtester import (
    run_backtest,
    create_equity_chart,
    format_backtest_summary,
)
from src.strategies import AVAILABLE_STRATEGIES, get_strategy_params

def render_backtest_tab():
    """Renders the Backtest tab."""
    st.markdown("## 🧪 売買戦略 & バックテスト")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("銘柄コード", value="SPY").upper()
        strategy_name = st.selectbox("戦略", list(AVAILABLE_STRATEGIES.keys()))
    
    with col2:
        period = st.selectbox("テスト期間", ["6mo", "1y", "2y", "5y"], index=1)
        initial_cash = st.number_input("初期資金 ($)", value=10000, step=1000)
    
    # 戦略パラメータ
    st.markdown("### ⚙️ 戦略パラメータ")
    params = get_strategy_params(strategy_name)
    
    param_cols = st.columns(len(params)) if params else [st]
    adjusted_params = {}
    
    for i, (param_name, default_value) in enumerate(params.items()):
        with param_cols[i]:
            adjusted_params[param_name] = st.number_input(
                param_name,
                value=default_value,
                step=1
            )
    
    st.divider()
    
    # バックテスト実行
    if st.button("🚀 バックテスト実行", use_container_width=True):
        with st.spinner("バックテスト実行中..."):
            result = run_backtest(
                ticker=ticker,
                strategy_name=strategy_name,
                period=period,
                initial_cash=initial_cash,
                **adjusted_params
            )
        
        if "error" in result:
            st.error(f"エラー: {result['error']}")
        else:
            # 結果表示
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### 📈 資産曲線")
                fig = create_equity_chart(result)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### 📊 サマリー")
                summary = format_backtest_summary(result)
                st.markdown(summary)
