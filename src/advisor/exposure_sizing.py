"""Convert probabilistic stock signals into conservative exposure guidance."""

from __future__ import annotations

from typing import Any


def suggest_exposure(
    expected_return: float,
    risk_adjusted_signal: float,
    confidence: str,
    realized_vol_20d: float | None,
    realized_vol_percentile: float | None,
    adverse_loss_p95: float | None,
    regime_fit: float,
    cost_adjusted_threshold: float = 0.002,
) -> dict[str, Any]:
    """Return action and max allocation without giving a hard trade instruction."""

    notes: list[str] = []
    max_allocation = 0
    size_multiplier = 0.0

    if expected_return <= cost_adjusted_threshold:
        action = "Avoid" if expected_return < 0 else "Watch"
        notes.append("Cost-adjusted expected return is not compelling.")
        return {
            "suggested_action": action,
            "max_allocation_pct": max_allocation,
            "size_multiplier": size_multiplier,
            "reason": "Expected edge does not clear transaction-cost threshold.",
            "risk_cap_notes": notes,
        }

    if risk_adjusted_signal >= 0.75:
        max_allocation = 5
        size_multiplier = 1.0
        action = "Add small"
    elif risk_adjusted_signal >= 0.35:
        max_allocation = 3
        size_multiplier = 0.75
        action = "Add small"
    else:
        max_allocation = 2
        size_multiplier = 0.5
        action = "Hold"

    if confidence == "Low" or regime_fit < 50:
        max_allocation = min(max_allocation, 1)
        size_multiplier = min(size_multiplier, 0.25)
        notes.append("Low confidence or weak regime fit caps exposure at 1%.")

    if realized_vol_percentile is not None and realized_vol_percentile >= 80:
        max_allocation = max(1, int(max_allocation * 0.5))
        size_multiplier = min(size_multiplier, 0.5)
        notes.append("Realized volatility is above its 80th percentile.")

    if adverse_loss_p95 is not None and adverse_loss_p95 > abs(expected_return) * 3:
        max_allocation = max(1, int(max_allocation * 0.5))
        size_multiplier = min(size_multiplier, 0.5)
        notes.append(
            "Historical adverse excursion is large relative to expected return."
        )

    if realized_vol_20d is not None and realized_vol_20d >= 0.80:
        max_allocation = min(max_allocation, 1)
        size_multiplier = min(size_multiplier, 0.25)
        notes.append("Annualized realized volatility is extremely high.")

    if max_allocation <= 1 and action == "Add small":
        action = "Watch"

    if not notes:
        notes.append("Sizing reflects expected return, volatility, and regime fit.")

    return {
        "suggested_action": action,
        "max_allocation_pct": max_allocation,
        "size_multiplier": round(size_multiplier, 2),
        "reason": notes[0],
        "risk_cap_notes": notes,
    }
