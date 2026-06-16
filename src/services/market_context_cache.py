"""Persistent cache I/O helpers for MarketContext snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.persistent_cache import (
    PersistentCacheRead,
    PersistentJsonCache,
    repo_state_cache,
)
from src.services.analysis_context import MarketContext


def market_context_cache(namespace: str) -> PersistentJsonCache:
    return repo_state_cache(namespace)


def context_cache_key(market_type: str, kind: str) -> str:
    return f"{market_type.lower()}_{kind}"


def context_cache_path(cache: PersistentJsonCache, market_type: str, kind: str) -> Path:
    return cache.path_for_key(context_cache_key(market_type, kind))


def save_context_cache(
    cache: PersistentJsonCache,
    context: MarketContext,
    kind: str,
    *,
    fetched_at: str,
) -> None:
    path = context_cache_path(cache, context.market_type, kind)
    cache.write_path(
        path,
        context_cache_key(context.market_type, kind),
        context.to_dict(),
        fetched_at=fetched_at,
    )


def read_context_cache(
    cache: PersistentJsonCache,
    market_type: str,
    kind: str,
    *,
    fresh_seconds: int,
    stale_seconds: int,
) -> PersistentCacheRead:
    key = context_cache_key(market_type, kind)
    return cache.read_path(
        context_cache_path(cache, market_type, kind),
        key,
        fresh_seconds=fresh_seconds,
        stale_seconds=stale_seconds,
    )


def context_from_cache_payload(payload: dict[str, Any]) -> MarketContext:
    return MarketContext.from_mapping(payload)
