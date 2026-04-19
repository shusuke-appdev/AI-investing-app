"""
Portfolio Input Module
ポートフォリオ入力・管理およびGoogle Financeライクな機能を提供します。
各UIコンポーネントは components/portfolio/ 配下に分離されています。
"""

import streamlit as st

from src.portfolio_advisor import PortfolioHolding
from src.ui.components.portfolio.highlights import (
    render_earnings_calendar,
    render_highlights,
    render_news,
)
from src.ui.components.portfolio.history_graph import render_history_graph
from src.ui.components.portfolio.holdings_table import (
    render_add_button,
    render_holdings_table,
)


def render_portfolio_manager() -> list[PortfolioHolding]:
    """
    Google Finance風のポートフォリオ管理UI
    上部に評価額推移、下に全幅で銘柄一覧、さらに下部にニュースとハイライトを2カラムで配置
    """
    holdings_data = st.session_state.get("managed_holdings", [])
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")

    # 1. Top Graph (Asset History)
    render_history_graph(current_name, holdings_data)

    st.markdown("---")

    # 2. Holdings Table (Full Width)
    render_holdings_table(holdings_data)

    # 3. Add Button
    render_add_button(holdings_data, current_name)

    st.markdown("---")

    # 4. News and Highlights (2-Column Layout)
    if holdings_data:
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("### 📰 ニュースとイベント")
            render_news([h["ticker"] for h in holdings_data])
            render_earnings_calendar([h["ticker"] for h in holdings_data])
        with col_right:
            render_highlights(holdings_data)

    return [PortfolioHolding(**h) for h in holdings_data if h["shares"] > 0]
