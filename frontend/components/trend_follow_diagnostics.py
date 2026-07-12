import reflex as rx

from frontend.components.ui_primitives import evaluation_badge
from frontend.state.stock_state import StockState


def _metric(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="gray", weight="bold"),
        rx.text(value, size="4", weight="bold"),
        spacing="1",
        align_items="start",
    )


def trend_follow_diagnostics_panel() -> rx.Component:
    diagnostics = StockState.trend_follow_diagnostics

    return rx.cond(
        diagnostics.contains("diagnostic_rating"),
        rx.box(
            rx.hstack(
                rx.heading("トレンド追随診断", size="5", as_="h2"),
                rx.spacer(),
                evaluation_badge(
                    diagnostics["rating_display"].to(str),
                    rx.cond(
                        diagnostics["diagnostic_rating"].to(str) == "Robust",
                        "green",
                        rx.cond(
                            diagnostics["diagnostic_rating"].to(str) == "Fragile",
                            "red",
                            rx.cond(
                                diagnostics["diagnostic_rating"].to(str) == "Watch",
                                "orange",
                                "gray",
                            ),
                        ),
                    ),
                ),
                width="100%",
                align_items="center",
                margin_bottom="1rem",
            ),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.heading("堅牢性", size="4", as_="h3"),
                        rx.text(
                            diagnostics["current_state_display"].to(str),
                            size="2",
                            color="gray",
                        ),
                        rx.grid(
                            _metric(
                                "戦略リターン",
                                diagnostics["strategy_total_return_display"].to(str),
                            ),
                            _metric(
                                "買い持ち",
                                diagnostics["buy_hold_total_return_display"].to(str),
                            ),
                            _metric(
                                "期間外アルファ",
                                diagnostics["oos_alpha_display"].to(str),
                            ),
                            _metric(
                                "ランダム比較順位",
                                diagnostics["random_percentile_display"].to(str),
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("失敗耐性テスト", size="4", as_="h3"),
                        rx.grid(
                            _metric(
                                "最大ドローダウン",
                                diagnostics["strategy_max_drawdown_display"].to(str),
                            ),
                            _metric(
                                "最大含み損期間",
                                diagnostics["strategy_tuw_display"].to(str),
                            ),
                            _metric(
                                "プロフィットファクター",
                                diagnostics["strategy_profit_factor_display"].to(str),
                            ),
                            _metric(
                                "上位5%除外後",
                                diagnostics["top5_removed_display"].to(str),
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.markdown(diagnostics["warnings_display"].to(str)),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            rx.text(
                "診断専用です。既存シグナルや売買判断を置き換えるものではありません。",
                size="1",
                color="gray",
                margin_top="0.75rem",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.box(),
    )
