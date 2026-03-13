"""
Flash Summary Component
マーケットの概況を資産クラス別に表示します。
"""

import streamlit as st


def render_market_item(label: str, value: str, change: float):
    """市場データの1行表示（色分け統一）"""
    color = "#10b981" if change >= 0 else "#ef4444"
    arrow = "↑" if change >= 0 else "↓"
    st.markdown(
        f"""
    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; 
                border-bottom: 1px solid #e5e7eb; font-size: 1rem;">
        <span style="color: #374151; font-weight: 500;">{label}</span>
        <span style="font-weight: 700;">{value}</span>
        <span style="color: {color}; font-weight: 600;">{arrow}{abs(change):.2f}%</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_flash_summary(market_data, market_type: str = "US"):
    """Flash Summaryを資産クラス別にボックス化して表示"""
    from src.market_config import get_market_config

    config = get_market_config(market_type)
    st.markdown("### 📌 Flash Summary")

    # --- FTD (Follow-Through Day) アラート ---
    from src.advisor.minervini_analyzer import detect_follow_through_day
    from src.market_data import get_stock_data

    benchmarks = {"US": "SPY", "JP": "^N225"}
    target_bm = benchmarks.get(market_type, "SPY")
    bm_data = get_stock_data(target_bm, "3mo")

    if bm_data is not None and not bm_data.empty:
        ftd_result = detect_follow_through_day(bm_data)
        if ftd_result.get("is_ftd"):
            st.success(
                f"🚀 **Market Alert:** {target_bm} にて **{ftd_result.get('status')}** (上昇率 {ftd_result.get('pct_change', 0):.2f}%) - 強気相場入りのシグナル点灯"
            )
        elif "ラリー試行中" in ftd_result.get("status", ""):
            st.info(
                f"👀 **Market Alert:** {target_bm} は現在 **{ftd_result.get('status')}** - 出来高を伴う大幅高に要警戒"
            )

    col1, col2, col3 = st.columns(3)
    indices_tickers = set(config["indices"].values())
    treasuries_tickers = set(config["treasuries"].values())
    sectors_tickers = set(config.get("sectors", {}).values())
    commodities_tickers = set(config["commodities"].values())
    crypto_tickers = set(config["crypto"].values())
    forex_tickers = set(config["forex"].values())

    with col1, st.container(border=True):
        st.markdown("**📊 株式指数・金利**")
        st.caption("主要指数")
        if market_type == "JP":
            jp_indices = ["日経平均", "TOPIX"]
            for name in jp_indices:
                if name in market_data:
                    data = market_data[name]
                    price = data.get("price", 0)
                    change = data.get("change", 0)
                    price_fmt = f"¥{price:,.0f}"
                    render_market_item(name, price_fmt, change)
        else:
            for name, data in market_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                if ticker in indices_tickers:
                    price = data.get("price", 0)
                    change = data.get("change", 0)
                    price_fmt = f"{price:,.0f}"
                    render_market_item(name, price_fmt, change)

        st.caption("債券・金利")
        if market_type == "JP":
            st.caption("※ 日本国債利回りは非対応")
        else:
            for name, data in market_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                if ticker in treasuries_tickers:
                    price = data.get("price", 0)
                    change = data.get("change", 0)
                    render_market_item(name, f"{price:.2f}%", change)

    with col2, st.container(border=True):
        st.markdown("**🏭 セクター別指数**")
        if not sectors_tickers:
            st.info("データなし")
        else:
            found_sectors = False
            for name, data in market_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                if ticker in sectors_tickers:
                    found_sectors = True
                    price = data.get("price", 0)
                    change = data.get("change", 0)
                    render_market_item(name, f"${price:.2f}", change)
            if not found_sectors:
                st.caption("データ取得中または利用不可")

    with col3, st.container(border=True):
        st.markdown("**🌍 商品・FX・暗号資産**")
        target_tickers = commodities_tickers | crypto_tickers | forex_tickers
        for name, data in market_data.items():
            if name in ("trend_1mo", "weekly_performance"):
                continue
            ticker = data.get("ticker", "")
            if ticker in target_tickers:
                price = data.get("price", 0)
                change = data.get("change", 0)
                if "JPY" in name:
                    price_fmt = f"¥{price:.2f}"
                elif "BTC" in ticker or "ETH" in ticker:
                    price_fmt = f"${price / 1000:.1f}K"
                elif "GC" in ticker or "Gold" in name:
                    price_fmt = f"${price:,.0f}"
                else:
                    price_fmt = f"${price:.2f}"
                render_market_item(name, price_fmt, change)
