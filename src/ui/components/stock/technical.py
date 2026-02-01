"""
テクニカル分析UIコンポーネント（コンパクト版）
個別銘柄分析画面にテクニカル分析セクションを表示します。
"""
import streamlit as st
from src.advisor.technical import analyze_technical


def render_technical_analysis(ticker: str):
    """テクニカル分析セクションをレンダリング（コンパクト版）"""
    
    with st.spinner("テクニカル分析中..."):
        tech = analyze_technical(ticker, "1y")
    
    if not tech:
        st.warning("テクニカルデータを取得できませんでした")
        return
    
    # === 1行でコンパクトに表示 ===
    st.markdown("#### 📊 テクニカル分析")
    
    # 総合判定の色
    if tech.overall_score > 20:
        score_badge = f"🟢 **{tech.overall_signal}** ({tech.overall_score:+d})"
    elif tech.overall_score < -20:
        score_badge = f"🔴 **{tech.overall_signal}** ({tech.overall_score:+d})"
    else:
        score_badge = f"🟡 **{tech.overall_signal}** ({tech.overall_score:+d})"
    
    # コンパクトな1行表示
    col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1.5])
    
    with col1:
        st.markdown(f"**総合**: {score_badge}")
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
            st.markdown(f"🎯 **買いゾーン内**")
        else:
            st.markdown(f"📍 買いゾーン: ${zone_lower:.0f}-${zone_upper:.0f}")
    
    # === 詳細は折りたたみ ===
    with st.expander("詳細を見る"):
        detail_cols = st.columns(4)
        with detail_cols[0]:
            st.caption(f"MA乖離: {tech.ma_deviation:+.1f}%")
            st.caption(f"BB: {tech.bb_position}")
        with detail_cols[1]:
            st.caption(f"ATR: ${tech.atr:.2f} ({tech.atr_percent:.1f}%)")
            st.caption(f"BB幅: {tech.bb_width:.1f}%")
        with detail_cols[2]:
            st.caption(f"サポート: ${tech.support_price:.2f}")
            st.caption(f"レジスタンス: ${tech.resistance_price:.2f}")
        with detail_cols[3]:
            st.caption(f"逆張りゾーン:")
            st.caption(f"${zone_lower:.2f} - ${zone_upper:.2f}")
