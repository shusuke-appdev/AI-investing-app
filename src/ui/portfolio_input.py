"""
Portfolio Input Module
ポートフォリオ入力関連のUI機能を提供します。
"""
import streamlit as st
from typing import Optional

from src.portfolio_advisor import PortfolioHolding, parse_csv_portfolio
from src.portfolio_storage import (
    save_portfolio, load_portfolio, list_portfolios, delete_portfolio
)
from src.market_data import get_stock_info


def render_portfolio_manager() -> list[PortfolioHolding]:
    """
    インタラクティブなポートフォリオ管理UI
    銘柄の追加・削除・編集が可能
    """
    st.markdown("### 📊 ポートフォリオ管理")
    
    # セッションステートでポートフォリオを管理
    if "managed_holdings" not in st.session_state:
        st.session_state.managed_holdings = []
    
    holdings_data = st.session_state.managed_holdings
    
    # 新規銘柄追加フォーム
    st.markdown("#### ➕ 銘柄を追加")
    
    # ラベル行（明確化）
    label_cols = st.columns([2, 1, 1, 1])
    with label_cols[0]:
        st.caption("**銘柄コード**")
    with label_cols[1]:
        st.caption("**株数**")
    with label_cols[2]:
        st.caption("**取得単価 ($)**")
    with label_cols[3]:
        st.caption("")
    
    # 入力行
    add_cols = st.columns([2, 1, 1, 1])
    with add_cols[0]:
        new_ticker = st.text_input(
            "銘柄コード",
            key="new_ticker",
            placeholder="AAPL",
            label_visibility="collapsed"
        ).upper()
    with add_cols[1]:
        new_shares = st.number_input(
            "株数",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="new_shares",
            label_visibility="collapsed",
            format="%.2f",
            placeholder="10"
        )
    with add_cols[2]:
        new_cost = st.number_input(
            "取得単価",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="new_cost",
            label_visibility="collapsed",
            format="%.2f",
            placeholder="150.00"
        )
    with add_cols[3]:
        if st.button("➕ 追加", use_container_width=True, type="primary"):
            if new_ticker and new_shares > 0:
                existing = next((h for h in holdings_data if h["ticker"] == new_ticker), None)
                if existing:
                    existing["shares"] += new_shares
                    st.success(f"✅ {new_ticker} を更新 (合計: {existing['shares']}株)")
                else:
                    holdings_data.append({
                        "ticker": new_ticker,
                        "shares": new_shares,
                        "avg_cost": new_cost if new_cost > 0 else None
                    })
                    st.success(f"✅ {new_ticker} を追加")
                st.session_state.managed_holdings = holdings_data
                st.rerun()
            else:
                st.warning("ティッカーと株数を入力してください")
    
    st.markdown("---")
    
    if not holdings_data:
        st.info("銘柄を追加してください")
        return []
    
    st.markdown(f"#### 📋 保有銘柄 ({len(holdings_data)}銘柄)")
    
    # ヘッダー
    header_cols = st.columns([2, 1.5, 1.5, 1, 0.5])
    with header_cols[0]:
        st.markdown("**銘柄**")
    with header_cols[1]:
        st.markdown("**株数**")
    with header_cols[2]:
        st.markdown("**取得単価**")
    with header_cols[3]:
        st.markdown("**評価額**")
    with header_cols[4]:
        st.markdown("**操作**")
    
    # 各銘柄の編集行
    updated_holdings = []
    to_delete = []
    
    for i, h in enumerate(holdings_data):
        cols = st.columns([2, 1.5, 1.5, 1, 0.5])
        
        with cols[0]:
            info = get_stock_info(h["ticker"])
            name = info.get("name", h["ticker"])[:20]
            st.markdown(f"**{h['ticker']}**  \n{name}")
        
        with cols[1]:
            new_shares = st.number_input(
                "株数",
                min_value=0.0,
                value=float(h["shares"]),
                step=1.0,
                key=f"edit_shares_{i}",
                label_visibility="collapsed",
                format="%.2f"
            )
        
        with cols[2]:
            current_cost = h.get("avg_cost") or 0.0
            new_cost = st.number_input(
                "単価",
                min_value=0.0,
                value=float(current_cost),
                step=1.0,
                key=f"edit_cost_{i}",
                label_visibility="collapsed",
                format="%.2f"
            )
        
        with cols[3]:
            current_price = info.get("current_price", 0)
            value = current_price * new_shares
            st.markdown(f"${value:,.0f}")
        
        with cols[4]:
            if st.button("🗑️", key=f"del_{i}", help="削除"):
                to_delete.append(i)
        
        if new_shares > 0:
            updated_holdings.append({
                "ticker": h["ticker"],
                "shares": new_shares,
                "avg_cost": new_cost if new_cost > 0 else None
            })
    
    if to_delete:
        for idx in sorted(to_delete, reverse=True):
            holdings_data.pop(idx)
        st.session_state.managed_holdings = holdings_data
        st.rerun()
    
    if updated_holdings != holdings_data:
        st.session_state.managed_holdings = updated_holdings
    
    # 一括操作
    st.markdown("---")
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("🔄 全クリア", type="secondary", use_container_width=True):
            st.session_state.managed_holdings = []
            st.rerun()
    with action_cols[1]:
        if st.button("📥 保存済みから読込", type="secondary", use_container_width=True):
            st.session_state.portfolio_input_mode = "saved"
            st.rerun()
    
    return [
        PortfolioHolding(
            ticker=h["ticker"],
            shares=h["shares"],
            avg_cost=h.get("avg_cost")
        )
        for h in st.session_state.managed_holdings
        if h["shares"] > 0
    ]


def render_save_portfolio(holdings: list[PortfolioHolding]):
    """ポートフォリオ保存UI"""
    with st.expander("💾 ポートフォリオを保存"):
        portfolio_name = st.text_input("ポートフォリオ名", placeholder="メインポートフォリオ")
        if st.button("保存", use_container_width=True):
            if portfolio_name:
                holdings_data = [
                    {"ticker": h.ticker, "shares": h.shares, "avg_cost": h.avg_cost}
                    for h in holdings
                ]
                if save_portfolio(portfolio_name, holdings_data):
                    st.success(f"✅ 「{portfolio_name}」を保存しました")
                else:
                    st.error("保存に失敗しました")
            else:
                st.warning("ポートフォリオ名を入力してください")


def render_saved_portfolios() -> list[PortfolioHolding]:
    """保存済みポートフォリオUI"""
    portfolios = list_portfolios()
    
    if not portfolios:
        st.info("保存済みポートフォリオがありません")
        return []
    
    selected = st.selectbox("📂 ポートフォリオを選択", portfolios)
    
    if selected:
        data = load_portfolio(selected)
        if data:
            holdings = []
            for h in data.get("holdings", []):
                holdings.append(PortfolioHolding(
                    ticker=h["ticker"],
                    shares=h["shares"],
                    avg_cost=h.get("avg_cost")
                ))
            
            if holdings:
                st.success(f"✅ {len(holdings)}銘柄を読み込み")
                show_holdings_preview(holdings)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📊 管理モードで編集", use_container_width=True):
                        st.session_state.managed_holdings = [
                            {"ticker": h.ticker, "shares": h.shares, "avg_cost": h.avg_cost}
                            for h in holdings
                        ]
                        st.session_state.portfolio_input_mode = "manage"
                        st.rerun()
                with col2:
                    if st.button("🗑️ このポートフォリオを削除", type="secondary", use_container_width=True):
                        if delete_portfolio(selected):
                            st.success("削除しました")
                            st.rerun()
                
                return holdings
    
    return []


def render_manual_input() -> list[PortfolioHolding]:
    """手動入力UI"""
    holdings = []
    
    num_holdings = st.slider("保有銘柄数", 1, 15, 3)
    
    st.markdown("#### 保有銘柄")
    
    for i in range(num_holdings):
        cols = st.columns([2, 1, 1])
        with cols[0]:
            ticker = st.text_input(
                f"銘柄{i+1}",
                key=f"ticker_{i}",
                placeholder="AAPL",
                label_visibility="collapsed"
            ).upper()
        with cols[1]:
            shares = st.number_input(
                "株数",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f"shares_{i}",
                label_visibility="collapsed"
            )
        with cols[2]:
            avg_cost = st.number_input(
                "取得単価",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f"cost_{i}",
                label_visibility="collapsed"
            )
        
        if ticker and shares > 0:
            holdings.append(PortfolioHolding(
                ticker=ticker,
                shares=shares,
                avg_cost=avg_cost if avg_cost > 0 else None
            ))
    
    return holdings


def render_text_paste() -> list[PortfolioHolding]:
    """テキスト貼付け入力UI"""
    st.markdown("""
    **CSV形式で貼り付け:**
    ```
    ticker,shares,avg_cost
    AAPL,10,150.00
    NVDA,5,500.00
    TSLA,3,
    ```
    """)
    
    csv_text = st.text_area(
        "CSVデータを貼り付け",
        height=200,
        placeholder="ticker,shares,avg_cost\nAAPL,10,150.00\nNVDA,5,500.00"
    )
    
    if csv_text.strip():
        holdings = parse_csv_portfolio(csv_text)
        if holdings:
            st.success(f"✅ {len(holdings)}銘柄を認識")
            show_holdings_preview(holdings)
            return holdings
        else:
            st.warning("⚠️ データを認識できませんでした")
    
    return []


def render_file_import() -> list[PortfolioHolding]:
    """ファイルインポートUI"""
    
    tab1, tab2 = st.tabs(["📁 ローカルCSV", "☁️ Google Drive"])
    
    with tab1:
        uploaded = st.file_uploader(
            "CSVファイルをアップロード",
            type=["csv"],
            help="ticker,shares,avg_cost のカラムを含むCSV"
        )
        
        if uploaded:
            content = uploaded.read().decode("utf-8")
            holdings = parse_csv_portfolio(content)
            if holdings:
                st.success(f"✅ {len(holdings)}銘柄を読み込み")
                show_holdings_preview(holdings)
                return holdings
    
    with tab2:
        st.markdown("""
        **Google Sheets共有リンクで取得:**
        """)
        
        drive_url = st.text_input(
            "Google Sheets共有URL",
            placeholder="https://docs.google.com/spreadsheets/d/..."
        )
        
        if drive_url and "docs.google.com/spreadsheets" in drive_url:
            # URLを安全に解析
            parts = drive_url.split("/d/")
            if len(parts) < 2:
                st.warning("⚠️ URLの形式が正しくありません。/d/ を含むURLを入力してください")
            else:
                sheet_parts = parts[1].split("/")
                if not sheet_parts or not sheet_parts[0]:
                    st.warning("⚠️ スプレッドシートIDを抽出できませんでした")
                else:
                    sheet_id = sheet_parts[0]
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                    
                    if st.button("📥 スプレッドシートを読み込み"):
                        import requests
                        try:
                            resp = requests.get(csv_url, timeout=10)
                            resp.raise_for_status()
                            holdings = parse_csv_portfolio(resp.text)
                            if holdings:
                                st.success(f"✅ {len(holdings)}銘柄を読み込み")
                                show_holdings_preview(holdings)
                                st.session_state.drive_holdings = holdings
                        except Exception as e:
                            st.error(f"❌ 読み込みエラー: {str(e)}")
                    
                    if "drive_holdings" in st.session_state:
                        return st.session_state.drive_holdings
    
    return []


def show_holdings_preview(holdings: list[PortfolioHolding]):
    """保有銘柄のプレビュー表示"""
    preview_data = [
        {"銘柄": h.ticker, "株数": h.shares, "取得単価": f"${h.avg_cost:.2f}" if h.avg_cost else "-"}
        for h in holdings
    ]
    st.dataframe(preview_data, use_container_width=True, hide_index=True)
