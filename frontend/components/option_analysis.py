import reflex as rx

from frontend.state.market_state import MarketState


def render_ticker_compact(opt) -> rx.Component:
    """Compact option summary card for a major index ETF."""

    sentiment = opt.sentiment
    icon = rx.cond(sentiment == "強気", "▲", rx.cond(sentiment == "弱気", "▼", "■"))

    pcr_color = rx.cond(
        opt.pcr_vol > 1.2, "red", rx.cond(opt.pcr_vol < 0.7, "green", "gray")
    )
    gex_color = rx.cond(
        opt.net_gex_available, rx.cond(opt.net_gex > 0, "green", "red"), "gray"
    )

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(icon, " ", opt.ticker, weight="bold"),
                rx.spacer(),
                rx.cond(
                    opt.current_price_str != "",
                    rx.text(opt.current_price_str, weight="bold"),
                    rx.text(""),
                ),
                rx.badge(
                    opt.data_quality,
                    color_scheme=_quality_color(opt.data_quality),
                    variant="surface",
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
                        lambda item: rx.text("- ", item, size="1", color="gray"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.text("詳細データがありません", size="1", color="gray"),
            ),
            rx.cond(
                opt.quality_warnings.length() > 0,
                rx.vstack(
                    rx.foreach(
                        opt.quality_warnings,
                        lambda item: rx.text(
                            "※ ", item, size="1", color=rx.color("amber", 11)
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def option_analysis_component() -> rx.Component:
    """Render option analysis section."""

    return rx.box(
        rx.heading("オプション分析", size="5", margin_bottom="1rem"),
        rx.cond(
            MarketState.market_type == "JP",
            rx.callout(
                "日本市場のオプションデータは対象外です。",
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
                    rx.cond(
                        MarketState.option_error_msg != "",
                        MarketState.option_error_msg,
                        "Option data is currently unavailable.",
                    ),
                    color="gray",
                ),
            ),
        ),
        width="100%",
        margin_top="2rem",
        margin_bottom="2rem",
    )


def _quality_color(quality) -> rx.Var:
    return rx.cond(
        quality == "available",
        "green",
        rx.cond(
            quality == "partial",
            "amber",
            rx.cond(
                quality == "estimated",
                "amber",
                rx.cond(quality == "stale_cache", "orange", "red"),
            ),
        ),
    )
