"""
Market News Tab Module (formerly Market Intelligence)
Displays flash summary, option analysis, and AI market recap.
"""

import streamlit as st

from src.log_config import get_logger

logger = get_logger(__name__)


def render_market_tab():
    """Renders the Market News tab."""
    # グローバル市場タイプを取得
    market_type = st.session_state.get("market_type", "US")
    market_label = "🇯🇵 日本市場" if market_type == "JP" else "🇺🇸 米国市場"

    # ヘッダーとAIレポートボタンを横並びに配置
    header_col, btn_col = st.columns([4, 1])
    with header_col:
        st.markdown(f"## 📰 ニュース ({market_label})")
    with btn_col:
        if st.button("✨ AI分析", type="secondary", use_container_width=True):
            _generate_ai_recap(market_type)

    with st.spinner("市場データを取得中..."):
        if st.session_state.market_data is None:
            from src.market_data import get_market_indices

            st.session_state.market_data = get_market_indices(market_type)
        market_data = st.session_state.market_data

    _render_flash_summary(market_data, market_type)

    # AIレポートがある場合のみ表示
    if st.session_state.get("ai_recap"):
        st.divider()
        with st.container(border=True):
            st.markdown("### 🤖 AI分析レポート")
            # Generate markdown, escaping dollar signs to prevent LaTeX rendering issues
            import re

            # エスケープされていない$のみをエスケープ（既に\$になっているものは除外）
            safe_recap = re.sub(r"(?<!\\)\$", r"\\$", st.session_state.ai_recap)
            st.markdown(safe_recap)
            if st.button("🔄 再生成", key="regenerate_recap"):
                st.session_state.ai_recap = None
                st.rerun()

    st.divider()
    _render_option_analysis(market_type)


def _generate_ai_recap(market_type: str = "US"):
    """AIレポート生成"""
    if not st.session_state.get("gemini_configured"):
        st.toast("⚠️ Gemini APIキーを設定してください", icon="⚠️")
        return

    with st.spinner("AI分析レポートを生成中... (ニュース取得・分析)"):
        try:
            from src.services.market_analyst_service import (
                generate_market_analysis_report,
            )

            recap = generate_market_analysis_report(market_type)

            if recap:
                st.session_state.ai_recap = recap
                st.rerun()
            else:
                st.error("レポートの生成に失敗しました。")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            logger.error(f"AI Recap Error: {e}")


def _render_flash_summary(market_data, market_type: str = "US"):
    """Flash Summaryを資産クラス別にボックス化して表示"""
    from src.market_config import get_market_config

    config = get_market_config(market_type)

    st.markdown("### 📌 Flash Summary")

    col1, col2, col3 = st.columns(3)

    # 各カテゴリのティッカーセットを作成
    indices_tickers = set(config["indices"].values())
    treasuries_tickers = set(config["treasuries"].values())
    sectors_tickers = set(config.get("sectors", {}).values())
    commodities_tickers = set(config["commodities"].values())
    crypto_tickers = set(config["crypto"].values())
    forex_tickers = set(config["forex"].values())

    # 左カラム: 株式指数 & 債券・金利
    with col1:
        with st.container(border=True):
            st.markdown("**📊 株式指数・金利**")

            # --- 株式指数 ---
            st.caption("主要指数")

            if market_type == "JP":
                # 日本市場: Stooq データは名前で判定
                jp_indices = ["日経平均", "TOPIX"]
                for name in jp_indices:
                    if name in market_data:
                        data = market_data[name]
                        price = data.get("price", 0)
                        change = data.get("change", 0)
                        price_fmt = f"¥{price:,.0f}"
                        _render_market_item(name, price_fmt, change)
            else:
                # 米国市場: ティッカーで判定
                for name, data in market_data.items():
                    if name in ("trend_1mo", "weekly_performance"):
                        continue
                    ticker = data.get("ticker", "")
                    if ticker in indices_tickers:
                        price = data.get("price", 0)
                        change = data.get("change", 0)
                        price_fmt = f"{price:,.0f}"
                        _render_market_item(name, price_fmt, change)

            # --- 債券・金利 ---
            st.caption("債券・金利")
            if market_type == "JP":
                # 日本市場: 金利データは取得不可
                st.caption("※ 日本国債利回りは非対応")
            else:
                for name, data in market_data.items():
                    if name in ("trend_1mo", "weekly_performance"):
                        continue
                    ticker = data.get("ticker", "")
                    if ticker in treasuries_tickers:
                        price = data.get("price", 0)
                        change = data.get("change", 0)
                        _render_market_item(name, f"{price:.2f}%", change)

    # 中央カラム: セクター別指数 (米国のみ)
    with col2:
        with st.container(border=True):
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
                        _render_market_item(name, f"${price:.2f}", change)
                if not found_sectors:
                    st.caption("データ取得中または利用不可")

    # 右カラム: 商品・FX・暗号資産
    with col3:
        with st.container(border=True):
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
                    _render_market_item(name, price_fmt, change)


def _render_market_item(label: str, value: str, change: float):
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


def _render_option_analysis(market_type: str = "US"):
    """オプション分析（コンパクト版）"""
    st.markdown("### 📊 オプション分析 (詳細)")

    # 日本市場ではオプションデータ取得不可
    if market_type == "JP":
        st.warning(
            "🇯🇵 日本市場のオプションデータは現在取得できません（yfinance APIの制約）"
        )
        return

    with st.spinner("オプションデータを取得中..."):
        if st.session_state.option_analysis is None:
            from src.option_analyst import get_major_indices_options

            st.session_state.option_analysis = get_major_indices_options(market_type)
        option_analysis = st.session_state.option_analysis

    if not option_analysis:
        st.info("オプションデータを取得できませんでした")
        return

    # 全体センチメント（コンパクト）
    bullish = sum(1 for o in option_analysis if o.get("sentiment") == "強気")
    bearish = sum(1 for o in option_analysis if o.get("sentiment") == "弱気")

    if bearish > bullish:
        st.error("🔴 **全体: 弱気** — ヘッジ需要強まる")
    elif bullish > bearish:
        st.success("🟢 **全体: 強気** — アップサイド期待")
    else:
        st.info("⚪ **全体: 中立** — 方向感模索中")

    # 各銘柄表示
    cols = st.columns(len(option_analysis))
    for i, opt in enumerate(option_analysis):
        with cols[i]:
            _render_ticker_compact(opt)


def _render_ticker_compact(opt: dict):
    """個別銘柄のコンパクト表示（ナラティブ形式）"""
    from src.market_data import get_stock_info

    ticker = opt.get("ticker", "N/A")
    sentiment = opt.get("sentiment", "中立")
    pcr = opt.get("pcr", {})
    gex = opt.get("gex", {})
    iv = opt.get("iv")
    max_pain = opt.get("max_pain")
    # analysis_points = opt.get("analysis", []) (Unused)

    icon = "🟢" if sentiment == "強気" else "🔴" if sentiment == "弱気" else "⚪"
    stock_info = get_stock_info(ticker)
    current_price = stock_info.get("current_price", 0)

    with st.container(border=True):
        # ヘッダー
        st.markdown(
            f"**{icon} {ticker}** ${current_price:,.2f}"
            if current_price
            else f"**{icon} {ticker}**"
        )

        # 主要指標グリッド
        # pcr_val = pcr.get("volume_pcr", 0) if pcr else 0 (Unused)
        net_gex = gex.get("nearby_net_gex", 0) if gex else 0

        # 1行目: PCR / GEX
        c1, c2 = st.columns(2)
        with c1:
            pcr_vol = pcr.get("volume_pcr", 0) if pcr else 0
            pcr_col = (
                "#ef4444"
                if pcr_vol > 1.2
                else "#10b981"
                if pcr_vol < 0.7
                else "#6b7280"
            )
            st.markdown(
                f"<small>PCR (Vol)</small><br><strong style='color:{pcr_col}'>{pcr_vol:.2f}</strong>",
                unsafe_allow_html=True,
            )
        with c2:
            gex_col = "#10b981" if net_gex > 0 else "#ef4444"
            st.markdown(
                f"<small>Net GEX</small><br><strong style='color:{gex_col}'>{net_gex / 1e6:+.0f}M</strong>",
                unsafe_allow_html=True,
            )

        # 2行目: IV / MaxPain
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(
                f"<small>IV(ATM)</small><br><strong>{iv:.1%}</strong>" if iv else "-",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f"<small>Max Pain</small><br><strong>${max_pain:.0f}</strong>"
                if max_pain
                else "-",
                unsafe_allow_html=True,
            )

        st.divider()

        # ナラティブ分析生成
        # ナラティブ分析生成
        pcr_vol = pcr.get("volume_pcr", 0) if pcr else 0
        narrative = (
            f"現在の**PCR(Vol)は{pcr_vol:.2f}**で、これは{sentiment}を示唆しています。"
        )
        if net_gex > 0:
            narrative += (
                " **正のNet GEX**により急激な値動きは抑制される傾向にあります。"
            )
        else:
            narrative += " **負のNet GEX**によりボラティリティが拡大しやすい状態です。"

        if iv and iv > 0.2:  # IV > 20%
            narrative += f" IVは{iv:.1%}とやや高まっており警戒が必要です。"

        if max_pain:
            narrative += f" **Max Painは${max_pain:.0f}**に位置しており、SQに向けて意識される可能性があります。"

        st.caption(narrative)

        # Wall情報などは補足として
        if gex:
            p_wall = (gex.get("positive_wall") or {}).get("strike")
            n_wall = (gex.get("negative_wall") or {}).get("strike")
            walls = []
            if p_wall:
                walls.append(f"+Wall ${p_wall:,.0f}")
            if n_wall:
                walls.append(f"-Wall ${n_wall:,.0f}")
            if walls:
                st.caption(f"抵抗帯: {', '.join(walls)}")


def _render_detailed_analysis_enhanced(
    opt: dict, pcr_val: float, vol_pcr: float, net_gex: float, price: float
):
    # Old function - logic moved to _render_ticker_compact
    pass
