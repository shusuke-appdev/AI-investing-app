import pytest

from src.persistent_cache import PersistentJsonCache
from src.services.analysis_jobs import AnalysisJobStore


def _store(tmp_path) -> AnalysisJobStore:
    return AnalysisJobStore(PersistentJsonCache(tmp_path, "analysis_jobs"))


def test_analysis_job_success_lifecycle_is_persisted(tmp_path):
    store = _store(tmp_path)
    job = store.enqueue(
        "watchlist_scoring",
        {"tickers": ["AAPL", "MSFT"]},
        job_id="job-1",
        timeout_seconds=30,
    )

    assert job.status == "queued"

    running = store.start("job-1")
    assert running.status == "running"
    assert running.attempts == 1

    done = store.succeed(
        "job-1",
        {"scored": 2},
        warnings=["MSFT used cached profile"],
        last_successful_cache="watchlist/job-1.json",
    )

    assert done.status == "succeeded"
    assert store.get("job-1").last_successful_cache == "watchlist/job-1.json"
    assert [item.job_id for item in store.list_jobs()] == ["job-1"]


def test_analysis_job_retries_then_fails(tmp_path):
    store = _store(tmp_path)
    store.enqueue("walk_forward", {"ticker": "SPY"}, job_id="job-2", max_retries=1)
    store.start("job-2")

    retry = store.fail("job-2", "provider unavailable")
    assert retry.status == "queued"

    store.start("job-2")
    failed = store.fail("job-2", "provider unavailable")

    assert failed.status == "failed"
    assert failed.error == "provider unavailable"


def test_analysis_job_partial_timeout_and_cancel_states(tmp_path):
    store = _store(tmp_path)
    store.enqueue("option_refresh", {"ticker": "SPY"}, job_id="partial")
    store.start("partial")
    partial = store.succeed("partial", {"rows": 1}, partial=True)
    assert partial.status == "partial"

    store.enqueue("backtest", {"ticker": "QQQ"}, job_id="timeout", timeout_seconds=5)
    timed_out = store.mark_timed_out("timeout")
    assert timed_out.status == "failed"
    assert "5 seconds" in timed_out.error

    store.enqueue("news_batch", {"tickers": ["AAPL"]}, job_id="cancel")
    cancelled = store.cancel("cancel")
    assert cancelled.status == "cancelled"

    with pytest.raises(ValueError):
        store.cancel("partial")
