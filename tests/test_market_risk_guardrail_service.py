from src.services.market_risk_guardrail_service import (
    _target_assessment,
    apply_market_risk_cap,
)


def test_market_risk_cap_only_downgrades_stance():
    extreme = {"action_cap": "protect"}
    high = {"action_cap": "watch"}

    assert apply_market_risk_cap("ready", extreme) == "protect"
    assert apply_market_risk_cap("watch", extreme) == "protect"
    assert apply_market_risk_cap("ready", high) == "watch"
    assert apply_market_risk_cap("protect", high) == "protect"


def test_inactive_guardrail_never_changes_stance():
    guardrail = {"action_cap": "none", "status": "research_only"}

    assert apply_market_risk_cap("ready", guardrail) == "ready"
    assert apply_market_risk_cap("watch", guardrail) == "watch"


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
