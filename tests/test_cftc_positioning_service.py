from datetime import date

import pandas as pd

from src.services.cftc_positioning_service import parse_cftc_positioning


def test_parse_cftc_positioning_applies_conservative_publication_lag():
    result = parse_cftc_positioning(
        [
            {
                "report_date_as_yyyy_mm_dd": "2026-06-30T00:00:00.000",
                "open_interest_all": "1000",
                "asset_mgr_positions_long": "500",
                "asset_mgr_positions_short": "100",
                "lev_money_positions_long": "120",
                "lev_money_positions_short": "320",
            }
        ]
    )

    assert result.index[0].date() == date(2026, 7, 6)
    assert result.iloc[0]["cftc_asset_manager_net_oi"] == 0.4
    assert result.iloc[0]["cftc_leveraged_money_net_oi"] == -0.2


def test_cftc_features_are_reserved_for_twenty_day_horizon():
    from src.services import market_short_horizon_forecast as forecast

    index = pd.date_range("2020-01-01", periods=1800, freq="B")
    features = pd.DataFrame(
        {
            "target_return_1d": range(1800),
            "cftc_asset_manager_net_oi": range(1800),
        },
        index=index,
    )

    assert "cftc_asset_manager_net_oi" not in forecast._select_features(features, 5)
    assert "cftc_asset_manager_net_oi" in forecast._select_features(features, 20)
