"""Shared provider result contract.

Provider implementations may add domain-specific fields, but retrieval state is
represented consistently so callers do not need provider-specific status logic.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Generic, TypeVar

T = TypeVar("T")


def memory_metadata(metadata: dict, age: float) -> dict:
    """Describe a memory hit without promoting stale/failed acquisition state."""
    result = dict(metadata)
    original = result.get("cache_status", "unknown")
    result["origin_cache_status"] = result.get("origin_cache_status", original)
    result["cache_layer"] = "memory"
    if original in {"live", "persistent_cache", "memory_cache"}:
        result["cache_status"] = "memory_cache"
    result["cache_age_seconds"] = (result.get("cache_age_seconds") or 0) + age
    return result


def memory_history(data, age: float):
    result = data.copy()
    result.attrs = deepcopy(data.attrs)
    result.attrs["fetch_metadata"] = memory_metadata(
        data.attrs.get("fetch_metadata", {}), age
    )
    return result


def memory_payload(data: dict, age: float) -> dict:
    result = dict(data)
    result["provider_status"] = memory_metadata(data.get("provider_status", {}), age)
    return result


def memory_result(result, age: float):
    metadata = memory_metadata(
        {
            "cache_status": result.cache_status,
            "cache_age_seconds": result.cache_age_seconds,
        },
        age,
    )
    data = (
        memory_history(result.data, age)
        if hasattr(result.data, "attrs")
        else result.data
    )
    return replace(
        result,
        data=data,
        cache_status=metadata["cache_status"],
        cache_age_seconds=metadata["cache_age_seconds"],
    )


@dataclass(kw_only=True)
class FetchResult(Generic[T]):
    """Payload plus normalized provenance, freshness, warning, and error state."""

    data: T
    source: str = ""
    fetched_at: str = ""
    is_stale: bool = False
    is_partial: bool = False
    cache_status: str = "live"
    cache_age_seconds: float | None = None
    status: str = "available"
    warnings: list[str] = field(default_factory=list)
    error_code: str = ""
    error: str = ""

    @property
    def is_available(self) -> bool:
        """Return whether the provider supplied a non-empty payload."""

        value = self.data
        if value is None:
            return False
        empty = getattr(value, "empty", None)
        if isinstance(empty, bool):
            return not empty
        try:
            return len(value) > 0  # type: ignore[arg-type]
        except TypeError:
            return True
