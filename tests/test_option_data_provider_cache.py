from datetime import datetime, timedelta, timezone

import pandas as pd

from src import option_data_provider


def test_option_provider_uses_stale_persistent_cache_when_refresh_fails(
    monkeypatch, tmp_path
):
    cache_file = tmp_path / "SPY.json"
    calls = pd.DataFrame(
        {
            "strike": [100],
            "volume": [10],
            "openInterest": [100],
            "impliedVolatility": [0.2],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [100],
            "volume": [20],
            "openInterest": [200],
            "impliedVolatility": [0.25],
        }
    )
    fetched_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    monkeypatch.setattr(option_data_provider, "_cache_file", lambda ticker: cache_file)
    monkeypatch.setattr(option_data_provider, "_is_market_likely_closed", lambda: False)
    monkeypatch.setattr(
        option_data_provider, "_fetch_with_timeout", lambda ticker: None
    )
    option_data_provider._fallback_cache.clear()
    option_data_provider._metadata_cache.clear()
    option_data_provider._save_persistent_cache("SPY", calls, puts, fetched_at)

    result = option_data_provider.get_option_chain("SPY")
    metadata = option_data_provider.get_option_chain_metadata("SPY")

    assert result is not None
    assert result[0]["strike"].iloc[0] == 100
    assert metadata["source"] == "persistent_cache"
    assert metadata["data_quality"] == "stale_cache"
    assert metadata["is_stale"] is True
    assert metadata["cache_status"] == "stale_cache"
    assert metadata["cache_age_seconds"] is not None


def test_option_provider_cache_only_never_refreshes(monkeypatch, tmp_path):
    cache_file = tmp_path / "AAPL.json"
    calls = pd.DataFrame({"strike": [100], "openInterest": [10]})
    puts = pd.DataFrame({"strike": [100], "openInterest": [20]})

    monkeypatch.setattr(option_data_provider, "_cache_file", lambda ticker: cache_file)
    monkeypatch.setattr(
        option_data_provider,
        "_get_yfinance_option_chain",
        lambda ticker: (_ for _ in ()).throw(AssertionError("live refresh ran")),
    )
    option_data_provider._save_persistent_cache(
        "AAPL", calls, puts, datetime.now(timezone.utc).isoformat()
    )

    result = option_data_provider.get_option_chain("AAPL", cache_only=True)

    assert result is not None
    assert result[0]["strike"].iloc[0] == 100
    assert (
        "保存済み"
        in option_data_provider.get_option_chain_metadata("AAPL")["quality_warnings"][0]
    )


def test_marketdata_is_only_used_when_explicitly_allowed(monkeypatch):
    calls = pd.DataFrame({"strike": [100]})
    puts = pd.DataFrame({"strike": [100]})
    marketdata_calls = []

    monkeypatch.setenv("MARKETDATA_OPTIONS_MODE", "preferred")
    monkeypatch.setattr(
        option_data_provider,
        "_get_yfinance_option_chain",
        lambda ticker: (calls, puts),
    )
    monkeypatch.setattr(
        option_data_provider,
        "_fetch_marketdata_chain",
        lambda ticker: (
            marketdata_calls.append(ticker)
            or (
                calls,
                puts,
                {
                    "source": "marketdata.app",
                    "fetched_at": "2026-06-13T00:00:00+00:00",
                    "is_stale": False,
                    "data_quality": "available",
                    "quality_warnings": [],
                    "cache_status": "live",
                    "cache_age_seconds": None,
                },
            )
        ),
    )

    option_data_provider.get_option_chain("SPY")
    assert marketdata_calls == []

    option_data_provider.get_option_chain("SPY", allow_marketdata=True)
    assert marketdata_calls == ["SPY"]


def test_shadow_mode_retains_yfinance_and_records_comparison(monkeypatch):
    y_calls = pd.DataFrame({"strike": [100]})
    y_puts = pd.DataFrame({"strike": [100]})
    m_calls = pd.DataFrame({"strike": [101]})
    m_puts = pd.DataFrame({"strike": [101]})

    monkeypatch.setenv("MARKETDATA_OPTIONS_MODE", "shadow")
    monkeypatch.setattr(
        option_data_provider,
        "_get_yfinance_option_chain",
        lambda ticker: (
            option_data_provider._set_metadata(
                ticker,
                source="yfinance",
                fetched_at="now",
                is_stale=False,
                data_quality="available",
                quality_warnings=[],
                cache_status="live",
                cache_age_seconds=None,
            )
            or (y_calls, y_puts)
        ),
    )
    monkeypatch.setattr(
        option_data_provider,
        "_fetch_marketdata_chain",
        lambda ticker: (
            m_calls,
            m_puts,
            {
                "source": "marketdata.app",
                "data_as_of": "2026-06-13T00:00:00+00:00",
                "data_mode": "delayed",
                "credits_consumed": 1,
                "credits_remaining": 99,
            },
        ),
    )

    result = option_data_provider.get_option_chain("SPY", allow_marketdata=True)
    metadata = option_data_provider.get_option_chain_metadata("SPY")

    assert result is not None
    assert result[0]["strike"].iloc[0] == 100
    assert metadata["source"] == "yfinance"
    assert metadata["shadow_source"] == "marketdata.app"


def test_preferred_mode_marks_yfinance_fallback(monkeypatch):
    calls = pd.DataFrame({"strike": [100]})
    puts = pd.DataFrame({"strike": [100]})

    monkeypatch.setenv("MARKETDATA_OPTIONS_MODE", "preferred")
    monkeypatch.setattr(
        option_data_provider, "_fetch_marketdata_chain", lambda ticker: None
    )
    monkeypatch.setattr(
        option_data_provider,
        "_get_yfinance_option_chain",
        lambda ticker: (
            option_data_provider._set_metadata(
                ticker,
                source="yfinance",
                fetched_at="now",
                is_stale=False,
                data_quality="available",
                quality_warnings=[],
                cache_status="live",
                cache_age_seconds=None,
            )
            or (calls, puts)
        ),
    )

    result = option_data_provider.get_option_chain("SPY", allow_marketdata=True)
    metadata = option_data_provider.get_option_chain_metadata("SPY")

    assert result is not None
    assert metadata["source"] == "yfinance"
    assert any("fallback" in item for item in metadata["quality_warnings"])
