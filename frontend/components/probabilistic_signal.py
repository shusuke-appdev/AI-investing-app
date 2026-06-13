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


def probabilistic_signal_panel() -> rx.Component:
    signal = StockState.probabilistic_signal

    return rx.cond(
        signal.contains("signal_label"),
        rx.box(
            rx.heading("確率シグナル", size="5", margin_bottom="1rem"),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading("シグナル概要", size="4"),
                            rx.spacer(),
                            evaluation_badge(
                                signal["suggested_action_display"].to(str),
                                rx.cond(
                                    signal["suggested_action"].to(str) == "Add small",
                                    "green",
                                    rx.cond(
                                        signal["suggested_action"].to(str) == "Hold",
                                        "blue",
                                        rx.cond(
                                            signal["suggested_action"].to(str)
                                            == "Avoid",
                                            "red",
                                            "gray",
                                        ),
                                    ),
                                ),
                            ),
                            width="100%",
                            align_items="center",
                        ),
                        rx.text(
                            signal["signal_label_display"].to(str),
                            weight="bold",
                            size="5",
                        ),
                        rx.grid(
                            _metric(
                                "期待5日リターン",
                                signal["expected_5d_return_display"].to(str),
                            ),
                            _metric(
                                "20日超過リターン",
                                signal["expected_20d_excess_return_display"].to(str),
                            ),
                            _metric(
                                "上昇確率",
                                signal["probability_up_display"].to(str),
                            ),
                            _metric(
                                "リスク調整シグナル",
                                signal["risk_adjusted_signal_display"].to(str),
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
                        rx.heading("リスクと配分上限", size="4"),
                        rx.grid(
                            _metric("確信度", signal["confidence_display"].to(str)),
                            _metric("相場適合度", signal["regime_fit_display"].to(str)),
                            _metric(
                                "最大配分",
                                signal["max_allocation_display"].to(str),
                            ),
                            _metric(
                                "ボラティリティ環境",
                                signal["volatility_regime"].to(str),
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.markdown(signal["risk_notes_display"].to(str)),
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
                        rx.heading("判定理由", size="4"),
                        rx.text("プラス要因", size="2", color="green"),
                        rx.markdown(signal["why_positive_display"].to(str)),
                        rx.text("マイナス要因", size="2", color="red"),
                        rx.markdown(signal["why_negative_display"].to(str)),
                        width="100%",
                        align_items="start",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("検証情報", size="4"),
                        rx.grid(
                            _metric(
                                "類似サンプル数",
                                signal["sample_size_display"].to(str),
                            ),
                            _metric(
                                "採用モデル",
                                signal["selected_model"].to(str),
                            ),
                            _metric("トレンド環境", signal["trend_regime"].to(str)),
                            _metric(
                                "行動目安", signal["suggested_action_display"].to(str)
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.text(signal["walk_forward_summary"].to(str), size="2"),
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
