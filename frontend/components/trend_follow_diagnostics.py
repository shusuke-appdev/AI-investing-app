import reflex as rx

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
                rx.heading("Trend-Follow Diagnostics", size="5"),
                rx.spacer(),
                rx.badge(
                    diagnostics["rating_display"].to(str),
                    color_scheme="teal",
                    variant="surface",
                ),
                width="100%",
                align_items="center",
                margin_bottom="1rem",
            ),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.heading("Robustness", size="4"),
                        rx.text(
                            diagnostics["current_state_display"].to(str),
                            size="2",
                            color="gray",
                        ),
                        rx.grid(
                            _metric(
                                "Strategy Return",
                                diagnostics["strategy_total_return_display"].to(str),
                            ),
                            _metric(
                                "Buy & Hold",
                                diagnostics["buy_hold_total_return_display"].to(str),
                            ),
                            _metric(
                                "OOS Alpha",
                                diagnostics["oos_alpha_display"].to(str),
                            ),
                            _metric(
                                "Random Percentile",
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
                        rx.heading("Failure Tests", size="4"),
                        rx.grid(
                            _metric(
                                "Max Drawdown",
                                diagnostics["strategy_max_drawdown_display"].to(str),
                            ),
                            _metric(
                                "Max TUW",
                                diagnostics["strategy_tuw_display"].to(str),
                            ),
                            _metric(
                                "Profit Factor",
                                diagnostics["strategy_profit_factor_display"].to(str),
                            ),
                            _metric(
                                "Top 5% Removed",
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
                "Diagnostic only. This does not replace the existing signal or create a trade recommendation.",
                size="1",
                color="gray",
                margin_top="0.75rem",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.box(),
    )
