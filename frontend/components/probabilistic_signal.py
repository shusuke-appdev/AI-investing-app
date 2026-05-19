import reflex as rx

from frontend.state.stock_state import StockState


def _metric(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="gray", weight="bold"),
        rx.text(value, size="4", weight="bold"),
        spacing="1",
        align_items="start",
    )


def probabilistic_signal_panel() -> rx.Component:
    signal = StockState.probabilistic_signal

    return rx.cond(
        signal.contains("signal_label"),
        rx.box(
            rx.heading("Probabilistic Stock Signal", size="5", margin_bottom="1rem"),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading("Signal Summary", size="4"),
                            rx.spacer(),
                            rx.badge(
                                signal["suggested_action"].to_string(),
                                color_scheme="blue",
                                variant="surface",
                            ),
                            width="100%",
                            align_items="center",
                        ),
                        rx.text(signal["signal_label"].to_string(), weight="medium"),
                        rx.grid(
                            _metric(
                                "Expected 5D Return",
                                signal["expected_5d_return_display"].to_string(),
                            ),
                            _metric(
                                "20D Excess Return",
                                signal[
                                    "expected_20d_excess_return_display"
                                ].to_string(),
                            ),
                            _metric(
                                "Probability Up",
                                signal["probability_up_display"].to_string(),
                            ),
                            _metric(
                                "Risk-adjusted Signal",
                                signal["risk_adjusted_signal_display"].to_string(),
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
                        rx.heading("Risk & Sizing", size="4"),
                        rx.grid(
                            _metric("Confidence", signal["confidence"].to_string()),
                            _metric(
                                "Regime Fit", signal["regime_fit_display"].to_string()
                            ),
                            _metric(
                                "Max Allocation",
                                signal["max_allocation_display"].to_string(),
                            ),
                            _metric(
                                "Vol Regime",
                                signal["volatility_regime"].to_string(),
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.markdown(signal["risk_notes_display"].to_string()),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                columns="2",
                spacing="4",
                width="100%",
                margin_bottom="1rem",
            ),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.heading("Why", size="4"),
                        rx.text("Positive factors", size="2", color="green"),
                        rx.markdown(signal["why_positive_display"].to_string()),
                        rx.text("Negative factors", size="2", color="red"),
                        rx.markdown(signal["why_negative_display"].to_string()),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("Validation", size="4"),
                        rx.grid(
                            _metric(
                                "Similar Samples",
                                signal["sample_size_display"].to_string(),
                            ),
                            _metric(
                                "Selected Model",
                                signal["selected_model"].to_string(),
                            ),
                            _metric("Trend Regime", signal["trend_regime"].to_string()),
                            _metric("Action", signal["suggested_action"].to_string()),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.text(signal["walk_forward_summary"].to_string(), size="2"),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.box(),
    )
