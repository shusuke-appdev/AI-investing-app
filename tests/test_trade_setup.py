import pandas as pd

from src.advisor import trade_setup


def _history(*, rows: int = 260, falling_ma200: bool = False) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="B")
    if falling_ma200:
        close = pd.Series(
            [300 - index * 0.5 for index in range(rows)], index=dates, dtype=float
        )
    else:
        close = pd.Series(
            [100 + index * 0.2 for index in range(rows)], index=dates, dtype=float
        )
    volume = pd.Series([1_000_000.0] * rows, index=dates)
    volume.iloc[-1] = 2_000_000.0
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": volume,
        }
    )


def test_trade_setup_blocks_declining_200ma(monkeypatch):
    stock = _history(falling_ma200=True)
    benchmark = _history()

    monkeypatch.setattr(
        trade_setup,
        "get_stock_data",
        lambda ticker, period: benchmark if ticker in {"SPY", "XLK"} else stock,
    )

    result = trade_setup.evaluate_trade_setup(
        "TEST",
        {"sector": "Technology"},
        {"vcp_data": {"is_vcp": False}, "obv_trend": "下降"},
        stock,
    )

    assert result.status == "blocked"
    assert any("200MA" in reason for reason in result.blocked_reasons)
    assert result.rvol > 1.5


def test_trade_setup_exposes_daily_proxy_metrics(monkeypatch):
    stock = _history()
    benchmark = _history()

    monkeypatch.setattr(trade_setup, "get_stock_data", lambda ticker, period: benchmark)

    result = trade_setup.evaluate_trade_setup(
        "TEST",
        {"sector": "Technology"},
        {
            "vcp_data": {"is_vcp": True, "breakout_price": stock["Close"].iloc[-2]},
            "base_recognition_data": {"detected": True},
            "obv_trend": "上昇",
        },
        stock,
    ).to_dict()

    assert result["benchmark"] == "SPY"
    assert result["rvol"] > 1.5
    assert result["profit_extension_levels"]["4x"] > 0
    assert any(item["key"] == "vars_proxy" for item in result["checks"])
    assert any("LoD" in warning for warning in result["warnings"])


def test_trade_setup_uses_japan_benchmark(monkeypatch):
    stock = _history()
    monkeypatch.setattr(trade_setup, "get_stock_data", lambda ticker, period: stock)

    result = trade_setup.evaluate_trade_setup("7203.T", {}, {}, stock)

    assert result.market_type == "JP"
    assert result.benchmark == "1306.T"
