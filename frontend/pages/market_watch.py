import reflex as rx

from frontend.components.data_provenance import data_status_panel, provenance_panel
from frontend.components.flash_summary import (
    market_distortion_panel,
    market_monitor,
    trend_ranking_panel,
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
            rx.cond(
                stage.target != "",
                rx.text(
                    "対象: " + stage.target,
                    size="1",
                    color=rx.color("gray", 10),
                ),
                rx.fragment(),
            ),
            rx.text(stage.summary, size="1", color=rx.color("gray", 10)),
            rx.cond(
                stage.cache_status != "",
                rx.text(
                    "取得経路: " + stage.cache_status,
                    size="1",
                    color=rx.color("gray", 9),
                ),
                rx.fragment(),
            ),
            rx.cond(
                stage.fetched_at != "",
                rx.text(
                    "更新: " + stage.fetched_at,
                    size="1",
                    color=rx.color("gray", 9),
                ),
                rx.fragment(),
            ),
            rx.cond(
                stage.error_message != "",
                rx.callout(
                    stage.error_message,
                    icon="triangle_alert",
                    color_scheme="amber",
                    width="100%",
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


def _update_action_bar() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text("更新対象", weight="bold", size="2"),
            rx.button(
                rx.icon("layers", size=16),
                "全部更新",
                on_click=MarketState.refresh_market_details,
                loading=MarketState.is_fetching_details,
                variant="surface",
            ),
            rx.button(
                rx.icon("git-branch", size=16),
                "Theme/Flow",
                on_click=MarketState.refresh_theme_flow,
                loading=MarketState.is_fetching_details,
                variant="surface",
            ),
            rx.button(
                rx.icon("activity", size=16),
                "Vol/Sentiment",
                on_click=MarketState.refresh_volatility_sentiment,
                loading=MarketState.is_fetching_details,
                variant="surface",
            ),
            rx.button(
                rx.icon("shield-alert", size=16),
                "Credit/Risk",
                on_click=MarketState.refresh_credit_distortion,
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
            gap="0.5rem",
            wrap="wrap",
            align="center",
            width="100%",
        ),
        width="100%",
        margin_bottom="1rem",
    )


def _market_decision_summary() -> rx.Component:
    return rx.grid(
        _summary_tile(
            "市場姿勢",
            rx.cond(
                MarketState.strategy_regime.label != "",
                MarketState.strategy_regime.label,
                rx.cond(
                    MarketState.ibd_regime.label != "",
                    MarketState.ibd_regime.label,
                    "未判定",
                ),
            ),
            rx.cond(
                MarketState.strategy_regime.rationale != "",
                MarketState.strategy_regime.rationale,
                MarketState.ibd_regime.rationale,
            ),
            "blue",
        ),
        _summary_tile(
            "リスク枠",
            rx.cond(
                MarketState.strategy_regime.risk_budget != "",
                MarketState.strategy_regime.risk_budget,
                MarketState.ibd_regime.exposure_level,
            ),
            rx.cond(
                MarketState.regime_playbook.stance != "",
                MarketState.regime_playbook.stance,
                "詳細更新後に市場スタンスを表示します。",
            ),
            "green",
        ),
        _summary_tile(
            "主要ドライバー",
            rx.cond(
                MarketState.market_drivers_summary != "",
                MarketState.market_drivers_summary,
                "未取得",
            ),
            rx.cond(
                MarketState.volatility_summary != "",
                MarketState.volatility_summary,
                MarketState.trend_ranking_summary,
            ),
            "cyan",
        ),
        _summary_tile(
            "未取得/要更新",
            _complete_label(MarketState.option_complete_status),
            rx.cond(
                MarketState.option_fallback_reason != "",
                MarketState.option_fallback_reason,
                "ステージカードで更新状況を確認できます。",
            ),
            "amber",
        ),
        columns=rx.breakpoints(initial="1", md="2", xl="4"),
        spacing="3",
        width="100%",
        margin_bottom="1rem",
    )


def _summary_tile(title: str, value, detail, color: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, size="1", color=rx.color("gray", 10), weight="bold"),
            rx.text(
                value,
                size="5",
                weight="bold",
                font_variant_numeric="tabular-nums",
            ),
            rx.text(detail, size="1", color=rx.color("gray", 10)),
            spacing="1",
            align_items="start",
            width="100%",
        ),
        border_left=f"4px solid {rx.color(color, 8)}",
        width="100%",
    )


def _details_accordion() -> rx.Component:
    return rx.accordion.root(
        _detail_item(
            header="概要",
            content=rx.vstack(
                watch_indices_strip(),
                market_risk_intelligence_panel(),
                market_monitor(),
                width="100%",
                spacing="4",
            ),
        ),
        _detail_item(
            header="トレンド/テーマ",
            content=rx.vstack(
                trend_ranking_panel(),
                momentum_monitor_component(),
                theme_ranking_content(embedded=True),
                width="100%",
                spacing="4",
            ),
        ),
        _detail_item(
            header="リスク/信用",
            content=rx.vstack(
                market_distortion_panel(),
                width="100%",
                spacing="4",
            ),
        ),
        _detail_item(
            header="オプション",
            content=option_analysis_component(),
        ),
        _detail_item(
            header="データ状態",
            content=rx.vstack(
                data_status_panel(MarketState.data_status),
                provenance_panel(MarketState.provenance),
                width="100%",
                spacing="3",
            ),
        ),
        type="multiple",
        default_value=["概要"],
        width="100%",
        display="flex",
        flex_direction="column",
        gap="0.5rem",
    )


def _detail_item(*, header: str, content: rx.Component) -> rx.Component:
    return rx.accordion.item(
        header=header,
        content=content,
        bg=rx.color("gray", 1),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="10px",
        overflow="hidden",
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
                rx.cond(value == "failed", "取得失敗", "未取得"),
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
        ),
        _market_decision_summary(),
        _update_action_bar(),
        _stage_status_strip(),
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
            _details_accordion(),
        ),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
