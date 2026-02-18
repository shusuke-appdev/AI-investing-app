"""
テクニカル分析UIコンポーネント（Phase 1/2 拡張版）
個別銘柄分析画面にテクニカル分析セクションを表示します。
"""

import streamlit as st

from src.advisor.technical import analyze_technical


def render_technical_analysis(ticker: str) -> None:
    """テクニカル分析セクションをレンダリング"""

    with st.spinner("テクニカル分析中..."):
        tech = analyze_technical(ticker, "1y")

    if not tech:
        st.warning("テクニカルデータを取得できませんでした")
        return

    st.markdown("#### 📊 テクニカル分析")
    _render_score_row(tech)

    with st.expander("詳細を見る"):
        _render_detail_section(tech)


def _render_score_row(tech) -> None:
    """総合スコアとコア指標の1行表示"""
    if tech.overall_score > 20:
        badge = f"🟢 **{tech.overall_signal}** ({tech.overall_score:+d})"
    elif tech.overall_score < -20:
        badge = f"🔴 **{tech.overall_signal}** ({tech.overall_score:+d})"
    else:
        badge = f"🟡 **{tech.overall_signal}** ({tech.overall_score:+d})"

    col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1.5])

    with col1:
        st.markdown(f"**総合**: {badge}")
    with col2:
        rsi_icon = "🟢" if tech.rsi < 30 else "🔴" if tech.rsi > 70 else "⚪"
        st.markdown(f"**RSI**: {rsi_icon} {tech.rsi:.0f}")
    with col3:
        st.markdown(f"**MACD**: {tech.macd_signal}")
    with col4:
        st.markdown(f"**トレンド**: {tech.ma_trend}")
    with col5:
        zone_lower, zone_upper = tech.contrarian_buy_zone
        if tech.contrarian_signal == "買い検討ゾーン":
            st.markdown("🎯 **買いゾーン内**")
        else:
            st.markdown(f"📍 買いゾーン: ${zone_lower:.0f}-${zone_upper:.0f}")


def _render_detail_section(tech) -> None:
    """詳細指標の展開表示（Phase 1/2 拡張版）"""
    # --- 基本指標 ---
    st.caption("**基本指標**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption(f"MA乖離: {tech.ma_deviation:+.1f}%")
        st.caption(f"BB: {tech.bb_position}")
    with c2:
        st.caption(f"ATR: ${tech.atr:.2f} ({tech.atr_percent:.1f}%)")
        st.caption(f"BB幅: {tech.bb_width:.1f}%")
    with c3:
        st.caption(f"サポート: ${tech.support_price:.2f}")
        st.caption(f"レジスタンス: ${tech.resistance_price:.2f}")
    with c4:
        zone_lower, zone_upper = tech.contrarian_buy_zone
        st.caption("逆張りゾーン:")
        st.caption(f"${zone_lower:.2f} - ${zone_upper:.2f}")

    st.divider()

    # --- Phase 1 高度指標 ---
    st.caption("**高度指標**")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        ichi_icon = (
            "☁️"
            if tech.ichimoku_regime == "in_cloud"
            else "☀️"
            if tech.ichimoku_regime == "above_cloud"
            else "🌧️"
        )
        st.caption(f"一目: {ichi_icon} {tech.ichimoku_signal}")
        if tech.ichimoku_sannyaku:
            st.caption("✨ 三役好転")
    with h2:
        slope_map = {
            "bottoming": "⬆️底打ち",
            "topping": "⬇️天井",
            "rising": "↗上昇",
            "falling": "↘下降",
            "neutral": "→横",
        }
        st.caption(
            f"MACD Hist: {slope_map.get(tech.macd_hist_slope, tech.macd_hist_slope)}"
        )
        st.caption(
            f"ゼロライン: {'上' if tech.macd_zero_filter == 'above_zero' else '下'}"
        )
    with h3:
        sq_icon = "🔴" if tech.bb_squeeze else "🟢"
        st.caption(f"BBスクイズ: {sq_icon} {tech.bb_squeeze_signal}")
    with h4:
        st.caption(f"動的RSI: {tech.rsi_dynamic_signal}")
        st.caption(f"レジーム: {tech.rsi_regime}")

    # --- Phase 2 指標 ---
    if tech.avwap_ytd > 0:
        st.divider()
        st.caption("**AVWAP & 需給**")
        v1, v2 = st.columns(2)
        with v1:
            st.caption(
                f"AVWAP(YTD): ${tech.avwap_ytd:.2f} (乖離: {tech.avwap_deviation:+.1f}%)"
            )
        with v2:
            if tech.gex_regime:
                gex_icon = "🛡️" if tech.gex_regime == "positive_gamma" else "⚡"
                st.caption(f"GEX環境: {gex_icon} {tech.gex_regime}")

    # --- Phase 3 パターン認識 ---
    st.divider()
    st.caption("**パターン認識**")
    p1, p2 = st.columns(2)
    with p1:
        pv_map = {
            "higher_highs": "📈 HH/HL (上昇構造)",
            "lower_lows": "📉 LH/LL (下降構造)",
            "range": "↔️ レンジ",
            "unknown": "—",
        }
        st.caption(
            f"極値構造: {pv_map.get(tech.peak_valley_signal, tech.peak_valley_signal)}"
        )
    with p2:
        if tech.candlestick_patterns:
            cdl_label_map = {
                "engulfing": "包み足",
                "hammer": "ハンマー",
                "invertedhammer": "逆ハンマー",
                "morningstar": "明けの明星",
                "eveningstar": "宵の明星",
                "3whitesoldiers": "赤三兵",
                "3blackcrows": "黒三兵",
                "doji": "同事線",
                "shootingstar": "流れ星",
                "hangingman": "首吊り線",
            }
            names = [
                f"{'🟢' if p['signal'] > 0 else '🔴'} {cdl_label_map.get(p['name'], p['name'])}"
                for p in tech.candlestick_patterns
            ]
            st.caption(f"ローソク足: {', '.join(names)}")
        else:
            st.caption("ローソク足: 検出なし")
