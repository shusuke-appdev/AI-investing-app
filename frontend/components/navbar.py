import reflex as rx


def navbar() -> rx.Component:
    """Top utility bar shared by every page."""
    return rx.hstack(
        rx.hstack(
            rx.icon("activity", size=24, color=rx.color("accent", 9)),
            rx.vstack(
                rx.text("AI Investing", size="3", weight="bold"),
                rx.text(
                    "調査ワークスペース",
                    size="1",
                    color=rx.color("gray", 10),
                ),
                spacing="0",
                align_items="start",
            ),
            align_items="center",
            spacing="3",
        ),
        rx.spacer(),
        rx.color_mode.button(
            aria_label="表示テーマを切り替える",
            min_width="44px",
            min_height="44px",
        ),
        width="100%",
        padding=rx.breakpoints(initial="0.75rem 1rem", md="1rem 1.5rem"),
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        justify="between",
        align_items="center",
        bg=rx.color("gray", 1),
        position="sticky",
        top="0",
        z_index="10",
        display=rx.breakpoints(initial="none", lg="flex"),
    )
