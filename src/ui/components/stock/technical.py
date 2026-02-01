"""
テクニカル分析UIコンポーネント
個別銘柄分析画面にテクニカル分析セクションを表示します。
"""
import streamlit as st
from src.advisor.technical import analyze_technical


def render_technical_analysis(ticker: str):
    """テクニカル分析セクションをレンダリング"""
    st.markdown("### 📊 AIテクニカル分析")
    
    with st.spinner("テクニカル分析を実行中..."):
        tech = analyze_technical(ticker, "1y")
    
    if not tech:
        st.warning("テクニカルデータを取得できませんでした")
        return
    
    # === メインメトリクス ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 総合スコア（色分け）
        score_color = "🟢" if tech.overall_score > 20 else "🔴" if tech.overall_score < -20 else "🟡"
        st.metric(
            label=f"{score_color} 総合スコア",
            value=f"{tech.overall_score:+d}",
            delta=tech.overall_signal
        )
    
    with col2:
        rsi_color = "🟢" if tech.rsi < 30 else "🔴" if tech.rsi > 70 else "⚪"
        st.metric(
            label=f"{rsi_color} RSI (14)",
            value=f"{tech.rsi:.1f}",
            delta=tech.rsi_signal
        )
    
    with col3:
        ma_color = "🟢" if tech.ma_deviation < -5 else "🔴" if tech.ma_deviation > 5 else "⚪"
        st.metric(
            label=f"{ma_color} 50日MA乖離",
            value=f"{tech.ma_deviation:+.1f}%",
            delta=tech.ma_signal
        )
    
    with col4:
        macd_color = "🟢" if tech.macd_signal == "強気" else "🔴" if tech.macd_signal == "弱気" else "⚪"
        st.metric(
            label=f"{macd_color} MACD",
            value=tech.macd_signal,
            delta=tech.ma_trend
        )
    
    # === 詳細情報（2行目）===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        bb_color = "🟢" if "下限" in tech.bb_position else "🔴" if "上限" in tech.bb_position else "⚪"
        st.metric(
            label=f"{bb_color} ボリンジャー",
            value=tech.bb_position,
            delta=f"幅: {tech.bb_width:.1f}%"
        )
    
    with col2:
        st.metric(
            label="📈 サポート",
            value=f"${tech.support_price:.2f}",
            delta=None
        )
    
    with col3:
        st.metric(
            label="📉 レジスタンス",
            value=f"${tech.resistance_price:.2f}",
            delta=None
        )
    
    with col4:
        st.metric(
            label="📊 ATR",
            value=f"${tech.atr:.2f}",
            delta=f"{tech.atr_percent:.1f}%"
        )
    
    # === 逆張り買いゾーン ===
    st.divider()
    
    contrarian_col1, contrarian_col2 = st.columns([2, 1])
    
    with contrarian_col1:
        zone_lower, zone_upper = tech.contrarian_buy_zone
        
        if tech.contrarian_signal == "買い検討ゾーン":
            st.success(f"🎯 **逆張り買い検討ゾーン**: ${zone_lower:.2f} 〜 ${zone_upper:.2f}")
        elif tech.contrarian_signal == "過熱警戒":
            st.error(f"⚠️ **過熱警戒**: 高値掴みに注意")
        else:
            st.info(f"📍 **逆張り買いゾーン**: ${zone_lower:.2f} 〜 ${zone_upper:.2f} (現在は様子見)")
    
    with contrarian_col2:
        # シグナル判定
        signal_box = {
            "買い検討ゾーン": ("success", "🟢 買い検討"),
            "過熱警戒": ("error", "🔴 過熱警戒"),
            "様子見": ("info", "⚪ 様子見")
        }
        box_type, label = signal_box.get(tech.contrarian_signal, ("info", "⚪ 様子見"))
        
        if box_type == "success":
            st.success(label)
        elif box_type == "error":
            st.error(label)
        else:
            st.info(label)
    
    # === 判定サマリー（Expander）===
    with st.expander("📋 テクニカル判定の詳細"):
        st.markdown(f"""
| 指標 | 値 | 判定 |
|------|-----|------|
| RSI (14) | {tech.rsi:.1f} | {tech.rsi_signal} |
| 50日MA乖離率 | {tech.ma_deviation:+.1f}% | {tech.ma_signal} |
| トレンド (20/50/200) | - | {tech.ma_trend} |
| MACD | - | {tech.macd_signal} |
| ボリンジャーバンド | {tech.bb_position} | 幅 {tech.bb_width:.1f}% |
| ATR (14) | ${tech.atr:.2f} | {tech.atr_percent:.1f}% |
| サポート | ${tech.support_price:.2f} | - |
| レジスタンス | ${tech.resistance_price:.2f} | - |

**総合判定**: {tech.overall_signal} (スコア: {tech.overall_score:+d})

**逆張り判定**: {tech.contrarian_signal}
- 買いゾーン: ${tech.contrarian_buy_zone[0]:.2f} 〜 ${tech.contrarian_buy_zone[1]:.2f}
        """)
