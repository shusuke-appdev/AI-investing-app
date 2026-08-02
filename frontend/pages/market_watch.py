import reflex as rx

from frontend.components.flash_summary import (
    market_distortion_panel,
    market_monitor,
    watch_indices_strip,
)
from frontend.components.market_risk_intelligence import market_risk_intelligence_panel
from frontend.components.momentum_display import momentum_monitor_component
from frontend.components.option_analysis import option_analysis_component
from frontend.components.ui_primitives import page_header, section_heading
from frontend.state.market_state import MarketState
from frontend.template import template


def _action_button(label: str, icon: str, handler, loading) -> rx.Component:
    return rx.button(
        rx.icon(icon, size=16),
        label,
        on_click=handler,
        loading=loading,
        variant="surface",
        min_height="44px",
    )


def _summary_tile(title: str, value, detail, color: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, size="1", color=rx.color("gray", 10), weight="bold"),
            rx.text(value, size="4", weight="bold"),
            rx.text(detail, size="1", color=rx.color("gray", 11)),
            spacing="1",
            align_items="start",
            width="100%",
        ),
        border_left=f"3px solid {rx.color(color, 8)}",
        width="100%",
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
                MarketState.sector_flow_summary != "",
                MarketState.sector_flow_summary,
                MarketState.trend_ranking_summary,
            ),
            "cyan",
        ),
        _summary_tile(
            "重要警戒",
            rx.cond(
                MarketState.top_risk_summary != "",
                MarketState.top_risk_summary,
                "顕著な警戒は未判定",
            ),
            rx.cond(
                MarketState.volatility_summary != "",
                MarketState.volatility_summary,
                "詳細更新でリスク情報を補完します。",
            ),
            "amber",
        ),
        columns=rx.breakpoints(initial="1", md="2", xl="4"),
        spacing="3",
        width="100%",
    )


def _theme_row(item) -> rx.Component:
    return rx.hstack(
        rx.badge("#" + item.rank.to_string(), color_scheme="blue", variant="surface"),
        rx.text(item.theme, weight="bold", size="2", flex="1"),
        rx.text(item.performance_1m_str, size="2", color=rx.color("gray", 11)),
        rx.badge(item.total_score_str, color_scheme="gray", variant="surface"),
        width="100%",
        align_items="center",
        min_height="38px",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _top_themes() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.text("上位5テーマ", weight="bold", size="3"),
                    rx.text(
                        MarketState.trend_ranking_summary,
                        size="1",
                        color=rx.color("gray", 10),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.link(
                    rx.button(
                        "詳細はトレンド/テーマへ",
                        rx.icon("arrow-right", size=15),
                        variant="ghost",
                        min_height="44px",
                    ),
                    href="/theme",
                    underline="none",
                ),
                width="100%",
                align_items="center",
                wrap="wrap",
            ),
            rx.cond(
                MarketState.top_theme_items.length() > 0,
                rx.vstack(
                    rx.foreach(MarketState.top_theme_items, _theme_row),
                    width="100%",
                    spacing="0",
                ),
                rx.text(
                    "上位テーマは概要更新後に表示します。全構成銘柄の比較はトレンド/テーマで取得します。",
                    size="2",
                    color=rx.color("gray", 10),
                ),
            ),
            width="100%",
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )


def _detail_header(label: str, handler, loading) -> rx.Component:
    return rx.hstack(
        rx.text(label, weight="bold", size="3", flex="1"),
        _action_button("この項目を更新", "refresh-cw", handler, loading),
        width="100%",
        align_items="center",
        wrap="wrap",
    )


def _details_accordion() -> rx.Component:
    return rx.box(
        section_heading(
            "必要なときだけ詳細を確認",
            "概要は常時表示し、取得負荷の高い信用・予測・オプションは明示更新します。",
        ),
        rx.vstack(
            _detail_item(
                header="市場レジーム・資金フロー",
                content=rx.vstack(
                    _detail_header(
                        "市場レジーム・資金フロー",
                        MarketState.refresh_theme_flow,
                        MarketState.is_fetching_details,
                    ),
                    market_monitor(),
                    momentum_monitor_component(),
                    width="100%",
                    spacing="4",
                ),
            ),
            _detail_item(
                header="リスク・信用・予測",
                content=rx.vstack(
                    _detail_header(
                        "リスク・信用・予測",
                        MarketState.refresh_credit_distortion,
                        MarketState.is_fetching_details,
                    ),
                    market_risk_intelligence_panel(),
                    market_distortion_panel(),
                    width="100%",
                    spacing="4",
                ),
            ),
            _detail_item(
                header="オプション",
                content=rx.vstack(
                    _detail_header(
                        "オプション",
                        MarketState.refresh_options,
                        MarketState.is_fetching_options,
                    ),
                    option_analysis_component(),
                    width="100%",
                    spacing="4",
                ),
            ),
            width="100%",
            spacing="3",
        ),
        width="100%",
    )


def _detail_item(*, header: str, content: rx.Component) -> rx.Component:
    return rx.el.details(
        rx.el.summary(
            header,
            cursor="pointer",
            font_weight="700",
            padding="1rem",
        ),
        rx.box(content, padding="0 1rem 1rem"),
        bg=rx.color("gray", 2),
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius="12px",
        overflow="hidden",
    )


def _freshness_footer() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.hstack(
                rx.icon("clock-3", size=16, color=rx.color("gray", 10)),
                rx.text(
                    rx.cond(
                        MarketState.context_fetched_at != "",
                        "最終更新 " + MarketState.context_fetched_at,
                        "最終更新 未取得",
                    ),
                    size="1",
                    color=rx.color("gray", 11),
                ),
                rx.cond(
                    MarketState.context_is_partial,
                    rx.badge("一部取得", color_scheme="amber", variant="surface"),
                    rx.fragment(),
                ),
                rx.cond(
                    MarketState.context_is_stale,
                    rx.badge("stale cache", color_scheme="orange", variant="surface"),
                    rx.fragment(),
                ),
                align_items="center",
                wrap="wrap",
            ),
            rx.spacer(),
            rx.link(
                "警告・来歴・所要時間はデータ品質へ", href="/data-quality", size="2"
            ),
            width="100%",
            align="center",
            gap="0.75rem",
            wrap="wrap",
        ),
        width="100%",
        variant="surface",
    )


@template
def market_watch_page() -> rx.Component:
    """市場監視ページ"""

    return rx.vstack(
        page_header(
            "市場監視",
            "判断に必要な概要を常時表示し、重い詳細だけを必要時に更新します。",
            _action_button(
                "概要を更新",
                "refresh-cw",
                MarketState.prepare_market_watch,
                MarketState.is_fetching_summary,
            ),
            _action_button(
                "詳細をすべて更新",
                "layers",
                MarketState.refresh_market_details,
                MarketState.is_fetching_details,
            ),
        ),
        rx.cond(
            MarketState.is_fetching_summary,
            rx.callout(
                "概要を更新中です。前回の表示を維持しています。",
                icon="refresh-cw",
                color_scheme="blue",
                width="100%",
            ),
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
        _market_decision_summary(),
        watch_indices_strip(),
        _top_themes(),
        _details_accordion(),
        _freshness_footer(),
        width="100%",
        max_width="1400px",
        margin="0 auto",
        spacing="4",
    )
