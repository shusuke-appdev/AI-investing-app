from src.persistent_cache import PersistentJsonCache
from src.services import provider_health
from src.services.analysis_context import DataResult


def test_provider_health_records_success_and_failure(monkeypatch, tmp_path):
    store = PersistentJsonCache(
        tmp_path, provider_health.PROVIDER_HEALTH_CACHE_NAMESPACE
    )
    monkeypatch.setattr(provider_health, "_provider_health_cache", lambda: store)

    provider_health.record_data_results(
        [
            DataResult(
                name="market_indices",
                source="yfinance",
                fetched_at="2026-06-17T00:00:00+00:00",
                cache_status="live",
            )
        ],
        scope="market.US",
    )
    provider_health.record_data_results(
        [
            DataResult(
                name="fred_credit",
                source="FRED",
                fetched_at="2026-06-17T00:01:00+00:00",
                error="timeout",
                cache_status="failed",
            )
        ],
        scope="market.US",
    )

    rows = {item.name: item for item in provider_health.load_provider_health()}

    assert rows["market.US.market_indices"].status_key == "ok"
    assert rows["market.US.market_indices"].last_success_at == (
        "2026-06-17T00:00:00+00:00"
    )
    assert rows["market.US.fred_credit"].status_key == "failed"
    assert rows["market.US.fred_credit"].last_error == "timeout"


def test_data_quality_state_reads_provider_health(monkeypatch, tmp_path):
    from frontend.state import data_quality_state

    store = PersistentJsonCache(
        tmp_path, provider_health.PROVIDER_HEALTH_CACHE_NAMESPACE
    )
    monkeypatch.setattr(provider_health, "_provider_health_cache", lambda: store)
    provider_health.record_data_results(
        [
            DataResult(
                name="options",
                source="persistent_cache",
                fetched_at="2026-06-17T00:00:00+00:00",
                is_stale=True,
                cache_status="stale_cache",
                cache_age_seconds=7200,
            )
        ],
        scope="market.US",
    )

    rows = data_quality_state._provider_health()

    assert rows[0].name == "market.US.options"
    assert rows[0].status_key == "stale"
    assert rows[0].cache_age_label == "2.0h"
