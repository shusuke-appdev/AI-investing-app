"""
Sidebar UI module
Manages the sidebar layout, navigation, settings, and AI chat.
"""
import streamlit as st
from datetime import datetime
from src.news_analyst import configure_gemini, generate_market_recap
from src.market_data import get_market_indices
from src.option_analyst import get_major_indices_options
from src.settings_storage import (
    get_gemini_api_key, set_gemini_api_key,
    get_gas_url, set_gas_url,
    get_storage_type, set_storage_type_setting
)
from src.gas_client import configure_gas
from src.portfolio_storage import set_storage_type


# ナビゲーションメニュー定義
PAGES = {
    "market": {"icon": "📰", "name": "ニュース"},
    "theme": {"icon": "🎯", "name": "テーマ別トレンド"},
    "stock": {"icon": "🔍", "name": "個別銘柄分析"},
    "portfolio": {"icon": "💼", "name": "ポートフォリオ"},
    "alerts": {"icon": "🔔", "name": "アラート設定"},
}

# ポートフォリオのサブモード
PORTFOLIO_SUBMODES = {
    "input": {"icon": "📝", "name": "入力・管理"},
    "analysis": {"icon": "📊", "name": "分析・可視化"},
    "advice": {"icon": "🤖", "name": "AIアドバイス"},
}


def render_sidebar():
    """Renders the application sidebar with navigation and AI chat."""
    with st.sidebar:
        st.markdown("## 📈 AI投資アプリ")
        
        # 保存済み設定を読み込み
        _load_saved_settings()
        
        # === ナビゲーション ===
        st.markdown("### 🧭 ナビゲーション")
        
        # 現在のページを取得
        if "current_page" not in st.session_state:
            st.session_state.current_page = "market"
        if "portfolio_submode" not in st.session_state:
            st.session_state.portfolio_submode = "input"
        
        # ナビボタン
        for page_id, page_info in PAGES.items():
            is_active = st.session_state.current_page == page_id
            
            if is_active:
                st.markdown(
                    f"""<div style="background-color: #2563eb; 
                    color: white; padding: 0.75rem 1rem; border-radius: 8px; 
                    margin-bottom: 0.5rem; font-weight: 600;">
                    {page_info['icon']} {page_info['name']}</div>""",
                    unsafe_allow_html=True
                )
                
                # ポートフォリオの場合はサブモードを表示
                if page_id == "portfolio":
                    _render_portfolio_submenu()
            else:
                if st.button(
                    f"{page_info['icon']} {page_info['name']}",
                    key=f"nav_{page_id}",
                    use_container_width=True
                ):
                    st.session_state.current_page = page_id
                    st.rerun()
        
        st.divider()
        
        # === AIチャット（全モード共通）===
        _render_ai_chat()
        
        st.divider()
        
        # === 設定（AIチャットの下）===
        _render_settings()
        
        st.divider()
        st.caption(f"📊 最終更新: {datetime.now().strftime('%H:%M')}")


def _render_portfolio_submenu():
    """ポートフォリオのサブメニュー（ツリー形式）"""
    st.markdown("""
    <style>
    .submenu-item {
        padding: 0.4rem 1rem 0.4rem 2rem;
        margin: 0.2rem 0;
        border-left: 2px solid #3b82f6;
        cursor: pointer;
    }
    .submenu-item:hover {
        background-color: #eff6ff;
    }
    .submenu-active {
        background-color: #dbeafe;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)
    
    for submode_id, submode_info in PORTFOLIO_SUBMODES.items():
        is_active = st.session_state.portfolio_submode == submode_id
        
        if st.button(
            f"{'▸' if not is_active else '▾'} {submode_info['icon']} {submode_info['name']}",
            key=f"sub_{submode_id}",
            use_container_width=True,
            type="tertiary" if not is_active else "secondary"
        ):
            st.session_state.portfolio_submode = submode_id
            st.rerun()


def _load_saved_settings():
    """保存済み設定を読み込み"""
    # Gemini API Key
    saved_api_key = get_gemini_api_key()
    if saved_api_key and not st.session_state.get("gemini_configured"):
        if configure_gemini(saved_api_key):
            st.session_state.gemini_configured = True
    
    # GAS URL
    saved_gas_url = get_gas_url()
    if saved_gas_url and not st.session_state.get("gas_url"):
        st.session_state.gas_url = saved_gas_url
        configure_gas(saved_gas_url)
    
    # Storage Type
    saved_storage = get_storage_type()
    if saved_storage:
        set_storage_type(saved_storage)


def _render_ai_chat():
    """AIチャット機能（サイドバー埋め込み・拡大版）"""
    st.markdown("### 💬 AIチャット")
    
    # チャット履歴の初期化
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # チャット履歴表示エリア（拡大）
    chat_container = st.container(height=280, border=True)
    with chat_container:
        if not st.session_state.chat_messages:
            st.caption("📝 質問を入力してください")
        else:
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    st.markdown(f"**🧑 You:** {msg['content']}")
                else:
                    st.markdown(f"**🤖 AI:** {msg['content']}")
    
    # 入力エリア
    user_input = st.text_area(
        "質問を入力",
        height=80,
        placeholder="市場について質問してください...",
        label_visibility="collapsed",
        key="chat_input_area"
    )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        send_btn = st.button("📤 送信", use_container_width=True, type="primary")
    with col2:
        if st.button("🗑️", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
    
    if send_btn and user_input.strip():
        if not st.session_state.get("gemini_configured"):
            st.warning("⚠️ APIキーを設定してください")
            return
        
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        with st.spinner("考え中..."):
            from src.chat_service import send_message
            context = st.session_state.get("ai_recap", "")
            response = send_message(user_input, context)
        
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        st.rerun()


def _render_settings():
    """設定セクション（API設定 + ストレージ設定統合）"""
    with st.expander("⚙️ 設定", expanded=False):
        # === API設定 ===
        st.markdown("**🔑 API設定**")
        
        saved_api_key = get_gemini_api_key()
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=saved_api_key if saved_api_key else "",
            help="AIレポート生成に必要です"
        )
        
        if api_key and api_key != saved_api_key:
            if configure_gemini(api_key):
                st.session_state.gemini_configured = True
                set_gemini_api_key(api_key)
                st.success("✅ API設定完了（保存済み）")
            else:
                st.error("❌ API設定失敗")
        elif saved_api_key:
            st.caption("✅ 設定済み")
        
        st.markdown("---")
        
        # === ストレージ設定 ===
        st.markdown("**💾 ストレージ設定**")
        
        saved_storage = get_storage_type()
        storage = st.radio(
            "保存先",
            ["local", "gas"],
            format_func=lambda x: "ローカル" if x == "local" else "Google Apps Script",
            index=0 if saved_storage == "local" else 1,
            horizontal=True
        )
        
        if storage != saved_storage:
            set_storage_type(storage)
            set_storage_type_setting(storage)
        
        if storage == "gas":
            saved_gas_url = get_gas_url()
            gas_url = st.text_input(
                "GAS Web App URL",
                value=saved_gas_url if saved_gas_url else "",
                placeholder="https://script.google.com/macros/s/xxx/exec"
            )
            
            if gas_url and gas_url != saved_gas_url:
                st.session_state.gas_url = gas_url
                configure_gas(gas_url)
                set_gas_url(gas_url)
                st.success("✅ GAS設定完了（保存済み）")
            elif saved_gas_url:
                st.caption("✅ 設定済み")
        
        st.markdown("---")
        
        # データ更新ボタン
        if st.button("🔄 データ更新", use_container_width=True):
            _refresh_data()


def _refresh_data():
    """データを更新する"""
    with st.spinner("データ更新中..."):
        st.session_state.market_data = None
        st.session_state.option_analysis = None
        st.session_state.ai_recap = None
        st.cache_data.clear()
        
        st.session_state.market_data = get_market_indices()
        st.session_state.option_analysis = get_major_indices_options()
        
        if st.session_state.get("gemini_configured"):
            news_data = [{"title": "市場データ更新完了"}]
            st.session_state.ai_recap = generate_market_recap(
                st.session_state.market_data,
                news_data,
                st.session_state.option_analysis or []
            )
            st.success("✅ AIレポート生成完了")
    
    st.rerun()
