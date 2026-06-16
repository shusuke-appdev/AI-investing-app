from src.services import market_strategy_service as service


def _levels(behavior: str):
    return {
        "items": [
            {
                "label": "S&P 500",
                "ticker": "SPY",
                "support": 500,
                "resistance": 550,
                "behavior": behavior,
                "behavior_label": behavior,
                "data_quality": "ok",
            }
        ]
    }


def _timeframes(current: float, one_week: float):
    return {
        "items": [
            {"key": "current", "score": current},
            {"key": "one_week", "score": one_week},
        ]
    }


def _squeeze_options():
    return [
        {
            "pcr": {"volume_pcr": 0.5},
            "gex": {"nearby_net_gex": -1_000_000},
        }
    ]


def test_strategy_regime_selects_five_requested_classes():
    assert (
        service.select_strategy_regime(_levels("breakout"), _timeframes(0.6, 0.5))[
            "key"
        ]
        == "aggressive_trend_following"
    )
    assert (
        service.select_strategy_regime(_levels("range"), _timeframes(0.3, 0.2))["key"]
        == "trend_following"
    )
    assert (
        service.select_strategy_regime(_levels("range"), _timeframes(0.0, 0.0))["key"]
        == "wait"
    )
    assert (
        service.select_strategy_regime(
            _levels("near_support"), _timeframes(-0.3, -0.1)
        )["key"]
        == "mean_reversion"
    )
    assert (
        service.select_strategy_regime(
            _levels("support_bounce"),
            _timeframes(0.0, 0.0),
            options=_squeeze_options(),
        )["key"]
        == "aggressive_mean_reversion"
    )


def test_timeframe_outlooks_expose_direction_labels():
    result = service.build_timeframe_outlooks(
        _levels("breakout"),
        {"items": []},
        trend_ranking={"items": [{"total_score": 60}], "summary": "AI leads."},
    )

    labels = {item["key"]: item["direction_label"] for item in result["items"]}
    assert labels["current"] == "上昇相場"
    assert labels["one_month"] in {"上昇相場", "レンジ相場", "下落相場"}
