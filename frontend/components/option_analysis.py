import reflex as rx

from frontend.state.market_state import MarketState


def render_ticker_compact(opt) -> rx.Component:
    """個別銘柄のコンパクト表示（ナラティブ形式）"""
    ticker = opt.ticker
    sentiment = opt.sentiment

    icon = rx.cond(sentiment == "強気", "🟢", rx.cond(sentiment == "弱気", "🔴", "⚪"))
    current_price = opt.current_price

    net_gex = opt.net_gex
    pcr_vol = opt.pcr_vol

    pcr_color = rx.cond(pcr_vol > 1.2, "red", rx.cond(pcr_vol < 0.7, "green", "gray"))
    gex_color = rx.cond(net_gex > 0, "green", "red")

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(icon, " ", ticker, weight="bold"),
                rx.spacer(),
                rx.cond(
                    current_price > 0,
                    rx.text(f"${current_price:,.2f}", weight="bold"),
                    rx.text(""),
                ),
                width="100%",
            ),
            rx.divider(),
            rx.grid(
                rx.vstack(
                    rx.text("PCR (Vol)", size="1", color="gray"),
                    rx.text(
                        opt.pcr_vol_str, weight="bold", color=rx.color(pcr_color, 9)
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Net GEX", size="1", color="gray"),
                    rx.text(
                        opt.net_gex_str, weight="bold", color=rx.color(gex_color, 9)
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("IV(ATM)", size="1", color="gray"),
                    rx.text(opt.iv, weight="bold"),
                    align_items="start",
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Max Pain", size="1", color="gray"),
                    rx.text(opt.max_pain, weight="bold"),
                    align_items="start",
                    spacing="1",
                ),
                columns="2",
                spacing="2",
                width="100%",
            ),
            rx.divider(),
            rx.cond(
                opt.analysis.length() > 0,
                rx.vstack(
                    rx.foreach(
                        opt.analysis,
                        lambda item: rx.text("• ", item, size="1", color="gray"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.text("詳細データがありません", size="1", color="gray"),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def option_analysis_component() -> rx.Component:
    """オプション分析コンポーネント"""
    return rx.box(
        rx.heading("📊 オプション分析 (詳細)", size="5", margin_bottom="1rem"),
        rx.cond(
            MarketState.market_type == "JP",
            rx.callout(
                "🇯🇵 日本市場のオプションデータは現在取得できません（yfinance APIの制約）",
                icon="info",
                color_scheme="amber",
                width="100%",
            ),
            rx.cond(
                MarketState.option_analysis.length() > 0,
                rx.grid(
                    rx.foreach(MarketState.option_analysis, render_ticker_compact),
                    columns=rx.breakpoints(initial="1", md="2", lg="3"),
                    spacing="4",
                    width="100%",
                ),
                rx.text(
                    "Yahoo Financeの利用制限（Rate Limit）により現在データが取得できません。数十秒〜数分経ってから更新をお試しください。",
                    color="gray",
                ),
            ),
        ),
        width="100%",
        margin_top="2rem",
        margin_bottom="2rem",
    )
