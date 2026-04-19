"""
Portfolio Holdings Table Component
銘柄一覧テーブルと追加・削除UIを提供します。
"""

import streamlit as st

from src.data_provider import DataProvider
from src.market_data import get_stock_info
from src.portfolio_advisor import parse_csv_portfolio
from src.portfolio_storage import save_portfolio


def _delete_holding(ticker: str) -> None:
    """銘柄削除のコールバック関数"""
    holdings = st.session_state.get("managed_holdings", [])
    updated = [h for h in holdings if h["ticker"] != ticker]
    st.session_state.managed_holdings = updated
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")
    if current_name != "新規ポートフォリオ":
        save_portfolio(current_name, updated)


def _bulk_delete_holdings(tickers: list[str]) -> None:
    """複数銘柄の一括削除"""
    holdings = st.session_state.get("managed_holdings", [])
    updated = [h for h in holdings if h["ticker"] not in tickers]
    st.session_state.managed_holdings = updated
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")
    if current_name != "新規ポートフォリオ":
        save_portfolio(current_name, updated)

    for t in tickers:
        key = f"sel_{t}"
        if key in st.session_state:
            del st.session_state[key]


def render_holdings_table(holdings_data: list) -> None:
    """銘柄一覧テーブルの描画（全幅）"""
    if not holdings_data:
        st.info("銘柄が登録されていません。下の「＋」ボタンから追加してください。")
        return

    show_bulk_delete = st.session_state.get("show_bulk_delete", False)

    layout_cols = [1.5, 1.0, 1.2, 1.5, 0.8, 1.3, 1.5, 1.5, 0.5]
    cols = st.columns(layout_cols)
    with cols[0]:
        st.caption("**セクター**")
    with cols[1]:
        st.caption("**シンボル**")
    with cols[2]:
        st.caption("**価格**")
    with cols[3]:
        st.caption("**平均取得価格**")
    with cols[4]:
        st.caption("**数量**")
    with cols[5]:
        st.caption("**評価額**")
    with cols[6]:
        st.caption("**1日の収益**")
    with cols[7]:
        st.caption("**損益**")
    with cols[8]:
        if show_bulk_delete:
            st.caption("**選択**")
        else:
            st.caption("")

    for _i, h in enumerate(holdings_data):
        info = get_stock_info(h["ticker"])
        quote = DataProvider.get_quote(h["ticker"]) or {}

        current_price = quote.get("c") or info.get("current_price") or 0.0
        dp = quote.get("dp") or 0.0
        d = quote.get("d") or 0.0

        c = st.columns(layout_cols)

        # 1. Sector
        c[0].write(info.get("sector", "N/A"))

        # 2. Symbol
        c[1].write(f"**{h['ticker']}**")

        # 3. Price
        c[2].write(f"${current_price:,.2f}")

        # 4. Avg Cost
        avg_cost = h.get("avg_cost")
        if avg_cost and avg_cost > 0:
            c[3].write(f"${avg_cost:,.2f}")
        else:
            c[3].write("-")

        # 5. Shares
        shares_int = int(h["shares"])
        c[4].write(f"{shares_int}")

        # 6. Value
        val = current_price * shares_int
        c[5].write(f"**${val:,.2f}**")

        # 7. 1-day return
        color = "green" if d >= 0 else "red"
        bg_color = "rgba(0,128,0,0.1)" if color == "green" else "rgba(255,0,0,0.1)"
        arrow = "↑" if d >= 0 else "↓"
        sign = "+" if d >= 0 else ""
        daily_return_val = d * shares_int
        c[6].markdown(
            f"<span style='color:{color}; font-weight:bold; background-color: {bg_color}; padding: 3px; border-radius: 3px;'>"
            f"{arrow}{abs(dp):.2f}%</span><br><span style='color:{color};'>{sign}${abs(daily_return_val):.2f}</span>",
            unsafe_allow_html=True,
        )

        # 8. Gain/Loss
        if avg_cost and avg_cost > 0:
            gl_val = (current_price - avg_cost) * shares_int
            gl_pct = ((current_price - avg_cost) / avg_cost) * 100
            gl_color = "green" if gl_val >= 0 else "red"
            gl_bg_color = "rgba(0,128,0,0.1)" if gl_val >= 0 else "rgba(255,0,0,0.1)"
            gl_arrow = "↑" if gl_val >= 0 else "↓"
            gl_sign = "+" if gl_val >= 0 else ""
            c[7].markdown(
                f"<span style='color:{gl_color}; font-weight:bold; background-color: {gl_bg_color}; padding: 3px; border-radius: 3px;'>"
                f"{gl_arrow}{abs(gl_pct):.2f}%</span><br><span style='color:{gl_color};'>{gl_sign}${abs(gl_val):.2f}</span>",
                unsafe_allow_html=True,
            )
        else:
            c[7].write("-")

        # 9. Delete
        if show_bulk_delete:
            c[8].checkbox(
                "選択",
                key=f"sel_{h['ticker']}",
                label_visibility="collapsed",
            )
        else:
            c[8].button(
                "🗑️",
                key=f"del_{h['ticker']}",
                help="削除",
                type="tertiary",
                on_click=_delete_holding,
                args=(h["ticker"],),
            )


def render_add_button(holdings_data: list, current_name: str) -> None:
    """中央揃えの「＋」ボタンと追加・一括削除UI"""
    show_bulk_delete = st.session_state.get("show_bulk_delete", False)

    if show_bulk_delete:
        selected_tickers = [
            h["ticker"]
            for h in holdings_data
            if st.session_state.get(f"sel_{h['ticker']}", False)
        ]

        _, col1, col2, _ = st.columns([2, 3, 3, 2])
        with col1:
            if st.button("キャンセル", use_container_width=True):
                st.session_state.show_bulk_delete = False
                st.rerun()
        with col2:
            btn_label = f"🗑️ {len(selected_tickers)}件を削除"
            if st.button(
                btn_label,
                use_container_width=True,
                type="primary",
                disabled=len(selected_tickers) == 0,
            ):
                _bulk_delete_holdings(selected_tickers)
                st.session_state.show_bulk_delete = False
                st.rerun()
    else:
        if "show_add_panel" not in st.session_state:
            st.session_state.show_add_panel = False

        _, center_col, btn_col, _ = st.columns([2.5, 4, 1.5, 2])
        with center_col:
            if st.button("＋", use_container_width=True, type="primary"):
                st.session_state.show_add_panel = not st.session_state.show_add_panel
                st.rerun()
        with btn_col:
            if st.button(
                "選択",
                use_container_width=True,
                help="一括削除する銘柄を選択します",
                type="secondary",
            ):
                st.session_state.show_bulk_delete = True
                st.session_state.show_add_panel = False
                for h in holdings_data:
                    st.session_state[f"sel_{h['ticker']}"] = False
                st.rerun()

        if st.session_state.show_add_panel:
            with st.container(border=True):
                tab_manual, tab_file = st.tabs(
                    ["✏️ 手動入力", "📁 ファイルアップロード"]
                )

                with tab_manual:
                    new_ticker = st.text_input("銘柄コード", placeholder="AAPL").upper()
                    new_shares = st.number_input(
                        "株数", min_value=0.0, value=0.0, step=1.0
                    )
                    new_cost = st.number_input(
                        "取得単価", min_value=0.0, value=0.0, step=1.0
                    )

                    if (
                        st.button("追加する", key="btn_manual_add")
                        and new_ticker
                        and new_shares > 0
                    ):
                        existing = next(
                            (h for h in holdings_data if h["ticker"] == new_ticker),
                            None,
                        )
                        if existing:
                            existing["shares"] += new_shares
                        else:
                            holdings_data.append(
                                {
                                    "ticker": new_ticker,
                                    "shares": new_shares,
                                    "avg_cost": new_cost if new_cost > 0 else None,
                                }
                            )
                        st.session_state.managed_holdings = holdings_data
                        if current_name != "新規ポートフォリオ":
                            save_portfolio(current_name, holdings_data)
                        st.session_state.show_add_panel = False
                        st.rerun()

                with tab_file:
                    uploaded = st.file_uploader(
                        "CSVファイルをアップロード",
                        type=["csv"],
                        help="ticker,shares,avg_cost のカラムを含むCSV",
                    )
                    if uploaded:
                        content = uploaded.read().decode("utf-8")
                        parsed = parse_csv_portfolio(content)
                        if parsed:
                            for p in parsed:
                                existing = next(
                                    (
                                        h
                                        for h in holdings_data
                                        if h["ticker"] == p.ticker
                                    ),
                                    None,
                                )
                                if existing:
                                    existing["shares"] += p.shares
                                else:
                                    holdings_data.append(
                                        {
                                            "ticker": p.ticker,
                                            "shares": p.shares,
                                            "avg_cost": p.avg_cost,
                                        }
                                    )
                            st.session_state.managed_holdings = holdings_data
                            if current_name != "新規ポートフォリオ":
                                save_portfolio(current_name, holdings_data)
                            st.session_state.show_add_panel = False
                            st.success(f"{len(parsed)}銘柄を追加しました")
                            st.rerun()
