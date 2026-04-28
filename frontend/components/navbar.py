import reflex as rx

def navbar() -> rx.Component:
    """上部に配置されるナビゲーションバー"""
    return rx.hstack(
        rx.hstack(
            rx.icon("activity", size=24, color=rx.color("accent", 9)),
            rx.heading("AI Investing Dashboard", size="6", weight="bold"),
            align_items="center",
            spacing="3",
        ),
        rx.spacer(),
        rx.color_mode.button(),
        width="100%",
        padding="1rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        justify="between",
        align_items="center",
        bg=rx.color("gray", 1),
    )
