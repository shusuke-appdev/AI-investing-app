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


def _render_market_monitor(market_type: str):
    """総合市場監視ダッシュボードの描画"""
    st.markdown("### 🚨 総合市場監視ダッシュボード")

    benchmarks = {"US": "SPY", "JP": "^N225"}
    target_bm = benchmarks.get(market_type, "SPY")

    opt_state = st.session_state.get("option_analysis")

    # 新しい総合評価モジュールの呼び出し
    from src.advisor.market_environment import evaluate_market_environment

    with st.spinner("市場環境を評価中..."):
        evaluation = evaluate_market_environment(market_type, opt_state)

    if "error" in evaluation and evaluation["error"]:
        st.warning(f"市場データ取得エラー: {evaluation['error']}")
        return
    status = evaluation["status"]
    score = evaluation["score"]
    desc = evaluation["description"]
    signals = evaluation["signals"]

    # 総合判断の表示
    st.markdown(f"**監視対象**: `{target_bm}` | **総合判断**: {status}")

    # -1.0 〜 +1.0 を 0.0 〜 1.0 に正規化してプログレスバーに表示
    norm_score = max(0.0, min(1.0, (score + 1.0) / 2.0))
    st.progress(
        norm_score, text=f"総合スコア: {score:+.2f} (範囲: -1.0 〜 +1.0) - {desc}"
    )

    # 詳細な内訳（根拠）の表示
    with st.expander(
        "詳細な評価コンポーネント内訳", expanded=("弱気" in status or "強気" in status)
    ):
        for sig in signals:
            name = sig["name"]
            s = sig["score"]
            w = sig["weight"]
            rat = sig["rationale"]

            # アイコン選択
            ico = "🟢" if s > 0.3 else "🔴" if s < -0.3 else "⚪"
            if s > 0.7:
                ico = "🚀"
            if s < -0.7:
                ico = "🚨"

            st.markdown(f"**{ico} {name}** (Score: `{s:+.2f}`, Weight: `{w:.1f}`)")
            st.caption(f"└ {rat}")


def render_flash_summary(market_data, market_type: str = "US"):
    """Flash Summaryを資産クラス別にボックス化して表示"""
    from src.market_config import get_market_config

    config = get_market_config(market_type)

    # --- 総合市場監視ダッシュボード ---
    _render_market_monitor(market_type)

    st.markdown("### 📌 アセットクラス別サマリー")

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

        # 望ましい表示順: コモディティ (WTI, Gold, Silver) -> FX -> 暗号資産
        categories_to_show = [
            ("commodities", commodities_tickers),
            ("forex", forex_tickers),
            ("crypto", crypto_tickers),
        ]

        for _category_name, valid_tickers in categories_to_show:
            for name, data in market_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                if ticker in valid_tickers:
                    price = data.get("price", 0)
                    change = data.get("change", 0)
                    if "JPY" in name:
                        price_fmt = f"¥{price:.2f}"
                    elif "BTC" in ticker or "ETH" in ticker:
                        price_fmt = f"${price / 1000:.1f}K"
                    elif "GC" in ticker or "Gold" in name or "Silver" in name:
                        price_fmt = (
                            f"${price:,.2f}" if "Silver" in name else f"${price:,.0f}"
                        )
                    else:
                        price_fmt = f"${price:.2f}"
                    render_market_item(name, price_fmt, change)
