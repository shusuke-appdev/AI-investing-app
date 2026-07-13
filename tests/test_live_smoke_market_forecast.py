def _forecast_payload():
    horizons = {
        key: {
            "status": "research_only",
            "probability_up": 0.52,
            "oos_metrics": {"oos_predictions": 504},
        }
        for key in ("1d", "5d", "20d")
    }
    return {
        "status": "research_only",
        "targets": {
            "SPY": {"horizons": horizons},
            "QQQ": {"horizons": horizons},
        },
    }


def test_market_forecast_smoke_accepts_research_only_with_oos(monkeypatch):
    from scripts import live_smoke
    from src.services import (
        market_composite_sentiment,
        market_short_horizon_forecast,
    )

    monkeypatch.setattr(
        market_short_horizon_forecast,
        "build_market_short_horizon_forecast",
        lambda **kwargs: _forecast_payload(),
    )
    monkeypatch.setattr(
        market_composite_sentiment,
        "build_market_composite_sentiment",
        lambda **kwargs: {
            "targets": {
                "SPY": {"state": "mixed", "status": "confirmed"},
                "QQQ": {"state": "hidden_tail_hedging", "status": "partial"},
            }
        },
    )

    detail = live_smoke._market_forecast_check(required=True)

    assert "SPY:1d:research_only" in detail
    assert "QQQ:composite=hidden_tail_hedging/partial" in detail


def test_market_forecast_smoke_skips_without_explicit_flag():
    from scripts import live_smoke

    assert live_smoke._market_forecast_check(required=False).startswith("SKIP:")
