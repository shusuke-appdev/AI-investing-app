import pandas as pd

from src.services.trading_plan_service import (
    active_entry_limit_exceeded,
    build_trade_plan,
    composite_loss_r,
    confirmation_stage,
    review_metrics,
    suggested_shares,
)


def _plan(ticker: str = "AAPL", entry_date: str = "2026-06-01"):
    return build_trade_plan(
        ticker=ticker,
        entry_date=entry_date,
        entry_price=100,
        final_stop_price=90,
        account_value=100_000,
        risk_percent=0.5,
        setup_snapshot={"grade": "A", "status": "ready"},
    )


def test_build_trade_plan_uses_risk_sizing_and_three_stops():
    plan = _plan()

    assert suggested_shares(100_000, 0.5, 100, 90) == 50
    assert plan.shares == 50
    assert len(plan.stops) == 3
    assert composite_loss_r(plan) == -0.67


def test_active_entry_limit_blocks_fourth_plan():
    plans = [_plan(ticker) for ticker in ("AAPL", "MSFT", "NVDA")]
    for plan in plans:
        plan.status = "active"

    assert active_entry_limit_exceeded(plans, "2026-06-01") is True


def test_confirmation_stage_counts_available_sessions():
    history = pd.DataFrame(
        {"Close": [100, 101, 102, 103]},
        index=pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"]),
    )

    assert confirmation_stage("2026-06-01", history) == "T+3"


def test_review_metrics_uses_realized_r():
    winner = _plan("AAPL")
    winner.status = "closed"
    winner.realized_r = 4.0
    loser = _plan("MSFT")
    loser.status = "closed"
    loser.realized_r = -0.67
    loser.mistake_tags = ["chased"]

    result = review_metrics([winner, loser])

    assert result["win_rate"] == 50.0
    assert result["expectancy_r"] == 1.67
    assert result["mistake_counts"]["chased"] == 1
