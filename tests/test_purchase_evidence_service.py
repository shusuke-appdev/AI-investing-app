from src.services.purchase_evidence_service import evaluate_purchase_evidence


def _evaluate(**overrides):
    values = {
        "technical": {
            "overall_score": 82,
            "overall_signal": "Buy",
            "stage_data": {"stage": 2},
        },
        "trade_setup": {"score": 80, "status": "ready"},
        "fundamental_profile": {"score": 78, "status": "available"},
        "sector_theme": {"best_theme_rank_points": 10},
        "probabilistic_signal": {"suggested_action": "Add small", "confidence": "High"},
        "fomo_regime": {"risk_level": "normal"},
    }
    values.update(overrides)
    return evaluate_purchase_evidence(**values)


def test_purchase_evidence_requires_both_sides_and_can_be_candidate():
    result = _evaluate()

    assert result["label"] == "購入候補"
    assert result["score"] >= 75


def test_entry_blocked_caps_purchase_evidence_at_54():
    result = _evaluate(trade_setup={"score": 90, "status": "blocked"})

    assert result["score"] <= 54
    assert result["label"] == "見送り"
    assert "Entry禁止" in result["cap_reasons"]


def test_watch_or_partial_data_caps_at_74():
    result = _evaluate(
        fundamental_profile={"score": 90, "status": "partial"},
        probabilistic_signal={"suggested_action": "Watch", "confidence": "Low"},
    )

    assert result["score"] <= 74
    assert result["label"] == "条件待ち"


def test_missing_fundamental_is_unavailable_not_zero():
    result = _evaluate(fundamental_profile={"score": None, "status": "unavailable"})

    assert result["status"] == "unavailable"
    assert result["score"] is None
