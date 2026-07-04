import pandas as pd

from src.services.japan_supply_demand_service import build_japan_supply_demand_context


def _price_frame_with_high_expiry() -> pd.DataFrame:
    dates = pd.bdate_range("2025-08-01", periods=170)
    high_date = pd.Timestamp("2025-11-03")
    close = pd.Series(100.0, index=dates)
    high = close.copy()
    low = close.copy()
    high.loc[high_date] = 150.0
    low.loc[dates[-30]] = 90.0
    return pd.DataFrame({"Close": close, "High": high, "Low": low}, index=dates)


def test_japan_supply_demand_detects_six_month_margin_setup():
    rows = [
        {
            "date": "2026-03-01",
            "system_buy_balance": 1200,
            "system_sell_balance": 1000,
        },
        {
            "date": "2026-04-01",
            "system_buy_balance": 900,
            "system_sell_balance": 1100,
        },
        {
            "date": "2026-05-01",
            "system_buy_balance": 760,
            "system_sell_balance": 1000,
        },
    ]

    context = build_japan_supply_demand_context(
        "7203",
        _price_frame_with_high_expiry(),
        margin_rows=rows,
        loan_alert={"active": True, "detail": "貸株注意喚起あり"},
        today="2026-05-04",
    )

    assert context["ticker"] == "7203.T"
    assert context["status"] == "available"
    assert context["label"] == "有効候補"
    assert context["margin"]["system_margin_ratio"] == 0.76
    assert context["price_expiry"]["near_high_expiry"] is True


def test_japan_supply_demand_invalidates_after_drop_and_buy_balance_increase():
    dates = pd.bdate_range("2026-01-01", periods=130)
    close = pd.Series(100.0, index=dates)
    close.iloc[-21] = 110.0
    close.iloc[-1] = 95.0
    frame = pd.DataFrame({"Close": close, "High": close, "Low": close}, index=dates)
    rows = [
        {
            "date": "2026-06-01",
            "system_buy_balance": 900,
            "system_sell_balance": 1000,
        },
        {
            "date": "2026-06-08",
            "system_buy_balance": 1200,
            "system_sell_balance": 1000,
        },
    ]

    context = build_japan_supply_demand_context(
        "7203.T",
        frame,
        margin_rows=rows,
        today="2026-07-01",
    )

    assert context["label"] == "無効化警戒"
    assert context["score"] <= 0.25
    assert context["invalidation"]["active"] is True


def test_japan_supply_demand_skips_non_japanese_tickers():
    context = build_japan_supply_demand_context("AAPL", pd.DataFrame())

    assert context["status"] == "not_applicable"
    assert context["items"] == []
