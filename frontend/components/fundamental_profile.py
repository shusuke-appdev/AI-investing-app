"""Adaptive fundamental, purchase-evidence, and volume-profile Stock panel."""

import reflex as rx

from frontend.components.data_provenance import feature_health_panel
from frontend.components.ui_primitives import evaluation_badge
from frontend.state.stock_state import StockState


def _purchase_color() -> rx.Var:
    return rx.cond(
        StockState.purchase_evidence_label == "高",
        "green",
        rx.cond(StockState.purchase_evidence_label == "中", "orange", "red"),
    )


def _fundamental_color() -> rx.Var:
    return rx.cond(
        StockState.fundamental_status == "available",
        "green",
        rx.cond(StockState.fundamental_status == "partial", "orange", "gray"),
    )


def _metric_row(item) -> rx.Component:
    return rx.grid(
        rx.text(item.axis, size="1", color=rx.color("gray", 10)),
        rx.text(item.metric, size="1", weight="medium"),
        rx.text(item.actual, size="1"),
        rx.text(item.benchmark, size="1"),
        rx.text(item.score, size="1", weight="bold"),
        columns="5",
        spacing="2",
        width="100%",
        padding_y="0.25rem",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _volume_bin(item) -> rx.Component:
    return rx.hstack(
        rx.text(item.label, size="1", width="112px", flex_shrink="0"),
        rx.box(
            width=item.width,
            min_width="2px",
            height="12px",
            bg=rx.cond(
                item.is_poc,
                rx.color("blue", 9),
                rx.cond(item.in_value_area, rx.color("cyan", 8), rx.color("gray", 6)),
            ),
            border_radius="2px",
        ),
        rx.text(item.share, size="1", color=rx.color("gray", 9), width="42px"),
        width="100%",
        spacing="2",
        align_items="center",
    )


def _reason_list(title: str, items, color: str = "gray") -> rx.Component:
    return rx.cond(
        items.length() > 0,
        rx.vstack(
            rx.text(title, weight="bold", size="2"),
            rx.foreach(
                items,
                lambda item: rx.text("・" + item, size="1", color=rx.color(color, 10)),
            ),
            align_items="start",
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def fundamental_profile_panel() -> rx.Component:
    """Render the compact decision summary and expandable evidence."""

    return rx.cond(
        StockState.fundamental_size_label != "",
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "適応型ファンダメンタル / 根拠一致度",
                        size="4",
                        as_="h3",
                    ),
                    rx.spacer(),
                    evaluation_badge(
                        StockState.fundamental_score_display,
                        _fundamental_color(),
                    ),
                    evaluation_badge(
                        StockState.purchase_evidence_label
                        + " "
                        + StockState.purchase_evidence_score_display,
                        _purchase_color(),
                    ),
                    width="100%",
                    align_items="center",
                    wrap="wrap",
                ),
                rx.hstack(
                    rx.badge(
                        StockState.fundamental_size_label,
                        color_scheme="blue",
                        variant="surface",
                    ),
                    rx.cond(
                        StockState.fundamental_size_borderline,
                        rx.badge("borderline", color_scheme="orange"),
                        rx.fragment(),
                    ),
                    rx.badge(
                        StockState.fundamental_style_label,
                        color_scheme="purple",
                        variant="surface",
                    ),
                    rx.badge(
                        StockState.fundamental_sector_label,
                        color_scheme="cyan",
                        variant="surface",
                    ),
                    rx.badge(
                        "充足率 " + StockState.fundamental_coverage_display,
                        color_scheme="gray",
                        variant="surface",
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.text(
                    StockState.purchase_evidence_summary,
                    size="2",
                    color=rx.color("gray", 11),
                ),
                rx.cond(
                    StockState.volume_profile_summary != "",
                    rx.text(
                        "重要価格帯: " + StockState.volume_profile_summary,
                        size="2",
                        weight="medium",
                        color=rx.color("blue", 10),
                    ),
                    rx.fragment(),
                ),
                rx.accordion.root(
                    rx.accordion.item(
                        header="評価内訳・除外理由・価格帯別出来高を見る",
                        content=rx.vstack(
                            rx.box(
                                rx.text("算出不可・上限理由", weight="bold", size="3"),
                                _reason_list(
                                    "算出不可・欠損",
                                    StockState.fundamental_missing_reasons,
                                    "red",
                                ),
                                _reason_list(
                                    "上限理由",
                                    StockState.fundamental_cap_reasons,
                                    "orange",
                                ),
                                _reason_list(
                                    "業種上の除外指標",
                                    StockState.fundamental_excluded_metrics,
                                ),
                                _reason_list(
                                    "購入判断の上限理由",
                                    StockState.purchase_evidence_cap_reasons,
                                    "orange",
                                ),
                                width="100%",
                                padding="0.75rem",
                                border=f"1px solid {rx.color('gray', 4)}",
                                border_radius="8px",
                            ),
                            feature_health_panel(
                                StockState.purchase_evidence_health,
                                title="根拠一致度の入力ヘルス",
                            ),
                            rx.cond(
                                StockState.fundamental_metrics.length() > 0,
                                rx.box(
                                    rx.vstack(
                                        rx.text("KPI表", weight="bold", size="3"),
                                        rx.grid(
                                            rx.text("評価軸", size="1", weight="bold"),
                                            rx.text("指標", size="1", weight="bold"),
                                            rx.text("実績", size="1", weight="bold"),
                                            rx.text("基準", size="1", weight="bold"),
                                            rx.text("点", size="1", weight="bold"),
                                            columns="5",
                                            spacing="2",
                                            width="100%",
                                        ),
                                        rx.foreach(
                                            StockState.fundamental_metrics, _metric_row
                                        ),
                                        width="100%",
                                        spacing="1",
                                    ),
                                    width="100%",
                                    padding="0.75rem",
                                    border=f"1px solid {rx.color('gray', 4)}",
                                    border_radius="8px",
                                ),
                                rx.fragment(),
                            ),
                            rx.cond(
                                StockState.volume_profile_bins.length() > 0,
                                rx.box(
                                    rx.vstack(
                                        rx.text(
                                            "価格帯別出来高",
                                            size="3",
                                            weight="bold",
                                        ),
                                        rx.text(
                                            "126営業日・24帯・日足均等配分proxy",
                                            size="1",
                                            color=rx.color("gray", 10),
                                        ),
                                        rx.foreach(
                                            StockState.volume_profile_bins, _volume_bin
                                        ),
                                        width="100%",
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    width="100%",
                                    padding="0.75rem",
                                    border=f"1px solid {rx.color('gray', 4)}",
                                    border_radius="8px",
                                ),
                                rx.fragment(),
                            ),
                            width="100%",
                            align_items="start",
                            spacing="3",
                        ),
                    ),
                    width="100%",
                    collapsible=True,
                ),
                width="100%",
                align_items="start",
                spacing="3",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.fragment(),
    )
