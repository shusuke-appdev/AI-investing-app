"""Comprehensive theme ranking page."""

import reflex as rx

from frontend.components.ui_primitives import empty_state, page_header, section_heading
from frontend.state.theme_state import ThemeItem, ThemeState, ThemeStock
from frontend.template import template


def _metric(label: str, value, maximum: str) -> rx.Component:
    return rx.box(
        rx.text(label, size="1", color=rx.color("gray", 10)),
        rx.text(value, maximum, size="3", weight="bold"),
        padding="0.55rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="0.55rem",
        min_width="0",
    )


def _return_badge(label: str, value, rank) -> rx.Component:
    return rx.badge(
        label,
        " ",
        rx.cond(value > 0, "+", ""),
        value,
        "% / #",
        rank,
        color_scheme=rx.cond(value >= 0, "green", "red"),
        variant="surface",
    )


def _stock_row(stock: ThemeStock) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.text(stock.display_name, size="2", weight="medium", flex="1"),
            rx.badge(
                stock.performance,
                "%",
                color_scheme=rx.cond(stock.performance >= 0, "green", "red"),
            ),
            rx.icon("arrow-right", size=14),
            width="100%",
            padding_y="0.4rem",
        ),
        href="/stock?ticker=" + stock.ticker,
        underline="none",
        width="100%",
    )


def _theme_card(item: ThemeItem) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.flex(
                rx.hstack(
                    rx.badge("#", item.rank, color_scheme="gray", variant="solid"),
                    rx.vstack(
                        rx.text(item.theme, size="4", weight="bold"),
                        rx.text(
                            item.component_count,
                            "/",
                            item.total_components,
                            "銘柄を取得",
                            size="1",
                            color=rx.color("gray", 10),
                        ),
                        align_items="start",
                        spacing="0",
                    ),
                ),
                rx.vstack(
                    rx.text("総合点", size="1", color=rx.color("gray", 10)),
                    rx.text(item.total_score, "/100", size="6", weight="bold"),
                    align_items="end",
                    spacing="0",
                ),
                justify="between",
                width="100%",
            ),
            rx.grid(
                _metric("価格モメンタム", item.momentum_score, "/30"),
                _metric("市場相対強度", item.relative_strength_score, "/25"),
                _metric("資金注目度（代理）", item.attention_score, "/25"),
                _metric("広がり・持続性", item.breadth_score, "/20"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="2",
                width="100%",
            ),
            rx.flex(
                _return_badge("1週", item.performance_1w, item.rank_1w),
                _return_badge("1か月", item.performance_1m, item.rank_1m),
                _return_badge("6か月", item.performance_6m, item.rank_6m),
                rx.badge(
                    "順位加速 ",
                    item.rank_acceleration,
                    color_scheme=rx.cond(item.rank_acceleration >= 5, "amber", "gray"),
                    variant="soft",
                ),
                wrap="wrap",
                gap="0.4rem",
            ),
            rx.flex(
                rx.badge("取得率 1週 ", item.coverage_1w, "%", variant="soft"),
                rx.badge("1か月 ", item.coverage_1m, "%", variant="soft"),
                rx.badge("6か月 ", item.coverage_6m, "%", variant="soft"),
                rx.cond(
                    item.proxy_ticker != "",
                    rx.badge(
                        "ETF確認 ",
                        item.proxy_ticker,
                        ": ",
                        item.proxy_confirmation,
                        color_scheme=rx.cond(
                            item.proxy_confirmation == "確認あり", "green", "amber"
                        ),
                        variant="surface",
                    ),
                    rx.fragment(),
                ),
                wrap="wrap",
                gap="0.4rem",
            ),
            rx.flex(
                rx.link(
                    rx.button("このテーマから候補を探す", variant="surface"),
                    href="/theme-leaders?theme=" + item.theme,
                    underline="none",
                ),
                rx.spacer(),
                rx.text(
                    "欠損値は0点に置き換えず順位対象外",
                    size="1",
                    color=rx.color("gray", 9),
                ),
                width="100%",
                align="center",
                wrap="wrap",
                gap="0.5rem",
            ),
            rx.cond(
                item.stocks.length() > 0,
                rx.accordion.root(
                    rx.accordion.item(
                        header="計測代表銘柄を表示",
                        content=rx.vstack(
                            rx.foreach(item.stocks, _stock_row),
                            width="100%",
                            spacing="0",
                        ),
                    ),
                    type="single",
                    collapsible=True,
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def _ranking_help() -> rx.Component:
    return rx.callout(
        rx.vstack(
            rx.text("ランキングの読み方", weight="bold", size="2"),
            rx.text(
                "総合順位は価格30点、市場相対強度25点、資金注目度（価格・出来高による代理）25点、広がり・持続性20点です。",
                size="2",
            ),
            rx.text(
                "実際の純資金流入額ではありません。構成銘柄の中央値と市場内パーセンタイルで比較し、ETFは確認表示だけで採点しません。",
                size="2",
            ),
            rx.text(
                "研究用途の優先順位であり、将来予測や売買推奨ではありません。",
                size="1",
                color=rx.color("gray", 10),
            ),
            align_items="start",
            spacing="1",
        ),
        icon="info",
        color_scheme="blue",
        width="100%",
    )


def theme_ranking_content(*, embedded: bool = False) -> rx.Component:
    header = (
        section_heading(
            "トレンド/テーマ：総合順位",
            "価格だけでなく相対強度、価格・出来高による注目度、値動きの広がりを統合します。",
        )
        if embedded
        else page_header(
            "トレンド/テーマ：総合順位",
            "価格だけでなく相対強度、価格・出来高による注目度、値動きの広がりを統合します。",
            rx.button(
                "上位・急浮上テーマから候補を探す",
                variant="solid",
                on_click=rx.redirect("/theme-leaders"),
            ),
        )
    )
    return rx.vstack(
        header,
        _ranking_help(),
        rx.flex(
            rx.badge(
                "対象市場: ",
                ThemeState.requested_market_label,
                color_scheme="blue",
                variant="surface",
            ),
            rx.cond(
                ThemeState.loaded_at != "",
                rx.text("更新: " + ThemeState.loaded_at, size="1", color="gray"),
                rx.fragment(),
            ),
            width="100%",
            wrap="wrap",
            gap="0.5rem",
            margin_y="0.75rem",
        ),
        rx.cond(
            ThemeState.error_msg != "",
            rx.callout(
                ThemeState.error_msg,
                icon="triangle-alert",
                color_scheme="red",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.warning_msg != "",
            rx.callout(
                ThemeState.warning_msg,
                icon="info",
                color_scheme="amber",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.is_fetching,
            rx.center(rx.spinner(size="3"), min_height="280px", width="100%"),
            rx.cond(
                ThemeState.ranked_themes.length() > 0,
                rx.grid(
                    rx.foreach(ThemeState.ranked_themes, _theme_card),
                    columns=rx.breakpoints(initial="1", xl="2"),
                    spacing="4",
                    width="100%",
                ),
                empty_state(
                    "総合順位を表示できません",
                    "必要な価格・出来高または市場ベンチマークが不足しています。",
                    "list-ordered",
                    rx.button(
                        "再試行",
                        on_click=ThemeState.fetch_themes,
                        loading=ThemeState.is_fetching,
                    ),
                ),
            ),
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )


@template
def theme_page() -> rx.Component:
    return theme_ranking_content()
