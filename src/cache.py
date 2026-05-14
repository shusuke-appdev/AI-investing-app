"""
汎用TTLキャッシュモジュール
Streamlitの @st.cache_data を完全に代替する、フレームワーク非依存のキャッシュ機構。
"""

import functools
import threading
import time
from collections.abc import Callable
from typing import Any

from src.log_config import get_logger

logger = get_logger(__name__)

_cache_store: dict[str, tuple[Any, float]] = {}
_global_lock = threading.Lock()
_locks: dict[str, threading.Lock] = {}

# 期限切れエントリの掃除間隔（秒）
_SWEEP_INTERVAL = 300  # 5分
_last_sweep_time: float = 0.0


def _sweep_expired_entries() -> None:
    """期限切れキャッシュエントリを掃除する（メモリリーク防止）。
    _global_lock を保持した状態で呼び出すこと。
    """
    global _last_sweep_time
    now = time.time()
    if now - _last_sweep_time < _SWEEP_INTERVAL:
        return

    _last_sweep_time = now
    keys_to_delete = [
        k for k, (_, ts) in _cache_store.items() if now - ts >= _SWEEP_INTERVAL * 6
    ]
    for k in keys_to_delete:
        del _cache_store[k]
        _locks.pop(k, None)

    if keys_to_delete:
        logger.debug(f"[Cache] Swept {len(keys_to_delete)} expired entries")


def ttl_cache(ttl: int = 300):
    """
    TTL付きキャッシュデコレータ。

    関数の引数をキーとしてキャッシュし、ttl秒経過後に自動的に無効化する。
    @st.cache_data(ttl=N) の完全な代替として使用する。

    Args:
        ttl: キャッシュの有効期間（秒）。デフォルト300秒（5分）。

    Usage:
        @ttl_cache(ttl=60)
        def fetch_data(ticker: str) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # hashableでない引数はstr変換でキー化
            try:
                key = f"{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
            except TypeError:
                key = f"{func.__module__}.{func.__qualname__}:{str(args)}:{str(kwargs)}"

            now = time.time()

            with _global_lock:
                if key not in _locks:
                    _locks[key] = threading.Lock()
                key_lock = _locks[key]
                # 低頻度で期限切れエントリを掃除（メモリリーク防止）
                _sweep_expired_entries()

            with key_lock:
                # Double-checked locking
                if key in _cache_store:
                    val, ts = _cache_store[key]
                    if now - ts < ttl:
                        return val

                # キャッシュミス: 関数実行
                result = func(*args, **kwargs)
                _cache_store[key] = (result, time.time())

            return result

        # キャッシュクリアメソッドを付与（テスト用）
        def _clear_cache():
            prefix = f"{func.__module__}.{func.__qualname__}:"
            with _global_lock:
                keys_to_delete = [k for k in _cache_store if k.startswith(prefix)]
                for k in keys_to_delete:
                    del _cache_store[k]

        wrapper.clear_cache = _clear_cache
        return wrapper

    return decorator


def clear_all_cache():
    """全キャッシュエントリをクリアする。"""
    with _global_lock:
        count = len(_cache_store)
        _cache_store.clear()
        _locks.clear()
    if count > 0:
        logger.info(f"[Cache] Cleared {count} cached entries")
