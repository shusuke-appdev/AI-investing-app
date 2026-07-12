from typing import Any

import reflex as rx

from frontend.components.trade_setup import trade_setup_panel
from frontend.components.ui_primitives import evaluation_badge
from frontend.state.stock_state import StockState


def _purchase_color(label) -> rx.Var:
    return rx.cond(
        label == "高",
        "green",
        rx.cond(label == "中", "orange", rx.cond(label == "低", "red", "gray")),
    )


def _level_row(item: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(item["label"], size="1", color=rx.color("gray", 10)),
            rx.text(item["value"], size="4", weight="bold"),
            rx.text(item["note"], size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
        ),
        width="100%",
    )


def _check_row(item: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                evaluation_badge(
                    rx.cond(
                        item["status"] == "pass",
                        "達成",
                        rx.cond(item["status"] == "fail", "未達", "確認"),
                    ),
                    rx.cond(
                        item["status"] == "pass",
                        "green",
                        rx.cond(item["status"] == "fail", "red", "gray"),
                    ),
                ),
                rx.text(item["label"], weight="bold", size="2"),
                width="100%",
                align_items="center",
            ),
            rx.text(item["value"], size="2"),
            rx.text(item["rationale"], size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )


def _supply_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.text(item["label"], size="2", weight="bold", min_width="8rem"),
        rx.vstack(
            rx.text(item["value"], size="2", weight="medium"),
            rx.text(item["note"], size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
        ),
        align_items="start",
        width="100%",
        padding_y="0.5rem",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _invalidation_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.badge(item["label"], color_scheme="red", variant="surface"),
        rx.text(item["value"], size="2"),
        align_items="center",
        width="100%",
        spacing="2",
    )


def _health_row(item: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item["label"], size="2", weight="bold", flex="1"),
            rx.badge(
                item["status_label"],
                color_scheme=rx.cond(
                    item["status_key"] == "ok",
                    "green",
                    rx.cond(
                        (item["status_key"] == "partial")
                        | (item["status_key"] == "capped"),
                        "amber",
                        "red",
                    ),
                ),
                variant="surface",
            ),
            rx.cond(
                item["required"],
                rx.badge("必須", color_scheme="gray", variant="outline"),
                rx.fragment(),
            ),
            width="100%",
            align_items="center",
        ),
        rx.text(item["value"], size="2", weight="medium"),
        rx.text(item["detail"], size="1", color=rx.color("gray", 10)),
        rx.text(item["effect"], size="1", color=rx.color("blue", 10)),
        width="100%",
        padding_y="0.5rem",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _analysis_body() -> rx.Component:
    analysis = StockState.trade_analysis.to(dict[str, Any])
    risk = analysis["risk"].to(dict[str, Any])
    timing = analysis["timing"].to(dict[str, Any])
    purchase_evidence = analysis["purchase_evidence"].to(dict[str, Any])
    purchase_health = analysis["purchase_evidence_health"].to(list[dict])
    key_levels = analysis["key_levels"].to(list[dict])
    timing_checks = analysis["timing_checks"].to(list[dict])
    supply_demand = analysis["supply_demand"].to(list[dict])
    invalidations = analysis["invalidations"].to(list[dict])
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("トレード分析", size="5", as_="h2"),
                    rx.text(
                        analysis["summary"].to(str),
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                evaluation_badge(
                    analysis["stance_label"].to(str),
                    analysis["stance_color"].to(str),
                ),
                rx.icon_button(
                    rx.icon("x", size=16),
                    on_click=StockState.hide_trade_analysis,
                    variant="ghost",
                    aria_label="トレード分析を閉じる",
                ),
                width="100%",
                align_items="start",
                wrap="wrap",
            ),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.text("主シナリオ", size="1", color=rx.color("gray", 10)),
                        rx.text(timing["primary"], size="2", weight="medium"),
                        align_items="start",
                        spacing="1",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.text("押し目条件", size="1", color=rx.color("gray", 10)),
                        rx.text(timing["pullback"], size="2"),
                        align_items="start",
                        spacing="1",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.text("ブレイク条件", size="1", color=rx.color("gray", 10)),
                        rx.text(timing["breakout"], size="2"),
                        align_items="start",
                        spacing="1",
                    ),
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
            rx.box(
                rx.hstack(
                    rx.heading("根拠一致度", size="4", as_="h3"),
                    rx.spacer(),
                    evaluation_badge(
                        purchase_evidence["label"].to(str)
                        + " "
                        + purchase_evidence["score_display"].to(str),
                        _purchase_color(purchase_evidence["label"]),
                    ),
                    width="100%",
                    align_items="center",
                    wrap="wrap",
                ),
                rx.text(
                    purchase_evidence["summary"].to(str),
                    size="2",
                    color=rx.color("gray", 11),
                    margin_top="0.35rem",
                ),
                rx.cond(
                    purchase_health.length() > 0,
                    rx.vstack(
                        rx.foreach(purchase_health, _health_row),
                        width="100%",
                        spacing="0",
                        margin_top="0.75rem",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                padding="0.75rem",
                border=f"1px solid {rx.color('gray', 4)}",
                border_radius="8px",
                bg=rx.color("gray", 1),
            ),
            rx.box(
                rx.heading("重要水準", size="4", as_="h3", margin_bottom="0.75rem"),
                rx.grid(
                    rx.foreach(key_levels, _level_row),
                    columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.box(
                rx.heading(
                    "需給・タイミング根拠",
                    size="4",
                    as_="h3",
                    margin_bottom="0.75rem",
                ),
                rx.grid(
                    rx.foreach(
                        timing_checks,
                        _check_row,
                    ),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.grid(
                rx.box(
                    rx.heading("需給確認", size="4", as_="h3", margin_bottom="0.75rem"),
                    rx.vstack(
                        rx.foreach(
                            supply_demand,
                            _supply_row,
                        ),
                        width="100%",
                        align_items="start",
                        spacing="0",
                    ),
                    width="100%",
                ),
                rx.box(
                    rx.heading(
                        "無効化条件・リスク",
                        size="4",
                        as_="h3",
                        margin_bottom="0.75rem",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.badge("Final stop", color_scheme="red"),
                            rx.text(risk["final_stop"], weight="bold"),
                            rx.badge("ATR%", color_scheme="gray"),
                            rx.text(risk["atr_percent"], size="2"),
                            spacing="2",
                            wrap="wrap",
                        ),
                        rx.text(
                            risk["position_note"],
                            size="2",
                            color=rx.color("gray", 10),
                        ),
                        rx.foreach(
                            invalidations,
                            _invalidation_row,
                        ),
                        width="100%",
                        align_items="start",
                        spacing="2",
                    ),
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", lg="2"),
                spacing="4",
                width="100%",
            ),
            rx.divider(),
            trade_setup_panel(),
            width="100%",
            align_items="start",
            spacing="4",
        ),
        width="100%",
        border=f"1px solid {rx.color('blue', 5)}",
        border_radius="8px",
        padding="1rem",
        bg=rx.color("blue", 2),
        margin_bottom="2rem",
    )


def stock_trade_analysis_panel() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading("トレード分析", size="5", as_="h2"),
                rx.text(
                    "この銘柄の既存分析データだけを使って、仕掛け水準と待機条件を整理します。",
                    size="2",
                    color=rx.color("gray", 10),
                ),
                align_items="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("line-chart", size=16),
                "トレード分析",
                on_click=StockState.show_trade_analysis,
                variant=rx.cond(
                    StockState.trade_analysis_visible,
                    "solid",
                    "outline",
                ),
                color_scheme="blue",
            ),
            width="100%",
            align_items="center",
            wrap="wrap",
            margin_top="1rem",
            margin_bottom="1rem",
        ),
        rx.cond(
            StockState.trade_analysis_error != "",
            rx.callout(
                StockState.trade_analysis_error,
                icon="triangle_alert",
                color_scheme="amber",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        rx.cond(StockState.trade_analysis_visible, _analysis_body(), rx.fragment()),
        width="100%",
    )
