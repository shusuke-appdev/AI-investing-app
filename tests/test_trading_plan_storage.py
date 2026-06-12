from src import trading_plan_storage
from src.services.trading_plan_service import build_trade_plan, display_plan


def test_local_trading_plan_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(trading_plan_storage, "DATA_PATH", tmp_path / "plans.json")
    monkeypatch.setattr(trading_plan_storage, "get_storage_type", lambda: "local")
    plan = build_trade_plan(
        ticker="AAPL",
        entry_date="2026-06-01",
        entry_price=100,
        final_stop_price=90,
        account_value=100_000,
    )

    assert trading_plan_storage.save_trade_plan(plan) is True
    loaded = trading_plan_storage.load_trade_plans()

    assert len(loaded) == 1
    assert loaded[0].plan_id == plan.plan_id
    assert trading_plan_storage.delete_trade_plan(plan.plan_id) is True
    assert trading_plan_storage.load_trade_plans() == []


def test_display_plan_uses_persisted_confirmation_without_market_fetch():
    plan = build_trade_plan(
        ticker="AAPL",
        entry_date="2026-06-01",
        entry_price=100,
        final_stop_price=90,
        account_value=100_000,
    )
    plan.t1_status = "confirmed"

    displayed = display_plan(plan)

    assert displayed["session_stage"] == "T+1"
