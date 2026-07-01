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


class DataStatusDisplay(BaseModel):
    name: str = ""
    source: str = ""
    fetched_at: str = ""
    status_label: str = "OK"
    status_key: str = "ok"
    cache_status: str = ""
    cache_age_label: str = ""
    error: str = ""


class FeatureHealthDisplay(BaseModel):
    feature: str = ""
    label: str = ""
    source: str = ""
    value: str = ""
    detail: str = ""
    status_key: str = "ok"
    status_label: str = "OK"
    effect: str = ""
    required: bool = False


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


def data_status_display_items(items: Iterable[Any]) -> list[DataStatusDisplay]:
    result = []
    for item in items:
        if hasattr(item, "to_dict"):
            value = item.to_dict()
        elif isinstance(item, dict):
            value = item
        else:
            continue
        is_stale = bool(value.get("is_stale", False))
        is_partial = bool(value.get("is_partial", False))
        error = str(value.get("error") or "")
        cache_status = str(value.get("cache_status") or "")
        age = value.get("cache_age_seconds")
        status_key = (
            "failed"
            if error and cache_status == "failed"
            else "stale"
            if is_stale or cache_status == "stale_cache"
            else "partial"
            if is_partial or error
            else "ok"
        )
        result.append(
            DataStatusDisplay(
                name=str(value.get("name") or ""),
                source=str(value.get("source") or ""),
                fetched_at=str(value.get("fetched_at") or ""),
                status_key=status_key,
                status_label=_status_label(status_key),
                cache_status=cache_status,
                cache_age_label=_cache_age_label(age),
                error=error,
            )
        )
    return result


def feature_health_display_items(items: Iterable[Any]) -> list[FeatureHealthDisplay]:
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            FeatureHealthDisplay(
                feature=str(item.get("feature") or ""),
                label=str(item.get("label") or ""),
                source=str(item.get("source") or ""),
                value=str(_display_value(item.get("value"))),
                detail=str(item.get("detail") or ""),
                status_key=str(item.get("status_key") or "ok"),
                status_label=str(
                    item.get("status_label")
                    or _status_label(str(item.get("status_key") or "ok"))
                ),
                effect=str(item.get("effect") or ""),
                required=bool(item.get("required", False)),
            )
        )
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


def feature_health_panel(
    items,
    *,
    title: str = "機能別ヘルス",
    empty_text: str = "ヘルス情報はまだありません。",
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon("activity", size=18, color=rx.color("blue", 9)),
                rx.text(title, weight="bold", size="3"),
                width="100%",
                align_items="center",
            ),
            rx.cond(
                items.length() > 0,
                rx.grid(
                    rx.foreach(items, _feature_health_item),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="2",
                    width="100%",
                ),
                rx.text(empty_text, size="2", color="gray"),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def data_status_panel(items, *, title: str = "取得ステータス") -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("database", size=18, color=rx.color("blue", 9)),
                rx.text(title, weight="bold", size="3"),
                width="100%",
                align_items="center",
            ),
            rx.cond(
                items.length() > 0,
                rx.vstack(rx.foreach(items, _data_status_item), width="100%"),
                rx.text("取得ステータスはまだありません。", size="2", color="gray"),
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
        variant="surface",
    )


def _feature_health_item(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.label, weight="bold", size="2", flex="1"),
            rx.badge(
                item.status_label,
                color_scheme=_status_color(item.status_key),
                variant="surface",
            ),
            rx.cond(
                item.required,
                rx.badge("必須", color_scheme="gray", variant="outline"),
                rx.fragment(),
            ),
            width="100%",
            align_items="center",
        ),
        rx.cond(
            item.value != "",
            rx.text(item.value, size="2", weight="medium"),
            rx.fragment(),
        ),
        rx.cond(
            item.detail != "",
            rx.text(item.detail, size="1", color=rx.color("gray", 10)),
            rx.fragment(),
        ),
        rx.cond(
            item.effect != "",
            rx.text(item.effect, size="1", color=rx.color("blue", 10)),
            rx.fragment(),
        ),
        rx.cond(
            item.source != "",
            rx.text("source: " + item.source, size="1", color=rx.color("gray", 9)),
            rx.fragment(),
        ),
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
        width="100%",
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


def _data_status_item(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.name, weight="bold", size="2", flex="1"),
            rx.badge(
                item.status_label,
                color_scheme=_status_color(item.status_key),
                variant="surface",
            ),
            rx.cond(
                item.cache_status != "",
                rx.badge(item.cache_status, color_scheme="gray", variant="outline"),
                rx.fragment(),
            ),
            width="100%",
            align_items="center",
        ),
        rx.cond(
            item.source != "",
            rx.text("source: " + item.source, size="1", color=rx.color("gray", 10)),
            rx.fragment(),
        ),
        rx.cond(
            item.fetched_at != "",
            rx.text("fetched: " + item.fetched_at, size="1", color=rx.color("gray", 9)),
            rx.fragment(),
        ),
        rx.cond(
            item.cache_age_label != "",
            rx.text(
                "cache age: " + item.cache_age_label,
                size="1",
                color=rx.color("gray", 9),
            ),
            rx.fragment(),
        ),
        rx.cond(
            item.error != "",
            rx.text(item.error, size="1", color=rx.color("amber", 11)),
            rx.fragment(),
        ),
        padding_y="0.55rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
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


def _status_label(status_key: str) -> str:
    return {
        "ok": "OK",
        "partial": "一部取得",
        "capped": "上限あり",
        "stale": "古いデータ",
        "unavailable": "算出不可",
        "failed": "失敗",
    }.get(status_key, status_key)


def _cache_age_label(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return ""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


def _display_value(value: Any) -> str:
    return "" if value is None else str(value)


def _status_color(status_key) -> rx.Var:
    return rx.cond(
        status_key == "ok",
        "green",
        rx.cond(
            (status_key == "partial") | (status_key == "capped"),
            "amber",
            rx.cond(
                status_key == "stale",
                "orange",
                rx.cond(status_key == "unavailable", "red", "red"),
            ),
        ),
    )
