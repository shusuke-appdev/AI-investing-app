"""Assertion diagnostics for analysis-context tests."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from src.services.analysis_context import DataResult


def assert_data_result_ok(
    result: DataResult | dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> None:
    """Assert one data result is usable and emit provider-rich diagnostics."""

    data = _as_dict(result)
    if not data.get("is_partial") and not data.get("error"):
        return
    raise AssertionError(_diagnostic_message("DataResult is not ok", data, context))


def assert_context_quality(
    context_value: Any,
    *,
    allow_partial: bool = False,
    context: dict[str, Any] | None = None,
) -> None:
    """Assert an analysis context has no unexplained errors or partial status."""

    data = _as_dict(context_value)
    if allow_partial:
        return
    errors = [str(item) for item in data.get("errors", []) if item]
    warnings = [str(item) for item in data.get("quality_warnings", []) if item]
    if not data.get("is_partial") and not errors and not warnings:
        return
    diagnostic = {
        "name": data.get("market_type") or data.get("ticker") or "analysis_context",
        "source": data.get("source") or ((context or {}).get("provider") or ""),
        "fetched_at": data.get("fetched_at", ""),
        "cache_status": data.get("cache_status", ""),
        "quality_warnings": warnings,
        "error": "; ".join(errors),
        "is_partial": data.get("is_partial", False),
    }
    raise AssertionError(
        _diagnostic_message("Context quality failed", diagnostic, context)
    )


def assert_no_unexplained_partial_data(
    results: list[DataResult | dict[str, Any]],
    *,
    quality_warnings: list[str] | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Require every partial data result to carry a visible explanation."""

    warnings = [str(item) for item in quality_warnings or [] if item]
    unexplained = []
    for result in results:
        data = _as_dict(result)
        if not data.get("is_partial"):
            continue
        if data.get("error") or warnings:
            continue
        unexplained.append(data)

    if not unexplained:
        return

    details = "\n".join(
        _diagnostic_message("Unexplained partial data", item, context)
        for item in unexplained
    )
    raise AssertionError(details)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, DataResult):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Unsupported diagnostic value: {type(value)!r}")


def _diagnostic_message(
    title: str,
    data: dict[str, Any],
    context: dict[str, Any] | None,
) -> str:
    provider = data.get("source") or (context or {}).get("provider") or "unknown"
    warnings = data.get("quality_warnings") or (context or {}).get("quality_warnings")
    return (
        f"{title}: "
        f"name={data.get('name', 'unknown')}; "
        f"ticker={(context or {}).get('ticker', 'unknown')}; "
        f"provider={provider}; "
        f"fetched_at={data.get('fetched_at', '')}; "
        f"cache_status={data.get('cache_status', '')}; "
        f"is_partial={data.get('is_partial', False)}; "
        f"error={data.get('error', '')}; "
        f"quality_warnings={warnings or []}"
    )
