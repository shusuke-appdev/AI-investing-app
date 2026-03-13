"""
Market News Tab Module (formerly Market Intelligence)
Displays flash summary, option analysis, and AI market recap.
This module now acts as a container for separated UI components.
"""

import re

import streamlit as st

from src.log_config import get_logger
from src.ui.components.market.chat import render_market_chat
from src.ui.components.market.flash_summary import render_flash_summary
from src.ui.components.market.option_analysis import render_option_analysis

logger = get_logger(__name__)


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


def render_market_tab():
    """Renders the Market News tab."""
    market_type = st.session_state.get("market_type", "US")
    market_label = "🇯🇵 日本市場" if market_type == "JP" else "🇺🇸 米国市場"

    header_col, btn_col = st.columns([3, 2])
    with header_col:
        st.markdown(f"## 📰 ニュース ({market_label})")
    with btn_col:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 更新", use_container_width=True):
                st.session_state.market_data = None
                st.session_state.option_analysis = None
                st.cache_data.clear()
                st.rerun()
        with c2:
            if st.button("✨ AI分析", type="secondary", use_container_width=True):
                _generate_ai_recap(market_type)

    with st.spinner("市場データを取得中..."):
        if st.session_state.market_data is None:
            from src.market_data import get_market_indices

            st.session_state.market_data = get_market_indices(market_type)
        market_data = st.session_state.market_data

    render_flash_summary(market_data, market_type)

    if st.session_state.get("ai_recap"):
        st.divider()
        with st.container(border=True):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown("### 🤖 AI分析レポート")
            with cols[1]:
                with st.popover("💬 AIに質問", use_container_width=True):
                    render_market_chat()

            safe_recap = re.sub(r"(?<!\\)\$", r"\\$", st.session_state.ai_recap)
            st.markdown(safe_recap)
            if st.button("🔄 再生成", key="regenerate_recap"):
                st.session_state.ai_recap = None
                st.rerun()

    st.divider()
    render_option_analysis(market_type)
