"""
Portfolio Input Module
ポートフォリオ入力・管理およびGoogle Financeライクな機能を提供します。
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import datetime

from src.market_data import get_stock_info
from src.data_provider import DataProvider
from src.portfolio_advisor import PortfolioHolding, parse_csv_portfolio
from src.portfolio_storage import save_portfolio
from src.portfolio_history import get_value_series


def render_portfolio_manager() -> list[PortfolioHolding]:
    """
    Google Finance風のポートフォリオ管理UI
    上部に評価額推移、メインに銘柄一覧、下部にニュースを配置し、右側にハイライト円グラフを表示
    """
    holdings_data = st.session_state.get("managed_holdings", [])
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")

    # 1. Top Graph (Asset History)
    _render_top_history_graph(current_name, holdings_data)

    st.markdown("---")

    # 2. 2-Column Layout (7:3 ratio)
    col_main, col_side = st.columns([7, 3])

    with col_main:
        # A. Holdings Table
        _render_holdings_table(holdings_data)

        # B. Add Button
        _render_add_button(holdings_data, current_name)

        # C. News
        if holdings_data:
            st.markdown("### 📰 ニュースとイベント")
            _render_news([h["ticker"] for h in holdings_data])

    with col_side:
        if holdings_data:
            _render_highlights(holdings_data)
            _render_earnings_calendar([h["ticker"] for h in holdings_data])

    return [PortfolioHolding(**h) for h in holdings_data if h["shares"] > 0]


def _render_top_history_graph(portfolio_name: str, holdings_data: list):
    """上部の評価額推移グラフを描画"""
    dates, values = get_value_series(portfolio_name, 30)

    # 履歴がない場合、現在の評価額のみを即時計算して表示する
    if not dates or len(dates) < 2:
        current_val = 0.0
        for h in holdings_data:
            quote = DataProvider.get_quote(h["ticker"]) or {}
            price = quote.get("c") or 0.0
            current_val += price * h["shares"]

        st.markdown(
            f"<h1 style='margin-bottom:0px;'>${current_val:,.2f}</h1>",
            unsafe_allow_html=True,
        )
        st.caption(
            "評価額の推移データがありません。スナップショットを記録するとグラフが表示されます。"
        )
        return

    df = pd.DataFrame({"Date": dates, "Value": values})
    fig = go.Figure(
        go.Scatter(
            x=df["Date"],
            y=df["Value"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#1a73e8", width=2),
            fillcolor="rgba(26, 115, 232, 0.1)",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=250,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True),
        hovermode="x unified",
    )

    # Highlight current value and 1-day change
    current_val = values[-1]
    prev_val = values[-2] if len(values) > 1 else current_val
    diff = current_val - prev_val
    diff_pct = (diff / prev_val * 100) if prev_val else 0.0

    st.markdown(
        f"<h1 style='margin-bottom:0px;'>${current_val:,.2f}</h1>",
        unsafe_allow_html=True,
    )
    color = "green" if diff >= 0 else "red"
    bg_color = "rgba(0,255,0,0.1)" if color == "green" else "rgba(255,0,0,0.1)"
    sign = "+" if diff >= 0 else ""
    st.markdown(
        f"<span style='color:{color}; font-weight:bold; background-color: {bg_color}; padding: 5px; border-radius: 5px;'>"
        f"{sign}{diff_pct:.2f}% ({sign}${diff:,.2f}) 今日</span>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def _delete_holding(ticker: str):
    """銘柄削除のコールバック関数"""
    holdings = st.session_state.get("managed_holdings", [])
    updated = [h for h in holdings if h["ticker"] != ticker]
    st.session_state.managed_holdings = updated
    current_name = st.session_state.get("current_portfolio_name", "新規ポートフォリオ")
    if current_name != "新規ポートフォリオ":
        save_portfolio(current_name, updated)


def _bulk_delete_holdings(tickers: list[str]):
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


def _render_holdings_table(holdings_data: list):
    """銘柄一覧テーブルの描画"""
    if not holdings_data:
        st.info("銘柄が登録されていません。下の「＋」ボタンから追加してください。")
        return

    show_bulk_delete = st.session_state.get("show_bulk_delete", False)

    # Table header
    cols = st.columns([1.5, 2, 1, 1, 1.5, 1, 0.5])
    with cols[0]:
        st.caption("**セクター**")
    with cols[1]:
        st.caption("**シンボル・名前**")
    with cols[2]:
        st.caption("**価格**")
    with cols[3]:
        st.caption("**数量**")
    with cols[4]:
        st.caption("**1日の収益**")
    with cols[5]:
        st.caption("**評価額**")
    with cols[6]:
        if show_bulk_delete:
            st.caption("**選択**")
        else:
            st.caption("")

    updated = []
    to_delete = []

    for i, h in enumerate(holdings_data):
        info = get_stock_info(h["ticker"])
        quote = DataProvider.get_quote(h["ticker"]) or {}

        current_price = quote.get("c") or info.get("current_price") or 0.0
        dp = quote.get("dp") or 0.0
        d = quote.get("d") or 0.0

        c = st.columns([1.5, 2, 1, 1, 1.5, 1, 0.5])

        # Sector
        c[0].write(info.get("sector", "N/A"))

        # Name
        c[1].write(f"**{h['ticker']}**\n{info.get('name', '')[:15]}")

        # Price
        c[2].write(f"${current_price:,.2f}")

        # Shares: 整数表示に変更し、入力欄を廃止
        shares_int = int(h["shares"])
        c[3].write(f"{shares_int}")

        # 1-day return
        color = "green" if d >= 0 else "red"
        bg_color = "rgba(0,255,0,0.1)" if color == "green" else "rgba(255,0,0,0.1)"
        arrow = "↑" if d >= 0 else "↓"
        sign = "+" if d >= 0 else ""
        daily_return_val = d * shares_int
        c[4].markdown(
            f"<span style='color:{color}; font-weight:bold; background-color: {bg_color}; padding: 3px; border-radius: 3px;'>"
            f"{arrow}{abs(dp):.2f}%</span><br><span style='color:{color};'>{sign}${abs(daily_return_val):.2f}</span>",
            unsafe_allow_html=True,
        )

        # Value
        val = current_price * shares_int
        c[5].write(f"**${val:,.2f}**")

        # Delete: コールバックによる即時削除（tertiaryタイプでUIの違和感解消）、または一括削除用チェックボックス
        if show_bulk_delete:
            c[6].checkbox(
                "選択",
                key=f"sel_{h['ticker']}",
                label_visibility="collapsed",
            )
        else:
            c[6].button(
                "🗑️",
                key=f"del_{h['ticker']}",
                help="削除",
                type="tertiary",
                on_click=_delete_holding,
                args=(h["ticker"],),
            )


def _render_add_button(holdings_data: list, current_name: str):
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

        # 横長で中央の＋ボタン、および右側の選択ボタン
        _, center_col, btn_col, _ = st.columns([2.5, 4, 1.5, 2])
        with center_col:
            # ボタンのテキストはシンプルに「＋」のみ、横幅最大
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

                    if st.button("追加する", key="btn_manual_add"):
                        if new_ticker and new_shares > 0:
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


def _render_highlights(holdings_data: list):
    """ポートフォリオハイライト（円グラフ）"""
    with st.container(border=True):
        st.markdown(
            "<div style='text-align:center; font-weight:bold; padding-bottom:10px;'>ポートフォリオのハイライト</div>",
            unsafe_allow_html=True,
        )

        total_val = 0
        sectors = {}
        caps = {"大企業": 0, "中規模": 0, "小規模": 0}

        for h in holdings_data:
            info = get_stock_info(h["ticker"])
            quote = DataProvider.get_quote(h["ticker"]) or {}
            price = quote.get("c") or info.get("current_price") or 0.0
            val = price * h["shares"]
            total_val += val

            # Sector
            sec = info.get("sector", "N/A")
            sectors[sec] = sectors.get(sec, 0) + val

            # Market Cap (Mega/Large: 大企業 > $10B, Mid: 中規模 > $2B, Small: 小規模 < $2B)
            mcap = info.get("market_cap") or 0
            if mcap >= 10_000_000_000:
                caps["大企業"] += val
            elif mcap >= 2_000_000_000:
                caps["中規模"] += val
            else:
                caps["小規模"] += val

        if total_val == 0:
            st.caption("評価額が0のためハイライトを表示できません")
            return

        def make_pie(data_dict):
            labels = [k for k, v in data_dict.items() if v > 0]
            values = [v for k, v in data_dict.items() if v > 0]
            fig = go.Figure(
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.5,
                    textinfo="label+percent",
                    textposition="inside",
                )
            )
            fig.update_layout(
                margin=dict(t=0, b=0, l=0, r=0), height=220, showlegend=False
            )
            return fig

        st.caption("株・セクター構成比")
        st.plotly_chart(make_pie(sectors), use_container_width=True)
        st.caption("企業規模別構成比")
        st.plotly_chart(make_pie(caps), use_container_width=True)


def _render_news(tickers: list):
    """ニュースコンポーネント"""
    news_items = []
    # API呼び出しの負担を減らすため最大3銘柄のニュースを取得
    for t in tickers[:3]:
        items = DataProvider.get_stock_news(t, max_items=2)
        for item in items:
            item["ticker"] = t
        news_items.extend(items)

    news_items.sort(key=lambda x: x.get("published", ""), reverse=True)

    if not news_items:
        st.info("関連ニュースが見つかりませんでした。")
        return

    for item in news_items[:5]:
        with st.container(border=True):
            st.markdown(
                f"**[{item.get('ticker', '')}]** [{item['title']}]({item['link']})"
            )
            # `published` works if dictionary has it
            st.caption(f"{item.get('publisher', '')} - {item.get('published', '')}")


def _render_earnings_calendar(tickers: list):
    """決算カレンダーコンポーネント"""
    with st.container(border=True):
        st.markdown(
            "<div style='text-align:center; font-weight:bold; padding-bottom:10px;'>収益カレンダー</div>",
            unsafe_allow_html=True,
        )

        today = datetime.date.today()
        next_month = today + datetime.timedelta(days=30)

        try:
            data = DataProvider.get_earnings_calendar(
                today.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d")
            )
            found = [d for d in data if d.get("symbol") in tickers]

            if found:
                found.sort(key=lambda x: x.get("date", ""))
                for item in found[:5]:
                    st.write(f"📅 **{item['symbol']}**: {item.get('date', '')}")
            else:
                st.caption("直近30日の決算発表予定はありません。")
        except Exception:
            st.caption("データ取得エラー")
