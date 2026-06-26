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
                rx.badge(
                    opt.complete_status_label,
                    color_scheme=_complete_color(opt.complete_status),
                    variant="surface",
                ),
                width="100%",
                wrap="wrap",
            ),
            rx.divider(),
            rx.hstack(
                rx.badge(
                    rx.cond(
                        opt.provider_active,
                        "MarketData.app active",
                        "direct Greeksなし",
                    ),
                    color_scheme=rx.cond(opt.provider_active, "green", "gray"),
                    variant="surface",
                ),
                rx.badge(
                    "Gamma " + opt.gamma_coverage_str,
                    color_scheme=rx.cond(
                        opt.gamma_coverage_str == "100%", "green", "amber"
                    ),
                    variant="surface",
                ),
                spacing="2",
                wrap="wrap",
            ),
            rx.cond(
                opt.source != "",
                rx.text(
                    "取得元: ",
                    opt.source,
                    rx.cond(
                        opt.data_mode != "",
                        " / mode=" + opt.data_mode,
                        "",
                    ),
                    rx.cond(
                        opt.data_as_of != "",
                        " / 基準時刻=" + opt.data_as_of,
                        "",
                    ),
                    size="1",
                    color="gray",
                ),
                rx.fragment(),
            ),
            rx.cond(
                opt.fallback_reason != "",
                rx.callout(
                    opt.fallback_reason,
                    icon="info",
                    color_scheme="amber",
                    width="100%",
                ),
                rx.fragment(),
            ),
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
            rx.cond(
                opt.term_structure_summary != "",
                rx.text(opt.term_structure_summary, size="1", color="gray"),
                rx.fragment(),
            ),
            rx.cond(
                opt.horizons.length() > 0,
                rx.vstack(
                    rx.foreach(opt.horizons, render_horizon_row),
                    spacing="1",
                    width="100%",
                ),
                rx.fragment(),
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


def render_horizon_row(horizon) -> rx.Component:
    """Compact term-structure row for one option horizon."""

    return rx.grid(
        rx.text(horizon.label, weight="bold", size="1"),
        rx.text("DTE ", horizon.dte, size="1", color="gray"),
        rx.text("IV ", horizon.iv, size="1"),
        rx.text("1σ ", horizon.expected_move, size="1"),
        rx.text("PCR ", horizon.pcr_vol, size="1"),
        rx.text("Skew ", horizon.skew, size="1"),
        rx.text("GEX ", horizon.gex, size="1"),
        columns=rx.breakpoints(initial="2", sm="4", lg="7"),
        spacing="2",
        width="100%",
        padding="0.35rem 0",
        border_bottom="1px solid var(--gray-4)",
    )


def option_analysis_component() -> rx.Component:
    """Render option analysis section."""

    return rx.box(
        rx.hstack(
            rx.heading("オプション分析", size="5"),
            rx.spacer(),
            rx.badge(
                MarketState.option_status,
                color_scheme=_quality_color(MarketState.option_status),
                variant="surface",
            ),
            rx.badge(
                _complete_label(MarketState.option_complete_status),
                color_scheme=_complete_color(MarketState.option_complete_status),
                variant="surface",
            ),
            width="100%",
            align_items="center",
            wrap="wrap",
            margin_bottom="1rem",
        ),
        rx.hstack(
            rx.badge(
                rx.cond(
                    MarketState.option_provider_active,
                    "MarketData.app active",
                    "MarketData.app inactive",
                ),
                color_scheme=rx.cond(
                    MarketState.option_provider_active, "green", "gray"
                ),
                variant="surface",
            ),
            rx.badge(
                "Gamma " + MarketState.option_gamma_coverage,
                color_scheme=rx.cond(
                    MarketState.option_gamma_coverage == "100%", "green", "amber"
                ),
                variant="surface",
            ),
            rx.cond(
                MarketState.option_fallback_reason != "",
                rx.badge(
                    "fallback",
                    color_scheme="amber",
                    variant="surface",
                ),
                rx.fragment(),
            ),
            spacing="2",
            wrap="wrap",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            MarketState.option_fallback_reason != "",
            rx.callout(
                MarketState.option_fallback_reason,
                icon="info",
                color_scheme="amber",
                width="100%",
                margin_bottom="0.75rem",
            ),
            rx.fragment(),
        ),
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


def _complete_label(value) -> rx.Var:
    return rx.cond(
        value == "complete",
        "完全取得",
        rx.cond(
            value == "fallback",
            "fallback中",
            rx.cond(
                value == "partial_greeks",
                "Greeks一部欠損",
                rx.cond(
                    value == "provider_inactive",
                    "直接Greeksなし",
                    rx.cond(value == "failed", "取得失敗", "未取得"),
                ),
            ),
        ),
    )


def _complete_color(value) -> rx.Var:
    return rx.cond(
        value == "complete",
        "green",
        rx.cond(
            (value == "fallback") | (value == "partial_greeks"),
            "amber",
            rx.cond(value == "failed", "red", "gray"),
        ),
    )
