from src.services.data_fetch_manifest import (
    get_data_fetch_manifest,
    required_data_names,
)


def test_data_fetch_manifest_declares_option_horizon_dependency():
    rows = get_data_fetch_manifest("market_options")

    assert rows
    assert rows[0]["name"] == "index_option_horizons"
    assert rows[0]["required"] is True
    assert "1W" in rows[0]["notes"]
    assert "1M" in rows[0]["notes"]
    assert required_data_names("market_options") == ["index_option_horizons"]
