from src.services.market_risk_guardrail_service import (
    _target_assessment,
)


def test_stale_forecast_is_not_used_even_when_horizon_was_validated():
    forecast = {
        "is_stale": True,
        "targets": {
            "SPY": {
                "horizons": {
                    "20d": {
                        "status": "validated",
                        "risk_level": "extreme",
                        "direction": "downside_bias",
                    }
                }
            }
        },
    }

    result = _target_assessment("SPY", forecast, {})

    assert result["available"] is False
    assert result["risk_level"] == "unknown"
