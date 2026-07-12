"""Shared provider result contract.

Provider implementations may add domain-specific fields, but retrieval state is
represented consistently so callers do not need provider-specific status logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


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
