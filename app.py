"""
AI投資アプリ - メインアプリケーション
Streamlitを使用したダッシュボードUI
サイドバーナビゲーション方式
"""
import streamlit as st
import os
import sys

# パス設定
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.styles import get_custom_css
from src.ui.sidebar import render_sidebar
from src.ui.market_tab import render_market_tab
from src.ui.theme_tab import render_theme_tab
from src.ui.stock_tab import render_stock_tab
from src.ui.portfolio_tab import render_portfolio_tab
from src.ui.alerts_tab import render_alerts_tab

# ページ設定
st.set_page_config(
    page_title="AI投資アプリ",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """セッション状態の初期化"""
    defaults = {
        "gemini_configured": False,
        "market_data": None,
        "option_analysis": None,
        "ai_recap": None,
        "current_page": "market",
        "portfolio_submode": "input",
        "market_type": "US",  # グローバル市場設定
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_error_screen(e):
    """起動エラー時のフォールバック画面を表示"""
    st.error("アプリケーションの起動中にエラーが発生しました。")
    st.code(str(e), language="python")
    st.markdown("""
    ### 対処方法
    1. ページをリロードしてみてください。
    2. 時間を置いて再度アクセスしてください。
    3. 管理者にご連絡ください。
    """)

def main():
    """メイン関数"""
    try:
    try:
        init_session_state()
        
        # --- 設定の即時読み込み（UI描画前）---
        # これによりデータ取得時（キャッシュ含む）にConfigが有効になる
        from src.settings_storage import load_settings, get_gemini_api_key, get_gas_url, get_storage_type, get_finnhub_api_key
        # settings_storageの関数を使ってセッションに同期
        # 1. Gemini
        saved_gen_key = get_gemini_api_key()
        if saved_gen_key and st.session_state.get("gemini_api_key") != saved_gen_key:
             st.session_state.gemini_api_key = saved_gen_key
             st.session_state.gemini_configured = True
        
        # 2. Finnhub
        saved_finn_key = get_finnhub_api_key()
        if saved_finn_key and st.session_state.get("finnhub_api_key") != saved_finn_key:
            st.session_state.finnhub_api_key = saved_finn_key
        
        # 3. GAS / Storage
        saved_gas = get_gas_url()
        if saved_gas and st.session_state.get("gas_url") != saved_gas:
             st.session_state.gas_url = saved_gas
             
        saved_storage = get_storage_type()
        if st.session_state.get("storage_type") != saved_storage:
             st.session_state.storage_type = saved_storage
        
        # -----------------------------------
        
        # スタイルの適用
        st.markdown(get_custom_css(), unsafe_allow_html=True)
        
        # サイドバー描画
        render_sidebar()
        
        # ページルーティング
        page = st.session_state.current_page
        
        if page == "market":
            render_market_tab()
        elif page == "theme":
            render_theme_tab()
        elif page == "stock":
            render_stock_tab()
        elif page == "portfolio":
            render_portfolio_tab()
        elif page == "alerts":
            render_alerts_tab()

    except Exception as e:
        render_error_screen(e)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # main外（インポート時など）のエラーを補足
        # streamlitが初期化されていない可能性もあるためprintも併用
        print(f"Critical Startup Error: {e}")
        try:
            st.error(f"Critical Startup Error: {e}")
        except:
            pass
