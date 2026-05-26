"""
汎用TTLキャッシュモジュール。

Streamlit の @st.cache_data を代替する、フレームワーク非依存の
メモリキャッシュ機構。関数単位の公開APIは維持しつつ、エントリ単位で
created_at / expires_at / ttl を保持する。
"""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.log_config import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """メモリTTLキャッシュの1エントリ。"""

    value: Any
    created_at: float
    expires_at: float
    ttl: int
    namespace: str

    @property
    def is_expired(self) -> bool:
        """現在時刻基準で期限切れならTrue。"""

        return time.time() >= self.expires_at


_cache_store: dict[str, CacheEntry] = {}
_global_lock = threading.Lock()
_locks: dict[str, threading.Lock] = {}

_SWEEP_INTERVAL = 300
_DEFAULT_MAX_ENTRIES = 2048
_last_sweep_time: float = 0.0


def ttl_cache(
    ttl: int = 300,
    *,
    namespace: str | None = None,
    max_entries: int | None = _DEFAULT_MAX_ENTRIES,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    TTL付きキャッシュデコレータ。

    Args:
        ttl: キャッシュの有効期間（秒）。
        namespace: 省略時は関数の完全名を名前空間にする。
        max_entries: 名前空間ごとの最大エントリ数。Noneなら制限しない。

    Returns:
        `.clear_cache()` と `.cache_info()` を持つラップ済み関数。
    """

    ttl_seconds = int(ttl)
    if ttl_seconds <= 0:
        raise ValueError("ttl must be a positive integer")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache_namespace = namespace or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_cache_key(cache_namespace, args, kwargs)
            now = time.time()

            with _global_lock:
                _sweep_expired_entries(now)
                key_lock = _locks.setdefault(key, threading.Lock())

            with key_lock:
                with _global_lock:
                    entry = _cache_store.get(key)
                    if entry and now < entry.expires_at:
                        return entry.value
                    if entry:
                        _cache_store.pop(key, None)

                result = func(*args, **kwargs)
                created_at = time.time()
                with _global_lock:
                    _cache_store[key] = CacheEntry(
                        value=result,
                        created_at=created_at,
                        expires_at=created_at + ttl_seconds,
                        ttl=ttl_seconds,
                        namespace=cache_namespace,
                    )
                    if max_entries is not None:
                        _enforce_max_entries(cache_namespace, max_entries)
                return result

        def _clear_cache() -> None:
            clear_namespace(cache_namespace)

        def _cache_info() -> dict[str, Any]:
            return cache_info(cache_namespace)

        wrapper.clear_cache = _clear_cache
        wrapper.cache_info = _cache_info
        return wrapper

    return decorator


def clear_namespace(namespace: str) -> int:
    """指定名前空間のキャッシュとロックを削除し、削除件数を返す。"""

    with _global_lock:
        keys_to_delete = [
            key for key, entry in _cache_store.items() if entry.namespace == namespace
        ]
        for key in keys_to_delete:
            _cache_store.pop(key, None)
            _locks.pop(key, None)
    return len(keys_to_delete)


def clear_all_cache() -> None:
    """全キャッシュエントリをクリアする。"""

    with _global_lock:
        count = len(_cache_store)
        _cache_store.clear()
        _locks.clear()
    if count > 0:
        logger.info(f"[Cache] Cleared {count} cached entries")


def cache_info(namespace: str | None = None) -> dict[str, Any]:
    """現在のメモリキャッシュ状態を返す。"""

    now = time.time()
    with _global_lock:
        entries = [
            entry
            for entry in _cache_store.values()
            if namespace is None or entry.namespace == namespace
        ]
        namespace_counts: dict[str, int] = {}
        for entry in entries:
            namespace_counts[entry.namespace] = (
                namespace_counts.get(entry.namespace, 0) + 1
            )
        expired = sum(1 for entry in entries if now >= entry.expires_at)
        next_expiration = min(
            (entry.expires_at for entry in entries if now < entry.expires_at),
            default=None,
        )
    return {
        "entries": len(entries),
        "expired_entries": expired,
        "namespaces": namespace_counts,
        "next_expiration": next_expiration,
    }


def _make_cache_key(
    namespace: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str:
    try:
        kwargs_part = tuple(sorted(kwargs.items()))
        return f"{namespace}:{repr(args)}:{repr(kwargs_part)}"
    except Exception:
        return f"{namespace}:{str(args)}:{str(kwargs)}"


def _sweep_expired_entries(now: float) -> None:
    """期限切れエントリを掃除する。_global_lock保持中に呼ぶ。"""

    global _last_sweep_time
    if now - _last_sweep_time < _SWEEP_INTERVAL:
        return

    _last_sweep_time = now
    keys_to_delete = [
        key for key, entry in _cache_store.items() if now >= entry.expires_at
    ]
    for key in keys_to_delete:
        _cache_store.pop(key, None)
        _locks.pop(key, None)

    if keys_to_delete:
        logger.debug(f"[Cache] Swept {len(keys_to_delete)} expired entries")


def _enforce_max_entries(namespace: str, max_entries: int) -> None:
    if max_entries <= 0:
        return

    namespace_items = [
        (key, entry)
        for key, entry in _cache_store.items()
        if entry.namespace == namespace
    ]
    overflow = len(namespace_items) - max_entries
    if overflow <= 0:
        return

    namespace_items.sort(key=lambda item: item[1].created_at)
    for key, _ in namespace_items[:overflow]:
        _cache_store.pop(key, None)
        _locks.pop(key, None)
