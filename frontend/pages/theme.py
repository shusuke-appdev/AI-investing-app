import reflex as rx

from frontend.state.theme_state import ThemeItem, ThemeState, ThemeStock
from frontend.template import template


def _render_stock_row(stock: ThemeStock) -> rx.Component:
    """構成銘柄の1行を描画する"""
    perf = stock.performance
    return rx.hstack(
        rx.text(
            stock.display_name,
            size="2",
            color=rx.color("gray", 12),
            weight="medium",
            flex="1",
        ),
        rx.spacer(),
        rx.badge(
            rx.cond(perf > 0, "+", ""),
            perf,
            "%",
            color_scheme=rx.cond(perf >= 0, "green", "red"),
            variant="surface",
        ),
        width="100%",
        padding_y="0.35rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        align_items="center",
    )


def _theme_stocks_accordion(theme_data: ThemeItem) -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header="構成銘柄を表示",
            content=rx.vstack(
                rx.foreach(theme_data.stocks, _render_stock_row),
                width="100%",
                spacing="0",
            ),
        ),
        type="single",
        collapsible=True,
        width="100%",
    )


def _render_theme_item(theme_data: ThemeItem, index: int) -> rx.Component:
    """個別のテーマ項目を描画する"""
    perf = theme_data.performance

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    rx.text("#", (index + 1).to_string()),
                    color_scheme="gray",
                    variant="solid",
                    radius="full",
                ),
                rx.vstack(
                    rx.text(theme_data.theme, weight="bold", size="3"),
                    rx.hstack(
                        rx.badge(
                            theme_data.component_count,
                            "/",
                            theme_data.total_components,
                            " 銘柄",
                            color_scheme="gray",
                            variant="soft",
                        ),
                        rx.badge(
                            "取得率 ",
                            theme_data.coverage,
                            "%",
                            color_scheme="gray",
                            variant="soft",
                        ),
                        spacing="2",
                    ),
                    align_items="start",
                    spacing="1",
                    flex="1",
                ),
                rx.badge(
                    rx.cond(perf > 0, "+", ""),
                    perf,
                    "%",
                    color_scheme=rx.cond(perf >= 0, "green", "red"),
                    size="3",
                    variant="surface",
                ),
                width="100%",
                align_items="start",
                spacing="3",
            ),
            rx.cond(
                theme_data.stocks.length() > 0,
                _theme_stocks_accordion(theme_data),
                rx.text("銘柄データなし", size="2", color="gray"),
            ),
            width="100%",
            align_items="start",
            spacing="2",
        ),
        width="100%",
        padding="0.8rem",
    )


def theme_ranking_content() -> rx.Component:
    """詳細版テーマランキングの内容を描画する。"""

    return rx.vstack(
        # ヘッダー領域
        rx.hstack(
            rx.hstack(
                rx.icon("list-ordered", size=26, color=rx.color("blue", 9)),
                rx.heading("テーマランキング", size="7"),
                align_items="center",
                spacing="2",
            ),
            rx.spacer(),
            # 期間選択
            rx.segmented_control.root(
                rx.foreach(
                    ThemeState.periods,
                    lambda period: rx.segmented_control.item(period, value=period),
                ),
                value=ThemeState.selected_period,
                on_change=ThemeState.set_period,
                size="2",
                radius="large",
            ),
            width="100%",
            align_items="center",
            margin_bottom="2rem",
        ),
        # エラーメッセージ
        rx.cond(
            ThemeState.error_msg != "",
            rx.callout(
                ThemeState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # ローディングまたはデータ表示
        rx.cond(
            ThemeState.is_fetching,
            rx.center(
                rx.spinner(size="3"),
                rx.text(
                    "テーマランキングを計算中...",
                    margin_top="1rem",
                    color="gray",
                ),
                direction="column",
                width="100%",
                height="300px",
            ),
            rx.cond(
                ThemeState.ranked_themes.length() > 0,
                rx.grid(
                    # Top 10
                    rx.vstack(
                        rx.heading(
                            "上昇テーマ Top 10",
                            size="5",
                            margin_bottom="1rem",
                            color=rx.color("green", 11),
                        ),
                        rx.foreach(
                            ThemeState.top_10_themes,
                            lambda theme, idx: _render_theme_item(theme, idx),
                        ),
                        width="100%",
                    ),
                    # Bottom 10
                    rx.vstack(
                        rx.heading(
                            "下落テーマ Top 10",
                            size="5",
                            margin_bottom="1rem",
                            color=rx.color("red", 11),
                        ),
                        rx.foreach(
                            ThemeState.bottom_10_themes,
                            lambda theme, idx: _render_theme_item(theme, idx),
                        ),
                        width="100%",
                    ),
                    columns=rx.breakpoints(initial="1", lg="2"),
                    spacing="6",
                    width="100%",
                ),
                rx.center(
                    rx.text("テーマランキングデータがありません", color="gray"),
                    height="200px",
                    width="100%",
                ),
            ),
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )


@template
def theme_page() -> rx.Component:
    """テーマランキング画面"""

    return theme_ranking_content()
