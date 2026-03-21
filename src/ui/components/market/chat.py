"""
Market Chat Component
AIアシスタントとの市場分析に関するチャットUIコンポーネント。
"""

import streamlit as st

from src.chat_service import get_market_chat_response


def render_market_chat():
    """AIに質問するチャットUI"""
    st.markdown("#### 💬 AIと議論する")
    st.caption("AI分析レポートや現在のニュースについて質問できます")

    if "market_chat_history" not in st.session_state:
        st.session_state.market_chat_history = []

    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.market_chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("質問を入力してください...（例：金利はどう動いてた？）"):
        st.session_state.market_chat_history.append({"role": "user", "content": prompt})
        with chat_container, st.chat_message("user"):
            st.markdown(prompt)

        with chat_container, st.chat_message("assistant"), st.spinner("思考中..."):
                context = st.session_state.get("ai_recap", "")
                response = get_market_chat_response(
                    prompt=prompt,
                    history=st.session_state.market_chat_history,
                    system_context=context,
                )
                st.markdown(response)

        st.session_state.market_chat_history.append(
            {"role": "assistant", "content": response}
        )
        st.rerun()
