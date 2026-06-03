import reflex as rx

from frontend.components.flash_summary import (
    market_distortion_panel,
    market_monitor,
    watch_indices_strip,
)
from frontend.components.momentum_display import momentum_monitor_component
from frontend.components.option_analysis import option_analysis_component
from frontend.pages.theme import theme_ranking_content
from frontend.state.market_state import MarketState
from frontend.template import template


@template
def market_watch_page() -> rx.Component:
    """市場監視ページ"""

    return rx.vstack(
        rx.hstack(
            rx.heading("市場監視", size="7"),
            rx.spacer(),
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
            width="100%",
            align_items="center",
            margin_bottom="2rem",
        ),
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
            rx.center(
                rx.spinner(size="3"),
                rx.text("市場監視データを取得中...", margin_top="1rem", color="gray"),
                direction="column",
                width="100%",
                height="300px",
            ),
            rx.vstack(
                watch_indices_strip(),
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
