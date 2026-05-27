import numpy as np
import pandas as pd

from src.advisor.trend_follow_diagnostics import (
    TrendFollowConfig,
    _run_strategy,
    _tail_dependency,
    generate_trend_follow_diagnostics,
    trend_follow_to_dict,
)


def _price_frame(rows: int = 360) -> pd.DataFrame:
    index = pd.bdate_range("2021-01-01", periods=rows)
    trend = np.linspace(0, rows * 0.08, rows)
    cycle = np.sin(np.arange(rows) / 13) * 1.5
    close = 100 + trend + cycle
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )


def test_strategy_enters_after_close_signal_without_same_day_lookahead():
    prices = pd.DataFrame(
        {
            "Open": [10.0, 10.0, 10.0, 20.0, 20.0, 20.0],
            "High": [10.0, 10.0, 10.0, 20.0, 20.0, 20.0],
            "Low": [10.0, 10.0, 10.0, 20.0, 20.0, 20.0],
            "Close": [10.0, 10.0, 10.0, 20.0, 20.0, 20.0],
            "Volume": [1000] * 6,
        },
        index=pd.bdate_range("2026-01-01", periods=6),
    )
    config = TrendFollowConfig(short_window=2, long_window=3, round_trip_cost_bps=0.0)

    run = _run_strategy(prices, config)
    first_signal_idx = int(
        (prices["Close"].rolling(2).mean() > prices["Close"].rolling(3).mean()).idxmax()
        == prices.index[3]
    )

    assert first_signal_idx == 1
    assert run.position_at_open.iloc[3] == 0.0
    assert run.position_at_open.iloc[4] == 1.0
    assert run.returns.iloc[4] == 0.0


def test_tail_dependency_removes_best_trade_buckets():
    class Trade:
        def __init__(self, net_return):
            self.net_return = net_return

    trades = [Trade(0.50), Trade(-0.10), Trade(-0.05), Trade(0.02)]

    result = _tail_dependency(trades)

    assert result["base_sum"] > 0
    assert result["remove_top_5_pct_sum"] < 0
    assert result["tail_dependent"] is True


def test_generate_diagnostics_returns_core_sections_and_display_fields():
    diagnostics = generate_trend_follow_diagnostics(
        "TEST",
        price_df=_price_frame(),
    )
    data = trend_follow_to_dict(diagnostics)

    assert diagnostics.ticker == "TEST"
    assert diagnostics.data_quality["status"] == "ok"
    assert "total_return" in diagnostics.strategy_metrics
    assert "oos_alpha_vs_buy_hold" in diagnostics.dev_oos
    assert diagnostics.cost_sensitivity
    assert diagnostics.lag_sensitivity
    assert diagnostics.parameter_grid
    assert data["strategy_total_return_display"].endswith("%")
    assert data["warnings_display"].startswith("- ")


def test_random_direction_diagnostics_are_seeded_and_repeatable():
    prices = _price_frame()

    first = generate_trend_follow_diagnostics("TEST", price_df=prices)
    second = generate_trend_follow_diagnostics("TEST", price_df=prices)

    assert first.random_direction == second.random_direction


def test_short_history_returns_unavailable_not_exception():
    diagnostics = generate_trend_follow_diagnostics(
        "TEST",
        price_df=_price_frame(rows=80),
    )

    assert diagnostics.diagnostic_rating == "Unavailable"
    assert diagnostics.data_quality["status"] == "insufficient_data"
