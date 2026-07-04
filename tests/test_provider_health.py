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


def test_data_quality_supabase_status_requires_url_and_key(monkeypatch):
    from frontend.state import data_quality_state

    for name in (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    missing_url = data_quality_state._supabase_provider_status()
    assert missing_url.status == "optional_missing"
    assert missing_url.mode == "missing_url"

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    missing_key = data_quality_state._supabase_provider_status()
    assert missing_key.status == "not_configured"
    assert missing_key.mode == "missing_key"
    assert "SUPABASE_SECRET_KEY" in missing_key.detail

    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    configured_secret = data_quality_state._supabase_provider_status()
    assert configured_secret.status == "configured"
    assert configured_secret.mode == "configured_secret"


def test_data_quality_supabase_status_marks_legacy_key(monkeypatch):
    from frontend.state import data_quality_state

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", "legacy")

    configured_legacy = data_quality_state._supabase_provider_status()

    assert configured_legacy.status == "configured"
    assert configured_legacy.mode == "configured_legacy"
    assert "SUPABASE_SECRET_KEY" in configured_legacy.detail
