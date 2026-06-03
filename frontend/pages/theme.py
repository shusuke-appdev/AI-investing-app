import reflex as rx

from frontend.state.theme_state import ThemeItem, ThemeState, ThemeStock
from frontend.template import template


def _render_stock_row(stock: ThemeStock) -> rx.Component:
    """構成銘柄の1行を描画する"""
    perf = stock.performance
    return rx.hstack(
        rx.text(stock.display_name, size="2", color=rx.color("gray", 11)),
        rx.spacer(),
        rx.text(
            rx.cond(perf > 0, "+", ""),
            perf,
            "%",
            size="2",
            color=rx.cond(perf >= 0, rx.color("green", 11), rx.color("red", 11)),
            weight="medium",
        ),
        width="100%",
        padding_y="0.25rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
    )


def _render_theme_item(theme_data: ThemeItem, index: int) -> rx.Component:
    """個別のテーマ項目を描画する"""
    perf = theme_data.performance
    perf_color = rx.cond(perf >= 0, "green", "red")
    perf_icon = rx.cond(perf >= 0, "📈", "📉")

    header_content = rx.hstack(
        rx.badge(index + 1, color_scheme="gray", variant="solid", radius="full"),
        rx.text(theme_data.theme, weight="bold", size="3"),
        rx.spacer(),
        rx.hstack(
            rx.text(perf_icon),
            rx.text(
                rx.cond(perf > 0, "+", ""),
                perf,
                "%",
                color=rx.color(perf_color, 11),
                weight="bold",
            ),
            spacing="1",
        ),
        align_items="center",
        width="100%",
    )

    stocks_content = rx.cond(
        theme_data.stocks.length() > 0,
        rx.vstack(
            rx.foreach(theme_data.stocks, _render_stock_row),
            width="100%",
            padding_top="0.5rem",
        ),
        rx.text("銘柄データなし", size="2", color="gray"),
    )

    return rx.accordion.root(
        rx.accordion.item(
            header=header_content,
            content=stocks_content,
            value=theme_data.theme,
        ),
        type="single",
        collapsible=True,
        width="100%",
        margin_bottom="0.5rem",
        bg="white",
        border_radius="md",
        box_shadow="0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
    )


def theme_ranking_content() -> rx.Component:
    """詳細版テーマランキングの内容を描画する。"""

    return rx.vstack(
        # ヘッダー領域
        rx.hstack(
            rx.heading("🎯 テーマ別トレンド", size="7"),
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
                    "テーマ別パフォーマンスを計算中...",
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
                            "🏆 Top 10 Winners",
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
                            "📉 Top 10 Losers",
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
                    columns="2",
                    spacing="6",
                    width="100%",
                ),
                rx.center(
                    rx.text("テーマデータがありません", color="gray"),
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
    """テーマ（Theme）別トレンド画面"""

    return theme_ranking_content()
