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


def test_timeframe_outlooks_use_option_horizons_as_evidence():
    result = service.build_timeframe_outlooks(
        _levels("range"),
        {"items": []},
        option_horizons=[
            {
                "key": "one_week",
                "label": "1週間",
                "iv": 0.22,
                "expected_move_pct": 0.018,
                "pcr_volume": 1.4,
                "skew": 0.08,
                "nearby_net_gex": -1_000_000,
            },
            {
                "key": "one_month",
                "label": "1か月",
                "iv": 0.3,
                "expected_move_pct": 0.07,
                "pcr_volume": 1.1,
                "skew": 0.03,
                "nearby_net_gex": 500_000,
            },
        ],
    )

    lookup = {item["key"]: item for item in result["items"]}
    assert any("1Wオプション" in item for item in lookup["one_week"]["evidence"])
    assert any("1Mオプション" in item for item in lookup["one_month"]["evidence"])
    assert lookup["one_week"]["score"] < lookup["current"]["score"]


def test_validated_forecast_is_primary_for_week_and_month_direction():
    forecast = {
        "is_stale": False,
        "targets": {
            "SPY": {
                "horizons": {
                    "5d": {
                        "status": "validated",
                        "probability_up": 0.35,
                        "direction_label": "下方向バイアス",
                    },
                    "20d": {
                        "status": "validated",
                        "probability_up": 0.65,
                        "direction_label": "上方向バイアス",
                    },
                }
            }
        },
    }

    result = service.build_timeframe_outlooks(
        _levels("range"),
        {"items": []},
        short_horizon_forecast=forecast,
    )

    lookup = {item["key"]: item for item in result["items"]}
    assert lookup["one_week"]["score"] < 0
    assert lookup["one_month"]["score"] > 0
    assert any("検証済みSPY 5日予測" in item for item in lookup["one_week"]["evidence"])


def test_research_only_forecast_does_not_replace_existing_outlook():
    forecast = {
        "targets": {
            "SPY": {
                "horizons": {"5d": {"status": "research_only", "probability_up": 0.1}}
            }
        }
    }

    baseline = service.build_timeframe_outlooks(_levels("breakout"), {"items": []})
    result = service.build_timeframe_outlooks(
        _levels("breakout"),
        {"items": []},
        short_horizon_forecast=forecast,
    )

    assert result["items"][1]["score"] == baseline["items"][1]["score"]


def test_confirmed_composite_risk_only_caps_strategy_budget():
    result = service.select_strategy_regime(
        _levels("breakout"),
        _timeframes(0.6, 0.5),
        composite_sentiment={
            "integration_enabled": True,
            "risk_floor": "extreme",
            "state_label": "下方向の増幅警戒",
        },
    )

    assert result["key"] == "aggressive_trend_following"
    assert result["risk_budget"] == "0-15%"


def test_composite_cap_never_increases_existing_risk_budget():
    medium = {"integration_enabled": True, "risk_floor": "medium"}
    high = {"integration_enabled": True, "risk_floor": "high"}

    assert service._cap_risk_budget("0-30%", medium) == "0-30%"
    assert service._cap_risk_budget("10-30%", high) == "10-30%"
    assert service._cap_risk_budget("30-70%", medium) == "0-50%"
