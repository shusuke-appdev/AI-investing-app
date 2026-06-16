"""Persistent provider/data retrieval health snapshots for the data-quality page."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.persistent_cache import repo_state_cache, utc_now_iso
from src.services.analysis_context import DataResult, OptionContext

PROVIDER_HEALTH_CACHE_NAMESPACE = "provider_health_snapshot"
PROVIDER_HEALTH_KEY = "latest"
PROVIDER_HEALTH_MAX_AGE_SECONDS = 90 * 86400


@dataclass
class ProviderHealthSnapshot:
    """Last known health for one user-visible data retrieval surface."""

    name: str
    status_key: str = "unavailable"
    source: str = ""
    scope: str = ""
    last_success_at: str = ""
    last_error_at: str = ""
    last_error: str = ""
    cache_status: str = ""
    cache_age_seconds: float | None = None
    is_stale: bool = False
    is_partial: bool = False
    degraded_reason: str = ""
    updated_at: str = ""

    @property
    def status_label(self) -> str:
        return {
            "ok": "OK",
            "partial": "一部取得",
            "stale": "古いキャッシュ",
            "failed": "取得失敗",
            "unavailable": "未取得",
        }.get(self.status_key, self.status_key)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status_label"] = self.status_label
        return value

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ProviderHealthSnapshot:
        return cls(
            name=str(value.get("name") or ""),
            status_key=str(value.get("status_key") or "unavailable"),
            source=str(value.get("source") or ""),
            scope=str(value.get("scope") or ""),
            last_success_at=str(value.get("last_success_at") or ""),
            last_error_at=str(value.get("last_error_at") or ""),
            last_error=str(value.get("last_error") or ""),
            cache_status=str(value.get("cache_status") or ""),
            cache_age_seconds=_optional_float(value.get("cache_age_seconds")),
            is_stale=bool(value.get("is_stale", False)),
            is_partial=bool(value.get("is_partial", False)),
            degraded_reason=str(value.get("degraded_reason") or ""),
            updated_at=str(value.get("updated_at") or ""),
        )


def record_data_results(
    results: list[DataResult] | list[dict[str, Any]], *, scope: str = ""
) -> None:
    """Merge DataResult rows into the persistent provider health snapshot."""

    if not results:
        return
    try:
        existing = {item.name: item for item in load_provider_health()}
        for raw in results:
            result = _coerce_data_result(raw)
            if result is None:
                continue
            snapshot = _snapshot_from_data_result(
                result,
                scope=scope,
                previous=existing.get(_health_name(result.name, scope)),
            )
            existing[snapshot.name] = snapshot
        _write_provider_health(list(existing.values()))
    except OSError:
        return


def record_option_context(
    context: OptionContext | dict[str, Any], *, scope: str
) -> None:
    """Record an option context as a provider health row."""

    if isinstance(context, dict):
        context = OptionContext(
            status=str(context.get("status") or "unavailable"),
            source=str(context.get("source") or ""),
            fetched_at=str(context.get("fetched_at") or ""),
            error_message=str(context.get("error_message") or ""),
            is_stale=bool(context.get("is_stale", False)),
            is_partial=bool(context.get("is_partial", False)),
            cache_status=str(context.get("cache_status") or ""),
            cache_age_seconds=_optional_float(context.get("cache_age_seconds")),
            quality_warnings=list(context.get("quality_warnings") or []),
        )
    error = context.error_message or "; ".join(context.quality_warnings[:3])
    result = DataResult(
        name="options",
        source=context.source,
        fetched_at=context.fetched_at,
        is_stale=context.is_stale,
        is_partial=context.is_partial or context.status in {"partial", "failed"},
        error=error if context.status != "available" else "",
        cache_status=context.cache_status or context.status,
        cache_age_seconds=context.cache_age_seconds,
    )
    record_data_results([result], scope=scope)


def load_provider_health() -> list[ProviderHealthSnapshot]:
    """Load the latest provider health rows from repo-local cache."""

    read = _provider_health_cache().read(
        PROVIDER_HEALTH_KEY,
        fresh_seconds=PROVIDER_HEALTH_MAX_AGE_SECONDS,
        stale_seconds=PROVIDER_HEALTH_MAX_AGE_SECONDS,
    )
    if not read.is_available:
        return []
    rows = read.payload.get("items", [])
    if not isinstance(rows, list):
        return []
    return [
        ProviderHealthSnapshot.from_mapping(item)
        for item in rows
        if isinstance(item, dict) and item.get("name")
    ]


def _snapshot_from_data_result(
    result: DataResult,
    *,
    scope: str,
    previous: ProviderHealthSnapshot | None = None,
) -> ProviderHealthSnapshot:
    now = utc_now_iso()
    status_key = _status_key(result)
    is_failure = status_key == "failed"
    fetched_at = result.fetched_at or now
    return ProviderHealthSnapshot(
        name=_health_name(result.name, scope),
        status_key=status_key,
        source=result.source,
        scope=scope,
        last_success_at=(
            previous.last_success_at if is_failure and previous else fetched_at
        ),
        last_error_at=fetched_at
        if is_failure
        else (previous.last_error_at if previous else ""),
        last_error=result.error
        if is_failure
        else (previous.last_error if previous else ""),
        cache_status=result.cache_status,
        cache_age_seconds=result.cache_age_seconds,
        is_stale=result.is_stale,
        is_partial=result.is_partial,
        degraded_reason=_degraded_reason(result, status_key),
        updated_at=now,
    )


def _write_provider_health(items: list[ProviderHealthSnapshot]) -> None:
    ordered = sorted(items, key=lambda item: (item.scope, item.name))
    _provider_health_cache().write(
        PROVIDER_HEALTH_KEY,
        {"items": [item.to_dict() for item in ordered]},
    )


def _status_key(result: DataResult) -> str:
    if result.error and result.cache_status == "failed":
        return "failed"
    if result.is_stale or result.cache_status == "stale_cache":
        return "stale"
    if result.is_partial or result.error:
        return "partial"
    return "ok"


def _degraded_reason(result: DataResult, status_key: str) -> str:
    if result.error:
        return result.error
    if status_key == "stale":
        return "stale cacheを使用中"
    if status_key == "partial":
        return "一部データが未取得または推定です"
    return ""


def _coerce_data_result(value: DataResult | dict[str, Any]) -> DataResult | None:
    if isinstance(value, DataResult):
        return value
    if not isinstance(value, dict):
        return None
    return DataResult(
        name=str(value.get("name") or ""),
        source=str(value.get("source") or ""),
        fetched_at=str(value.get("fetched_at") or ""),
        is_stale=bool(value.get("is_stale", False)),
        is_partial=bool(value.get("is_partial", False)),
        error=str(value.get("error") or ""),
        cache_status=str(value.get("cache_status") or "live"),
        cache_age_seconds=_optional_float(value.get("cache_age_seconds")),
    )


def _health_name(name: str, scope: str) -> str:
    normalized = str(name or "").strip() or "unknown"
    return f"{scope}.{normalized}" if scope else normalized


def _provider_health_cache():
    return repo_state_cache(PROVIDER_HEALTH_CACHE_NAMESPACE)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
