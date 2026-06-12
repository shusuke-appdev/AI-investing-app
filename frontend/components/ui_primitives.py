"""Shared Reflex UI primitives for consistent dashboard surfaces."""

import reflex as rx


def page_header(title: str, subtitle: str, *actions: rx.Component) -> rx.Component:
    return rx.flex(
        rx.vstack(
            rx.heading(title, size="7"),
            rx.text(subtitle, size="2", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
        ),
        rx.flex(
            *actions,
            gap="0.5rem",
            wrap="wrap",
            justify=rx.breakpoints(initial="start", md="end"),
        ),
        width="100%",
        direction=rx.breakpoints(initial="column", md="row"),
        justify="between",
        align=rx.breakpoints(initial="start", md="center"),
        gap="1rem",
        margin_bottom="1.5rem",
    )


def section_heading(
    title: str, description: str = "", *actions: rx.Component
) -> rx.Component:
    return rx.flex(
        rx.vstack(
            rx.heading(title, size="5"),
            rx.cond(
                description != "",
                rx.text(description, size="2", color=rx.color("gray", 10)),
                rx.fragment(),
            ),
            spacing="1",
            align_items="start",
        ),
        rx.flex(*actions, gap="0.5rem", wrap="wrap"),
        width="100%",
        justify="between",
        align=rx.breakpoints(initial="start", md="center"),
        direction=rx.breakpoints(initial="column", md="row"),
        gap="0.75rem",
        margin_bottom="1rem",
    )


def loading_state(message: str) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text(message, color=rx.color("gray", 10), size="2"),
            spacing="3",
            align_items="center",
        ),
        width="100%",
        min_height="260px",
    )


def empty_state(
    title: str, description: str, icon: str = "inbox", *actions: rx.Component
) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon(icon, size=28, color=rx.color("gray", 9)),
            rx.text(title, weight="bold", size="3"),
            rx.text(
                description,
                size="2",
                color=rx.color("gray", 10),
                text_align="center",
                max_width="520px",
            ),
            rx.flex(*actions, gap="0.5rem", wrap="wrap"),
            align_items="center",
            spacing="3",
        ),
        width="100%",
        min_height="180px",
        padding="2rem",
        border=f"1px dashed {rx.color('gray', 5)}",
        border_radius="12px",
        bg=rx.color("gray", 1),
    )
