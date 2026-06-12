import reflex as rx

from frontend.state.stock_state import StockState


def fomo_volatility_panel() -> rx.Component:
    """Display the high-volatility stock state beside existing diagnostics."""

    return rx.cond(
        StockState.fomo_label != "",
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("FOMO Volatility Regime", size="4"),
                    rx.spacer(),
                    rx.badge(
                        StockState.fomo_label,
                        color_scheme=rx.cond(
                            StockState.fomo_risk_level == "critical",
                            "red",
                            rx.cond(
                                StockState.fomo_risk_level == "high",
                                "orange",
                                rx.cond(
                                    StockState.fomo_risk_level == "elevated",
                                    "amber",
                                    "green",
                                ),
                            ),
                        ),
                        variant="surface",
                    ),
                    width="100%",
                ),
                rx.text(
                    "高ボラ銘柄の現在状態を示す補助診断です。単独の売買シグナルではありません。",
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.foreach(
                    StockState.fomo_evidence,
                    lambda item: rx.text("• " + item, size="2"),
                ),
                rx.callout(
                    "確認条件: " + StockState.fomo_confirmation,
                    icon="circle-check",
                    color_scheme="blue",
                    width="100%",
                ),
                rx.callout(
                    "無効化条件: " + StockState.fomo_invalidation,
                    icon="triangle-alert",
                    color_scheme="amber",
                    width="100%",
                ),
                align_items="start",
                width="100%",
                spacing="3",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.fragment(),
    )
