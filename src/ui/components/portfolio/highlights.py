"""
Portfolio Highlights Component
ポートフォリオのニュース、決算カレンダー、ハイライト（損益と円グラフ）を描画します。
"""

import datetime

import plotly.graph_objects as go
import streamlit as st

from src.data_provider import DataProvider
from src.market_data import get_stock_info


def render_highlights(holdings_data: list) -> None:
    """ポートフォリオハイライト（損益と円グラフ）"""
    with st.container(border=True):
        st.markdown(
            "<div style='font-size:1.2rem; font-weight:bold; padding-bottom:15px;'>ポートフォリオのハイライト</div>",
            unsafe_allow_html=True,
        )

        total_val = 0.0
        total_cost = 0.0
        total_daily_val = 0.0
        total_prev_val = 0.0
        sectors: dict[str, float] = {}
        caps = {"大企業": 0.0, "中規模": 0.0, "小規模": 0.0}

        for h in holdings_data:
            info = get_stock_info(h["ticker"])
            quote = DataProvider.get_quote(h["ticker"]) or {}
            price = quote.get("c") or info.get("current_price") or 0.0
            daily_change = quote.get("d") or 0.0

            val = price * h["shares"]
            total_val += val

            avg_cost = h.get("avg_cost")
            if avg_cost and avg_cost > 0:
                total_cost += avg_cost * h["shares"]
            else:
                total_cost += price * h["shares"]

            total_daily_val += daily_change * h["shares"]
            prev_price = price - daily_change
            total_prev_val += prev_price * h["shares"]

            sec = info.get("sector", "N/A")
            sectors[sec] = sectors.get(sec, 0) + val

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

        total_daily_pct = (
            (total_daily_val / total_prev_val * 100) if total_prev_val > 0 else 0.0
        )
        total_return_val = total_val - total_cost
        total_return_pct = (
            (total_return_val / total_cost * 100) if total_cost > 0 else 0.0
        )

        daily_color = "#10b981" if total_daily_val >= 0 else "#ef4444"
        daily_bg = "#ecfdf5" if total_daily_val >= 0 else "#fef2f2"
        daily_sign = "+" if total_daily_val >= 0 else ""
        daily_arrow = "↑" if total_daily_val >= 0 else "↓"

        total_color = "#10b981" if total_return_val >= 0 else "#ef4444"
        total_bg = "#ecfdf5" if total_return_val >= 0 else "#fef2f2"
        total_sign = "+" if total_return_val >= 0 else ""
        total_arrow = "↑" if total_return_val >= 0 else "↓"

        st.markdown(
            f"""
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <div style="flex:1; background-color:{daily_bg}; padding:15px; border-radius:8px;">
                <div style="font-size:0.9rem; color:#4b5563; margin-bottom:5px;">1日の収益</div>
                <div style="font-size:1.2rem; font-weight:bold; color:{daily_color};">{daily_sign}${abs(total_daily_val):,.2f}</div>
                <div style="font-size:1rem; font-weight:bold; color:{daily_color};">{daily_arrow} {abs(total_daily_pct):.2f}%</div>
            </div>
            <div style="flex:1; background-color:{total_bg}; padding:15px; border-radius:8px;">
                <div style="font-size:0.9rem; color:#4b5563; margin-bottom:5px;">合計収益</div>
                <div style="font-size:1.2rem; font-weight:bold; color:{total_color};">{total_sign}${abs(total_return_val):,.2f}</div>
                <div style="font-size:1rem; font-weight:bold; color:{total_color};">{total_arrow} {abs(total_return_pct):.2f}%</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        def make_pie(data_dict: dict) -> go.Figure:
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


def render_news(tickers: list) -> None:
    """ニュースコンポーネント"""
    news_items = []
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
            st.caption(f"{item.get('publisher', '')} - {item.get('published', '')}")


def render_earnings_calendar(tickers: list) -> None:
    """決算カレンダーコンポーネント"""
    with st.container(border=True):
        st.markdown(
            "<div style='font-size:1.1rem; font-weight:bold; padding-bottom:10px;'>収益カレンダー</div>",
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
