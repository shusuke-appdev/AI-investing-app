import reflex as rx

from frontend.components.ui_primitives import empty_state, page_header, section_heading
from frontend.state.theme_state import ThemeItem, ThemeState, ThemeStock
from frontend.template import template


def _render_stock_row(stock: ThemeStock) -> rx.Component:
    """構成銘柄の1行を描画する"""
    perf = stock.performance
    return rx.link(
        rx.hstack(
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
            rx.icon("arrow-right", size=14, color=rx.color("gray", 9)),
            width="100%",
            padding_y="0.5rem",
            padding_x="0.25rem",
            border_bottom=f"1px solid {rx.color('gray', 3)}",
            align_items="center",
            min_height="44px",
            _hover={"bg": rx.color("gray", 2)},
        ),
        href="/stock?ticker=" + stock.ticker,
        aria_label=stock.display_name + "の個別銘柄分析を開く",
        underline="none",
        width="100%",
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
                theme_data.leader_ticker != "",
                rx.callout(
                    rx.hstack(
                        rx.text(
                            "テーマ内パフォーマンス上位（同期間）",
                            size="1",
                            weight="bold",
                        ),
                        rx.link(
                            theme_data.leader_display_name,
                            href="/stock?ticker=" + theme_data.leader_ticker,
                            weight="bold",
                            underline="hover",
                        ),
                        rx.badge(
                            rx.cond(theme_data.leader_performance > 0, "+", ""),
                            theme_data.leader_performance,
                            "%",
                            color_scheme=rx.cond(
                                theme_data.leader_performance >= 0, "green", "red"
                            ),
                            variant="surface",
                        ),
                        spacing="2",
                        wrap="wrap",
                        align_items="center",
                    ),
                    icon="chart-no-axes-combined",
                    color_scheme="blue",
                    width="100%",
                ),
                rx.fragment(),
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


def _theme_column(title: str, themes, color: str, empty_message: str) -> rx.Component:
    return rx.vstack(
        rx.heading(
            title,
            size="5",
            as_="h2",
            margin_bottom="1rem",
            color=rx.color(color, 11),
        ),
        rx.cond(
            themes.length() > 0,
            rx.foreach(themes, lambda theme, idx: _render_theme_item(theme, idx)),
            rx.callout(
                empty_message,
                icon="info",
                color_scheme="gray",
                width="100%",
            ),
        ),
        width="100%",
    )


def _theme_operation_panel(period_control: rx.Component) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.vstack(
                rx.text("期間", size="1", weight="bold", color="gray"),
                rx.box(
                    period_control,
                    width="100%",
                    max_width="100%",
                    overflow_x="auto",
                    padding_bottom="0.15rem",
                ),
                spacing="1",
                align_items="start",
                flex=rx.breakpoints(initial="0 1 auto", md="2 1 480px"),
                min_width="0",
            ),
            rx.vstack(
                rx.text("方向", size="1", weight="bold", color="gray"),
                rx.segmented_control.root(
                    rx.segmented_control.item("すべて", value="all"),
                    rx.segmented_control.item("上昇", value="up"),
                    rx.segmented_control.item("下落", value="down"),
                    value=ThemeState.direction_filter,
                    on_change=ThemeState.set_direction_filter,
                    size="2",
                ),
                spacing="1",
                align_items="start",
                flex=rx.breakpoints(initial="0 1 auto", md="1 1 240px"),
                min_width="0",
            ),
            rx.vstack(
                rx.text("並び替え", size="1", weight="bold", color="gray"),
                rx.segmented_control.root(
                    rx.segmented_control.item("騰落率", value="performance"),
                    rx.segmented_control.item("取得率", value="coverage"),
                    value=ThemeState.sort_mode,
                    on_change=ThemeState.set_sort_mode,
                    size="2",
                ),
                spacing="1",
                align_items="start",
                flex=rx.breakpoints(initial="0 1 auto", md="1 1 210px"),
                min_width="0",
            ),
            direction=rx.breakpoints(initial="column", md="row"),
            wrap="wrap",
            gap="1rem",
            width="100%",
            align=rx.breakpoints(initial="stretch", md="end"),
        ),
        width="100%",
        margin_bottom="0.75rem",
    )


def _ranking_help() -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header="ランキングの読み方",
            content=rx.vstack(
                rx.text(
                    "騰落率は、取得できた構成銘柄を同じ期間で比較した集計値です。",
                    size="2",
                ),
                rx.text(
                    "取得率が低いテーマは一部銘柄だけの結果になり得るため、順位より先に取得率と警告を確認してください。",
                    size="2",
                ),
                rx.text(
                    "リーダー銘柄は同期間の構成銘柄内で騰落率が最も高い銘柄で、売買推奨ではありません。",
                    size="2",
                ),
                rx.text(
                    "研究用途です。取得不能・不足データは0として補完しません。",
                    size="1",
                    color=rx.color("gray", 10),
                ),
                width="100%",
                align_items="start",
                spacing="2",
            ),
        ),
        type="single",
        collapsible=True,
        width="100%",
        margin_bottom="0.75rem",
    )


def theme_ranking_content(*, embedded: bool = False) -> rx.Component:
    """トレンド/テーマの詳細内容を描画する。"""

    period_control = rx.segmented_control.root(
        rx.foreach(
            ThemeState.periods,
            lambda period: rx.segmented_control.item(period, value=period),
        ),
        value=ThemeState.selected_period,
        on_change=ThemeState.set_period,
        size="2",
        radius="large",
    )
    header = (
        section_heading(
            "トレンド/テーマ",
            "選択市場の構成銘柄を同じ期間で比較します。",
        )
        if embedded
        else page_header(
            "トレンド/テーマ",
            "選択市場の構成銘柄を同じ期間で比較します。",
        )
    )

    return rx.vstack(
        header,
        _theme_operation_panel(period_control),
        _ranking_help(),
        rx.flex(
            rx.badge(
                "対象市場: ",
                ThemeState.requested_market_label,
                color_scheme="blue",
                variant="surface",
            ),
            rx.badge(
                "期間: ",
                ThemeState.selected_period,
                color_scheme="gray",
                variant="surface",
            ),
            rx.cond(
                ThemeState.loaded_at != "",
                rx.text(
                    "更新: " + ThemeState.loaded_at,
                    size="1",
                    color=rx.color("gray", 9),
                ),
                rx.fragment(),
            ),
            rx.spacer(),
            width="100%",
            align_items="center",
            gap="0.5rem",
            wrap="wrap",
            margin_bottom="0.75rem",
        ),
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
        rx.cond(
            ThemeState.warning_msg != "",
            rx.callout(
                ThemeState.warning_msg,
                icon="info",
                color_scheme="amber",
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
                    "トレンド/テーマを計算中...",
                    margin_top="1rem",
                    color="gray",
                ),
                direction="column",
                width="100%",
                height="300px",
            ),
            rx.cond(
                ThemeState.ranked_themes.length() > 0,
                rx.cond(
                    ThemeState.direction_filter == "all",
                    rx.grid(
                        _theme_column(
                            "上昇テーマ Top 10",
                            ThemeState.top_10_themes,
                            "green",
                            "この条件に該当する上昇テーマはありません。",
                        ),
                        _theme_column(
                            "下落テーマ Top 10",
                            ThemeState.bottom_10_themes,
                            "red",
                            "この条件に該当する下落テーマはありません。",
                        ),
                        columns=rx.breakpoints(initial="1", lg="2"),
                        spacing="6",
                        width="100%",
                    ),
                    rx.cond(
                        ThemeState.direction_filter == "up",
                        _theme_column(
                            "上昇テーマ Top 10",
                            ThemeState.top_10_themes,
                            "green",
                            "この条件に該当する上昇テーマはありません。",
                        ),
                        _theme_column(
                            "下落テーマ Top 10",
                            ThemeState.bottom_10_themes,
                            "red",
                            "この条件に該当する下落テーマはありません。",
                        ),
                    ),
                ),
                empty_state(
                    "ランキングを表示できません",
                    "対象市場・期間の価格データが不足しているか、取得先が一時的に利用できません。条件を確認して再試行してください。",
                    "list-ordered",
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "再試行",
                        on_click=ThemeState.fetch_themes,
                        loading=ThemeState.is_fetching,
                        variant="surface",
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
    """トレンド/テーマ画面"""

    return theme_ranking_content()
