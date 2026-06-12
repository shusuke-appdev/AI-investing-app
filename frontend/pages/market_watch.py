import reflex as rx

from frontend.components.data_provenance import provenance_panel
from frontend.components.flash_summary import (
    market_distortion_panel,
    market_monitor,
    watch_indices_strip,
)
from frontend.components.market_risk_intelligence import market_risk_intelligence_panel
from frontend.components.momentum_display import momentum_monitor_component
from frontend.components.option_analysis import option_analysis_component
from frontend.components.ui_primitives import loading_state, page_header
from frontend.pages.theme import theme_ranking_content
from frontend.state.market_state import MarketState
from frontend.template import template


def _stage_status_strip() -> rx.Component:
    return rx.grid(
        rx.foreach(MarketState.detail_stages, _stage_status_card),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="3",
        width="100%",
        margin_bottom="1rem",
    )


def _stage_status_card(stage) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(stage.difficulty, color_scheme="gray", variant="surface"),
                rx.text(stage.label, weight="bold", size="2", flex="1"),
                rx.badge(
                    stage.status_label,
                    color_scheme=_stage_color(stage.status),
                    variant="surface",
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(stage.summary, size="1", color=rx.color("gray", 10)),
            rx.cond(
                stage.cache_status != "",
                rx.text(
                    "source: " + stage.cache_status,
                    size="1",
                    color=rx.color("gray", 9),
                ),
                rx.fragment(),
            ),
            align_items="start",
            spacing="1",
            width="100%",
        ),
        padding="0.75rem",
    )


def _stage_color(status) -> rx.Var:
    return rx.cond(
        status == "live",
        "green",
        rx.cond(
            status == "loading",
            "blue",
            rx.cond(
                status == "partial",
                "amber",
                rx.cond(
                    (status == "cache") | (status == "stale_cache"),
                    "orange",
                    rx.cond(status == "failed", "red", "gray"),
                ),
            ),
        ),
    )


@template
def market_watch_page() -> rx.Component:
    """市場監視ページ"""

    return rx.vstack(
        page_header(
            "市場監視",
            "市場スタンス、主要ドライバー、リスク要因を段階更新で確認します。",
            rx.button(
                rx.icon("activity", size=16),
                "詳細更新",
                on_click=MarketState.refresh_market_details,
                loading=MarketState.is_fetching_details,
                variant="surface",
            ),
            rx.button(
                rx.icon("chart-no-axes-combined", size=16),
                "Options",
                on_click=MarketState.refresh_options,
                loading=MarketState.is_fetching_options,
                variant="surface",
            ),
        ),
        _stage_status_strip(),
        provenance_panel(MarketState.provenance),
        rx.cond(
            MarketState.error_msg != "",
            rx.callout(
                MarketState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                width="100%",
            ),
        ),
        rx.cond(
            MarketState.is_fetching,
            loading_state("市場監視データを取得中..."),
            rx.vstack(
                watch_indices_strip(),
                market_risk_intelligence_panel(),
                market_monitor(),
                market_distortion_panel(),
                momentum_monitor_component(),
                option_analysis_component(),
                theme_ranking_content(),
                width="100%",
                spacing="4",
            ),
        ),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
