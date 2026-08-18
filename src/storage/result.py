"""Status-aware results for personal-data storage operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
StorageStatus = Literal["available", "empty", "not_found", "unavailable"]


@dataclass(frozen=True, slots=True)
class StorageResult(Generic[T]):
    """Keep a valid empty result distinct from a backend failure."""

    data: T
    backend: Literal["local", "supabase"]
    status: StorageStatus
    warnings: list[str] = field(default_factory=list)
    error_code: str = ""

    @property
    def is_available(self) -> bool:
        return self.status in {"available", "empty"}


def available(data: T, backend: Literal["local", "supabase"]) -> StorageResult[T]:
    status: StorageStatus = "empty" if not data else "available"
    return StorageResult(data=data, backend=backend, status=status)


def unavailable(
    data: T,
    backend: Literal["local", "supabase"],
    *,
    warning: str,
    error_code: str,
) -> StorageResult[T]:
    return StorageResult(
        data=data,
        backend=backend,
        status="unavailable",
        warnings=[warning],
        error_code=error_code,
    )
