from src.option_market_aggregate import _aggregate_option_horizons


def _result(ticker, value, *, method="delta_25_direct", status="direct", stale=False):
    return {
        "ticker": ticker,
        "is_stale": stale,
        "horizons": [
            {
                "key": "one_week",
                "label": "1週間",
                "skew": value,
                "skew_detail": {
                    "value": value,
                    "method": method,
                    "status": status,
                    "liquidity_status": "ok",
                    "warnings": [],
                },
            }
        ],
    }


def test_spy_direct_skew_is_reference_not_cross_index_average():
    horizon = _aggregate_option_horizons(
        [_result("SPY", 0.08), _result("QQQ", 0.02), _result("IWM", -0.02)]
    )[0]

    assert horizon["skew"] == 0.08
    assert horizon["skew_reference"]["ticker"] == "SPY"
    assert horizon["skew_by_ticker"]["QQQ"]["value"] == 0.02
    assert horizon["skew_dispersion"] == 0.10


def test_proxy_stale_and_legacy_values_cannot_become_skew_reference():
    proxy = _result("SPY", 0.12, method="moneyness_10pct_proxy", status="proxy")
    stale = _result("SPY", 0.12, stale=True)
    legacy = {"ticker": "SPY", "horizons": [{"key": "one_week", "skew": 0.12}]}

    for result in (proxy, stale, legacy):
        horizon = _aggregate_option_horizons([result])[0]
        assert horizon["skew"] is None
        assert horizon["skew_reference"] is None
