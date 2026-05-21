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
