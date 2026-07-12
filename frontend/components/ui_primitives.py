"""Shared Reflex UI primitives for consistent dashboard surfaces."""

import reflex as rx


def private_mode_notice(feature_name: str) -> rx.Component:
    """Explain why a personal feature is unavailable in public mode."""

    return rx.vstack(
        page_header(
            feature_name,
            "この画面は個人データを扱うため、現在の公開モードでは利用できません。",
        ),
        rx.callout(
            f"{feature_name}は非公開モード専用です。公開モードでは個人データを読み込みません。",
            icon="lock",
            color_scheme="amber",
            width="100%",
        ),
        width="100%",
        max_width="1000px",
        margin="0 auto",
    )


def evaluation_badge(label, color_scheme) -> rx.Component:
    """Render a prominent primary evaluation consistently across stock diagnostics."""

    return rx.badge(
        label,
        color_scheme=color_scheme,
        variant="surface",
        size="3",
        font_size="1rem",
        padding_x="0.8rem",
        padding_y="0.45rem",
        white_space="nowrap",
    )


def page_header(title: str, subtitle: str, *actions: rx.Component) -> rx.Component:
    return rx.flex(
        rx.vstack(
            rx.heading(title, size="7", as_="h1", text_wrap="balance"),
            rx.text(
                subtitle,
                size="2",
                color=rx.color("gray", 10),
                text_wrap="pretty",
            ),
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
            rx.heading(title, size="5", as_="h2", text_wrap="balance"),
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
