"""
Sidebar UI module
Manages the sidebar layout, navigation, settings, and AI chat.
"""

from datetime import datetime

import streamlit as st

from src.gas_client import configure_gas
from src.market_data import get_market_indices
from src.news_analyst import configure_gemini, generate_market_recap
from src.option_analyst import get_major_indices_options
from src.portfolio_storage import set_storage_type
from src.settings_storage import (
    get_finnhub_api_key,
    get_gas_url,
    get_gemini_api_key,
    get_storage_type,
    set_gas_url,
    set_storage_type_setting,
)

# ナビゲーションメニュー定義
PAGES = {
    "market": {"icon": "📰", "name": "ニュース"},
    "theme": {"icon": "🎯", "name": "テーマ別トレンド"},
    "stock": {"icon": "🔍", "name": "個別銘柄分析"},
    "portfolio": {"icon": "💼", "name": "ポートフォリオ"},
    "knowledge": {"icon": "📚", "name": "参照知識"},
}

# ポートフォリオのサブモード
PORTFOLIO_SUBMODES = {
    "input": {"icon": "📝", "name": "管理"},
    "analysis": {"icon": "📊", "name": "分析"},
}


def render_sidebar():
    """Renders the application sidebar with navigation and AI chat."""
    with st.sidebar:
        st.markdown("## 📈 AI投資アプリ")

        # 保存済み設定を読み込み
        _load_saved_settings()

        # === グローバル市場選択（全機能に影響） ===
        st.markdown("### 🌐 市場")
        if "market_type" not in st.session_state:
            st.session_state.market_type = "US"

        market_options = ["🇺🇸 米国株", "🇯🇵 日本株"]
        current_idx = 0 if st.session_state.market_type == "US" else 1

        market_selection = st.segmented_control(
            "市場選択",
            options=market_options,
            default=market_options[current_idx],
            label_visibility="collapsed",
        )

        new_market = "US" if "米国" in (market_selection or "") else "JP"
        if new_market != st.session_state.market_type:
            st.session_state.market_type = new_market
            # キャッシュをクリアして再取得
            st.cache_data.clear()
            st.rerun()

        st.divider()

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
                    {page_info["icon"]} {page_info["name"]}</div>""",
                    unsafe_allow_html=True,
                )

                # ポートフォリオの場合はサブモードを表示
                if page_id == "portfolio":
                    _render_portfolio_submenu()
            else:
                if st.button(
                    f"{page_info['icon']} {page_info['name']}",
                    key=f"nav_{page_id}",
                    use_container_width=True,
                ):
                    st.session_state.current_page = page_id
                    st.rerun()

        st.divider()

        # === 設定（AIチャットの下）===
        _render_settings()

        st.divider()
        st.caption(f"📊 最終更新: {datetime.now().strftime('%H:%M')}")


def _render_portfolio_submenu():
    """ポートフォリオのサブメニュー（ツリー形式）"""
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )

    for submode_id, submode_info in PORTFOLIO_SUBMODES.items():
        is_active = st.session_state.portfolio_submode == submode_id

        if st.button(
            f"{'▸' if not is_active else '▾'} {submode_info['icon']} {submode_info['name']}",
            key=f"sub_{submode_id}",
            use_container_width=True,
            type="tertiary" if not is_active else "secondary",
        ):
            st.session_state.portfolio_submode = submode_id
            st.rerun()


def _load_saved_settings():
    """保存済み設定を読み込み、セッション状態と同期させる"""
    # Gemini API Key (Secrets / Env only)
    saved_api_key = get_gemini_api_key()
    if saved_api_key and st.session_state.get("gemini_api_key") != saved_api_key:
        st.session_state.gemini_configured = True
        st.session_state.gemini_api_key = saved_api_key
        configure_gemini(saved_api_key)

    # GAS URL
    saved_gas_url = get_gas_url()
    if saved_gas_url and st.session_state.get("gas_url") != saved_gas_url:
        st.session_state.gas_url = saved_gas_url
        configure_gas(saved_gas_url)

    # Storage Type
    saved_storage = get_storage_type()
    if saved_storage:
        current_storage = st.session_state.get("storage_type")
        if current_storage != saved_storage:
            st.session_state.storage_type = saved_storage
            set_storage_type(saved_storage)

    # Finnhub API Key (Secrets / Env only)
    saved_finnhub_key = get_finnhub_api_key()
    if (
        saved_finnhub_key
        and st.session_state.get("finnhub_api_key") != saved_finnhub_key
    ):
        st.session_state.finnhub_api_key = saved_finnhub_key


def _render_settings():
    """設定セクション（API設定 + ストレージ設定統合）"""
    with st.expander("⚙️ 設定", expanded=True):  # 展開しておく
        # === API設定 ===
        st.markdown("**🔑 API設定**")
        st.caption(
            "※ APIキーのUIからの保存機能はセキュリティ向上のため廃止されました。`.env` または `st.secrets` で環境変数を設定してください。"
        )

        from src.settings_storage import get_finnhub_api_key, get_gemini_api_key

        gemini_configured = bool(get_gemini_api_key())
        finnhub_configured = bool(get_finnhub_api_key())

        if gemini_configured:
            st.success("✅ Gemini API: 設定済み (st.secrets または .env)")
        else:
            st.error("❌ Gemini API: 未設定 (AI分析機能が利用できません)")

        if finnhub_configured:
            st.success("✅ Finnhub API: 設定済み (st.secrets または .env)")
        else:
            st.warning("⚠️ Finnhub API: 未設定 (一部データ取得が制限されます)")

        st.markdown("---")

        # === ストレージ設定 ===
        st.markdown("**💾 ストレージ設定**")

        saved_storage = get_storage_type()

        storage_options = ["local", "gas", "supabase"]
        try:
            default_index = storage_options.index(saved_storage)
        except ValueError:
            default_index = 0

        storage = st.radio(
            "保存先",
            storage_options,
            format_func=lambda x: {
                "local": "ローカル",
                "gas": "Google Apps Script",
                "supabase": "Supabase",
            }.get(x, x),
            index=default_index,
            horizontal=True,
        )

        if storage != saved_storage:
            set_storage_type(storage)
            set_storage_type_setting(storage)
            st.rerun()

        if storage == "gas":
            saved_gas_url = get_gas_url()
            gas_url = st.text_input(
                "GAS Web App URL",
                value=saved_gas_url if saved_gas_url else "",
                placeholder="https://script.google.com/macros/s/xxx/exec",
            )

            if gas_url and gas_url != saved_gas_url:
                st.session_state.gas_url = gas_url
                configure_gas(gas_url)
                set_gas_url(gas_url)
                st.success("✅ GAS設定完了（保存済み）")
            elif saved_gas_url:
                st.caption("✅ 設定済み")

        if storage == "supabase":
            from src.supabase_client import get_supabase_client

            if not get_supabase_client():
                st.warning(
                    "⚠️ secrets.toml に SUPABASE_URL と SUPABASE_KEY を設定してください"
                )
            else:
                st.success("✅ Supabase接続OK")

        st.markdown("---")

        # データ更新ボタン
        if st.button("🔄 データ更新", use_container_width=True):
            _refresh_data()


def _refresh_data():
    """データを更新する"""
    with st.spinner("データ更新中..."):
        # セッション状態のリセット
        st.session_state.market_data = None
        st.session_state.option_analysis = None
        st.session_state.ai_recap = None

        # キャッシュの完全クリア
        st.cache_data.clear()

        # データの再取得
        try:
            st.session_state.market_data = get_market_indices(
                st.session_state.get("market_type", "US")
            )
            st.session_state.option_analysis = get_major_indices_options(
                st.session_state.get("market_type", "US")
            )
        except Exception as e:
            st.error(f"データ取得エラー: {e}")

        if st.session_state.get("gemini_configured"):
            news_data = [{"title": "市場データ更新完了"}]
            st.session_state.ai_recap = generate_market_recap(
                st.session_state.market_data,
                news_data,
                st.session_state.option_analysis or [],
            )
            st.success("✅ AIレポート生成完了")

    st.rerun()
