import streamlit as st

from src.chat_service import send_message
from src.knowledge_storage import get_knowledge_for_ai_context


def render_chat_component(key_prefix: str = "global", default_context: str = ""):
    """
    AIチャットをボタンの中に格納し、クリックで展開するコンポーネント。

    Args:
        key_prefix: 複数箇所に設置するためのキーのプレフィックス
        default_context: AIに渡すデフォルトの文脈（現在の画面のレポート内容など）
    """
    # チャット履歴をセッションに保持
    session_key = f"chat_messages_{key_prefix}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []

    # Streamlit 1.32.0以降のPopoversを使用
    with st.popover("🤖 AIに質問"):
        st.markdown(f"**Chat (Context: {key_prefix})**")

        # チャット履歴表示エリア
        chat_container = st.container(height=300, border=False)
        with chat_container:
            if not st.session_state[session_key]:
                st.caption("📝 このレポートについて何でも質問してください")
            else:
                for msg in st.session_state[session_key]:
                    if msg["role"] == "user":
                        st.markdown(f"**🧑 You:** {msg['content']}")
                    else:
                        st.markdown(f"**🤖 AI:** {msg['content']}")

        # 入力エリア
        user_input = st.text_area(
            "質問を入力",
            key=f"{key_prefix}_input",
            height=68,
            label_visibility="collapsed",
            placeholder="ここに質問を入力...",
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            send_btn = st.button(
                "📤 送信",
                key=f"{key_prefix}_send",
                use_container_width=True,
                type="primary",
            )
        with col2:
            if st.button("🗑️", key=f"{key_prefix}_clear", use_container_width=True):
                st.session_state[session_key] = []
                st.rerun()

        if send_btn and user_input.strip():
            if not st.session_state.get("gemini_configured"):
                st.warning("⚠️ 設定からGemini APIキーを登録してください")
                return

            st.session_state[session_key].append(
                {"role": "user", "content": user_input}
            )

            with st.spinner("考え中..."):
                knowledge_context = get_knowledge_for_ai_context(max_items=3)
                full_context = (
                    f"{default_context}\n\n[USER KNOWLEDGE]\n{knowledge_context}"
                )

                try:
                    response = send_message(user_input, full_context)
                except Exception as e:
                    response = f"エラーが発生しました: {e}"

            st.session_state[session_key].append(
                {"role": "assistant", "content": response}
            )
            st.rerun()
