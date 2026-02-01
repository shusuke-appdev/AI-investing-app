"""
Alerts Tab Module
アラート設定機能を独立したページとして提供します。
"""
import streamlit as st
from src.portfolio_storage import list_portfolios
from src.gas_client import get_gas_client


def render_alerts_tab():
    """Renders the Alerts configuration tab."""
    st.markdown("## 🔔 アラート設定")
    
    gas_client = get_gas_client()
    
    if not gas_client:
        st.warning("⚠️ GAS連携を設定するとアラート機能が使えます")
        st.info("サイドバーの「設定」でGAS Web App URLを入力してください")
        return
    
    # 既存アラート一覧
    _render_existing_alerts(gas_client)
    
    st.divider()
    
    # 新規アラート設定
    _render_new_alert_form(gas_client)
    
    st.divider()
    
    # テストメール
    _render_test_email(gas_client)


def _render_existing_alerts(gas_client):
    """既存アラート一覧"""
    st.markdown("### 📋 設定済みアラート")
    
    try:
        alerts = gas_client.get_alerts()
    except Exception:
        alerts = []
    
    if alerts:
        for alert in alerts:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{alert['portfolio_name']}**")
                    st.caption(f"タイプ: {_format_alert_type(alert['alert_type'])}")
                with col2:
                    st.markdown(f"📧 {alert['email']}")
                    st.caption(f"閾値: {_format_threshold(alert['alert_type'], alert['threshold'])}")
                with col3:
                    st.markdown(f"{'✅ 有効' if alert['enabled'] else '❌ 無効'}")
                    if st.button("🗑️", key=f"del_{alert['portfolio_name']}_{alert['alert_type']}"):
                        if gas_client.delete_alert(alert['portfolio_name'], alert['alert_type']):
                            st.success("削除しました")
                            st.rerun()
    else:
        st.info("設定済みアラートはありません")


def _render_new_alert_form(gas_client):
    """新規アラート設定フォーム"""
    st.markdown("### ➕ 新規アラート設定")
    
    portfolios = list_portfolios()
    
    if not portfolios:
        st.info("先にポートフォリオを保存してください")
        return
    
    with st.form("new_alert_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            portfolio_name = st.selectbox("ポートフォリオ", portfolios)
            email = st.text_input("通知先メールアドレス", placeholder="your@email.com")
        
        with col2:
            alert_type = st.selectbox(
                "アラートタイプ",
                ["daily_change", "value_below", "value_above"],
                format_func=_format_alert_type
            )
            
            if alert_type == "daily_change":
                threshold = st.number_input(
                    "変動率閾値（%）",
                    min_value=0.1,
                    value=5.0,
                    step=0.5,
                    help="日次変動率がこの値を超えるとアラート"
                )
            else:
                threshold = st.number_input(
                    "評価額閾値（$）",
                    min_value=0.0,
                    value=10000.0,
                    step=1000.0,
                    help="評価額がこの値を超える/下回るとアラート"
                )
        
        submitted = st.form_submit_button("🔔 アラートを設定", use_container_width=True, type="primary")
        
        if submitted:
            if not email or "@" not in email:
                st.error("有効なメールアドレスを入力してください")
            else:
                if gas_client.set_alert(portfolio_name, email, alert_type, threshold):
                    st.success(f"✅ アラートを設定しました: {portfolio_name}")
                    st.rerun()
                else:
                    st.error("設定に失敗しました")


def _render_test_email(gas_client):
    """テストメール送信"""
    st.markdown("### 📧 テストメール送信")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        test_email = st.text_input("テスト送信先", placeholder="your@email.com", key="test_email")
    with col2:
        if st.button("📤 送信", use_container_width=True):
            if test_email and "@" in test_email:
                if gas_client.send_alert_email(
                    test_email,
                    "[AI投資アプリ] テストメール",
                    "これはアラート機能のテストメールです。正常に受信できています。"
                ):
                    st.success("✅ テストメールを送信しました")
                else:
                    st.error("送信に失敗しました")
            else:
                st.warning("有効なメールアドレスを入力してください")


def _format_alert_type(alert_type: str) -> str:
    """アラートタイプを日本語表示"""
    mapping = {
        "daily_change": "日次変動率",
        "value_below": "評価額下限",
        "value_above": "評価額上限"
    }
    return mapping.get(alert_type, alert_type)


def _format_threshold(alert_type: str, threshold: float) -> str:
    """閾値をフォーマット"""
    if alert_type == "daily_change":
        return f"{threshold}%"
    else:
        return f"${threshold:,.0f}"
