import threading
import time

import pytest

from src import cache


@pytest.fixture(autouse=True)
def clear_memory_cache():
    cache.clear_all_cache()
    cache._last_sweep_time = 0.0
    yield
    cache.clear_all_cache()
    cache._last_sweep_time = 0.0


def test_ttl_cache_uses_entry_ttl_when_sweeping(monkeypatch):
    now = 1_000.0
    calls = 0

    monkeypatch.setattr(cache.time, "time", lambda: now)

    @cache.ttl_cache(ttl=86_400)
    def expensive_value() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert expensive_value() == 1

    now += 1_801
    assert expensive_value() == 1
    assert calls == 1
    assert expensive_value.cache_info()["entries"] == 1


def test_ttl_cache_sweeps_only_expired_entries(monkeypatch):
    now = 1_000.0
    monkeypatch.setattr(cache.time, "time", lambda: now)

    @cache.ttl_cache(ttl=10, namespace="short")
    def short_value() -> str:
        return "short"

    @cache.ttl_cache(ttl=1_000, namespace="long")
    def long_value() -> str:
        return "long"

    assert short_value() == "short"
    assert long_value() == "long"

    now += 301
    assert long_value() == "long"
    assert cache.cache_info("short")["entries"] == 0
    assert cache.cache_info("long")["entries"] == 1


def test_clear_cache_removes_values_and_locks():
    @cache.ttl_cache(ttl=60)
    def value(item: int) -> int:
        return item

    assert value(1) == 1
    assert value.cache_info()["entries"] == 1

    value.clear_cache()

    assert value.cache_info()["entries"] == 0
    assert cache.cache_info()["entries"] == 0


def test_ttl_cache_deduplicates_concurrent_same_key():
    calls = 0
    start_event = threading.Event()
    results: list[int] = []

    @cache.ttl_cache(ttl=60)
    def expensive_value(item: str) -> int:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return len(item)

    def worker() -> None:
        start_event.wait(timeout=5)
        results.append(expensive_value("SPY"))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    start_event.set()
    for thread in threads:
        thread.join(timeout=5)

    assert results == [3] * 8
    assert calls == 1
