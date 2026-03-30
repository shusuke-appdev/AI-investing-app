"""
Option Analysis Component
主要な指数のオプションチェーン分析サマリーを表示します。
"""

import streamlit as st


def render_ticker_compact(opt: dict):
    """個別銘柄のコンパクト表示（ナラティブ形式）"""
    from src.market_data import get_stock_info

    ticker = opt.get("ticker", "N/A")
    sentiment = opt.get("sentiment", "中立")
    pcr = opt.get("pcr", {})
    gex = opt.get("gex", {})
    iv = opt.get("iv")
    max_pain = opt.get("max_pain")

    icon = "🟢" if sentiment == "強気" else "🔴" if sentiment == "弱気" else "⚪"
    stock_info = get_stock_info(ticker)
    current_price = stock_info.get("current_price", 0)

    with st.container(border=True):
        if current_price:
            st.markdown(
                f"**{icon} {ticker}** &#36;{current_price:,.2f}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"**{icon} {ticker}**")

        net_gex = gex.get("nearby_net_gex", 0) if gex else 0

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

        c3, c4 = st.columns(2)
        with c3:
            st.markdown(
                f"<small>IV(ATM)</small><br><strong>{iv:.1%}</strong>" if iv else "-",
                unsafe_allow_html=True,
            )
        with c4:
            if max_pain:
                st.markdown(
                    f"<small>Max Pain</small><br><strong>&#36;{max_pain:.0f}</strong>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("-", unsafe_allow_html=True)

        st.divider()

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

        if iv and iv > 0.2:
            narrative += f" IVは{iv:.1%}とやや高まっており警戒が必要です。"

        if max_pain:
            narrative += f" **Max Painは&#36;{max_pain:.0f}**に位置しており、SQに向けて意識される可能性があります。"

        st.caption(narrative, unsafe_allow_html=True)

        if gex:
            p_wall = (gex.get("positive_wall") or {}).get("strike")
            n_wall = (gex.get("negative_wall") or {}).get("strike")
            walls = []
            if p_wall:
                walls.append(f"+Wall &#36;{p_wall:,.0f}")
            if n_wall:
                walls.append(f"-Wall &#36;{n_wall:,.0f}")
            if walls:
                st.caption(f"抵抗帯: {', '.join(walls)}", unsafe_allow_html=True)


def render_option_analysis(market_type: str = "US"):
    """オプション分析（コンパクト版）表示"""
    st.markdown("### 📊 オプション分析 (詳細)")

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

        fetched_at = option_analysis[0].get("fetched_at") if option_analysis else None
        if fetched_at:
            st.caption(f"データ取得日時: {fetched_at}")

    if not option_analysis:
        st.warning(
            "⚠️ オプションデータを取得できませんでした（SPY, QQQ, IWM 全て失敗）\n\n"
            "**考えられる原因:**\n"
            "- Finnhub無料プランではオプションAPI非対応 (403)\n"
            "- yfinance (Yahoo Finance) が一時的にアクセス制限中\n\n"
            "詳細はアプリログを確認してください。"
        )
        return

    bullish = sum(1 for o in option_analysis if o.get("sentiment") == "強気")
    bearish = sum(1 for o in option_analysis if o.get("sentiment") == "弱気")

    if bearish > bullish:
        st.error("🔴 **全体: 弱気** — ヘッジ需要強まる")
    elif bullish > bearish:
        st.success("🟢 **全体: 強気** — アップサイド期待")
    else:
        st.info("⚪ **全体: 中立** — 方向感模索中")

    cols = st.columns(len(option_analysis))
    for i, opt in enumerate(option_analysis):
        with cols[i]:
            render_ticker_compact(opt)
