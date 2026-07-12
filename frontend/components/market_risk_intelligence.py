import reflex as rx

from frontend.state.market_state import MarketState


def market_risk_intelligence_panel() -> rx.Component:
    """Compact volatility, sentiment, and top-risk summaries."""

    return rx.vstack(
        rx.grid(
            _summary_card(
                "ボラティリティ・レジーム",
                MarketState.volatility_summary,
                MarketState.volatility_posture,
                "activity",
            ),
            _summary_card(
                "独自 Fear & Greed",
                MarketState.sentiment_summary,
                MarketState.sentiment_coverage,
                "gauge",
            ),
            _summary_card(
                "天井警戒サインポスト",
                MarketState.top_risk_summary,
                "BofA-inspired / 非公式",
                "triangle-alert",
            ),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("高ボラ銘柄 FOMOスキャン", size="4", as_="h2"),
                    rx.spacer(),
                    rx.button(
                        "スキャン実行",
                        on_click=MarketState.refresh_fomo_scan,
                        loading=MarketState.is_scanning_fomo,
                        variant="surface",
                    ),
                    width="100%",
                ),
                rx.text(
                    rx.cond(
                        MarketState.fomo_scan_summary != "",
                        MarketState.fomo_scan_summary,
                        "明示実行時のみ対象銘柄を取得します。",
                    ),
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.foreach(
                    MarketState.fomo_scan_items,
                    lambda item: rx.hstack(
                        rx.text(item.ticker, weight="bold", width="90px"),
                        rx.badge(item.label, variant="surface"),
                        rx.text(item.risk_level, size="1", color=rx.color("gray", 10)),
                        width="100%",
                    ),
                ),
                align_items="start",
                width="100%",
            ),
            width="100%",
        ),
        width="100%",
    )


def _summary_card(title, summary, badge, icon: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=17),
                rx.text(title, weight="bold", size="2"),
                width="100%",
            ),
            rx.text(
                rx.cond(summary != "", summary, "詳細更新後に表示します。"),
                size="2",
            ),
            rx.cond(
                badge != "",
                rx.badge(badge, variant="surface", color_scheme="blue"),
                rx.fragment(),
            ),
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )
