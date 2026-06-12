import reflex as rx

from frontend.state.stock_state import StockState


def _setup_check(item: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    item["status"],
                    color_scheme=rx.cond(
                        item["status"] == "pass",
                        "green",
                        rx.cond(item["status"] == "fail", "red", "gray"),
                    ),
                ),
                rx.text(item["label"], weight="bold", size="2"),
                rx.spacer(),
                rx.text(
                    item["points"].to(str) + "/" + item["max_points"].to(str),
                    size="1",
                    color=rx.color("gray", 10),
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(item["value_display"], size="2"),
            rx.text(item["rationale"], size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )


def trade_setup_panel() -> rx.Component:
    setup = StockState.trade_setup
    return rx.cond(
        setup.contains("status"),
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.heading("Entry Framework", size="5"),
                    rx.text(
                        "既存分析を置き換えず、日足のEntry品質と禁止条件を判定します。",
                        size="2",
                        color=rx.color("gray", 10),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.badge(
                    setup["status"].to(str),
                    color_scheme=rx.cond(
                        setup["status"].to(str) == "ready",
                        "green",
                        rx.cond(
                            setup["status"].to(str) == "blocked",
                            "red",
                            "orange",
                        ),
                    ),
                    size="3",
                ),
                rx.badge("Grade " + setup["grade"].to(str), size="3"),
                rx.badge(setup["score_display"].to(str), size="3"),
                width="100%",
                align_items="center",
                wrap="wrap",
                margin_bottom="1rem",
            ),
            rx.card(
                rx.vstack(
                    rx.text(setup["summary"].to(str), weight="bold"),
                    rx.grid(
                        _metric("RVOL", setup["rvol_display"].to(str)),
                        _metric("ADR%", setup["adr_display"].to(str)),
                        _metric("VARS proxy", setup["vars_display"].to(str)),
                        _metric(
                            "50MA Extension",
                            setup["ma50_extension_display"].to(str),
                        ),
                        columns=rx.breakpoints(initial="2", md="4"),
                        spacing="3",
                        width="100%",
                    ),
                    align_items="start",
                    width="100%",
                ),
                width="100%",
                margin_bottom="1rem",
            ),
            rx.cond(
                setup["blocked_display"].to(str) != "",
                rx.callout(
                    rx.markdown(setup["blocked_display"].to(str)),
                    icon="circle-x",
                    color_scheme="red",
                    width="100%",
                    margin_bottom="1rem",
                ),
            ),
            rx.grid(
                rx.foreach(setup["checks"].to(list[dict]), _setup_check),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="3",
                width="100%",
            ),
            rx.callout(
                rx.markdown(setup["warnings_display"].to(str)),
                icon="info",
                color_scheme="amber",
                width="100%",
                margin_top="1rem",
            ),
            rx.link(
                rx.button(
                    rx.icon("clipboard-list", size=16),
                    "Trading Planを作成",
                    variant="outline",
                    margin_top="1rem",
                ),
                href="/trading-plan",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.box(),
    )


def _metric(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color=rx.color("gray", 10)),
        rx.text(value, size="3", weight="bold"),
        align_items="start",
        spacing="1",
    )
