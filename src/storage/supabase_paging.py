"""Bounded, deterministic Supabase Data API pagination helpers."""

from __future__ import annotations

from typing import Any

DEFAULT_PAGE_SIZE = 1000


def fetch_all_rows(
    client: Any,
    table: str,
    columns: str = "*",
    *,
    order_column: str,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Read every row using stable ordering and inclusive range pages."""

    if page_size <= 0:
        raise ValueError("page_size must be positive")
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(columns).order(order_column)
        response = query.range(start, start + page_size - 1).execute()
        page = [item for item in (response.data or []) if isinstance(item, dict)]
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size
