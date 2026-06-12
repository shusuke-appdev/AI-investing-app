"""Shared data-provenance presentation components."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import reflex as rx
from pydantic import BaseModel


class ProvenanceDisplay(BaseModel):
    item_id: str = ""
    label: str = ""
    kind: str = "unavailable"
    source: str = ""
    as_of: str = ""
    method: str = ""
    limitation: str = ""
    risk_level: str = "low"


def provenance_display_items(items: Iterable[Any]) -> list[ProvenanceDisplay]:
    result = []
    for item in items:
        if hasattr(item, "to_dict"):
            value = item.to_dict()
        elif isinstance(item, dict):
            value = item
        else:
            continue
        result.append(ProvenanceDisplay(**value))
    return result


def provenance_panel(items, *, title: str = "データの来歴・信頼性") -> rx.Component:
    """Show where displayed analysis values came from and their limitations."""

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("shield-check", size=18, color=rx.color("blue", 9)),
                rx.vstack(
                    rx.text(title, weight="bold", size="3"),
                    rx.text(
                        "直接値・算出値・proxy・推定値・キャッシュを区別して表示します。",
                        size="1",
                        color=rx.color("gray", 10),
                    ),
                    spacing="0",
                    align_items="start",
                ),
                width="100%",
                align_items="center",
            ),
            rx.cond(
                items.length() > 0,
                rx.grid(
                    rx.foreach(items, _provenance_item),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="2",
                    width="100%",
                ),
                rx.text("来歴情報はまだありません。", size="2", color="gray"),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
        variant="surface",
    )


def provenance_badge(item) -> rx.Component:
    return rx.tooltip(
        rx.badge(
            _kind_label(item.kind),
            color_scheme=_kind_color(item.kind),
            variant="surface",
        ),
        content=rx.cond(
            item.limitation != "",
            item.limitation,
            "制約情報はありません。",
        ),
    )


def _provenance_item(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.label, weight="bold", size="2", flex="1"),
            provenance_badge(item),
            rx.badge(
                _risk_label(item.risk_level),
                color_scheme=_risk_color(item.risk_level),
                variant="outline",
            ),
            width="100%",
            align_items="center",
        ),
        rx.cond(
            item.source != "",
            rx.text("取得元: " + item.source, size="1", color=rx.color("gray", 10)),
            rx.fragment(),
        ),
        rx.cond(
            item.method != "",
            rx.text(item.method, size="1", color=rx.color("gray", 11)),
            rx.fragment(),
        ),
        rx.cond(
            item.limitation != "",
            rx.text(
                "制約: " + item.limitation,
                size="1",
                color=rx.color("amber", 11),
            ),
            rx.fragment(),
        ),
        rx.cond(
            item.as_of != "",
            rx.text("基準: " + item.as_of, size="1", color=rx.color("gray", 9)),
            rx.fragment(),
        ),
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
        width="100%",
    )


def _kind_label(kind) -> rx.Var:
    return rx.cond(
        kind == "direct",
        "直接値",
        rx.cond(
            kind == "computed",
            "算出値",
            rx.cond(
                kind == "proxy",
                "proxy",
                rx.cond(
                    kind == "estimated",
                    "推定値",
                    rx.cond(
                        kind == "model_output",
                        "モデル出力",
                        rx.cond(
                            kind == "fixed_fallback",
                            "固定補完",
                            rx.cond(
                                kind == "stale_cache",
                                "古いキャッシュ",
                                "利用不可",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _kind_color(kind) -> rx.Var:
    return rx.cond(
        kind == "direct",
        "green",
        rx.cond(
            kind == "computed",
            "blue",
            rx.cond(
                (kind == "proxy") | (kind == "estimated") | (kind == "model_output"),
                "amber",
                rx.cond(kind == "stale_cache", "orange", "red"),
            ),
        ),
    )


def _risk_label(risk) -> rx.Var:
    return rx.cond(risk == "high", "要注意", rx.cond(risk == "medium", "注意", "低"))


def _risk_color(risk) -> rx.Var:
    return rx.cond(risk == "high", "red", rx.cond(risk == "medium", "amber", "gray"))
