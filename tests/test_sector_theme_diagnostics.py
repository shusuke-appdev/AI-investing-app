import pandas as pd

from src.advisor import sector_theme_diagnostics as diagnostics


def _history(start: float, end: float):
    values = [start + (end - start) * idx / 130 for idx in range(131)]
    return pd.DataFrame(
        {"Close": values},
        index=pd.date_range("2025-01-01", periods=len(values)),
    )


def test_market_distortions_detects_bullish_and_bearish_gaps(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "get_themes",
        lambda market_type: {
            "Fundamental ignored": ["AAA", "AAB"],
            "Flow crowded": ["BBB", "BBC"],
        },
    )

    def fake_info(ticker, include_summary=False):
        if ticker.startswith("AA"):
            return {
                "revenueGrowth": 35,
                "earningsGrowth": 40,
                "operatingMargins": 28,
                "returnOnEquity": 30,
                "forward_pe": 22,
                "pe_ratio": 30,
                "pegRatio": 1.1,
            }
        return {
            "revenueGrowth": -5,
            "earningsGrowth": -10,
            "operatingMargins": 5,
            "returnOnEquity": 4,
            "forward_pe": 70,
            "pe_ratio": 60,
            "pegRatio": 3.5,
        }

    def fake_history(ticker, period):
        if ticker == "SPY":
            return _history(100, 120)
        if ticker.startswith("AA"):
            return _history(100, 95)
        return _history(100, 155)

    monkeypatch.setattr(diagnostics, "get_stock_info", fake_info)
    monkeypatch.setattr(diagnostics, "get_stock_data", fake_history)

    result = diagnostics.detect_market_distortions("US", max_themes=2, top_n=5)

    assert result["bullish"][0]["theme"] == "Fundamental ignored"
    assert result["bullish"][0]["tickers"] == ["AAA", "AAB"]
    assert result["bearish"][0]["theme"] == "Flow crowded"
    assert result["bearish"][0]["tickers"] == ["BBB", "BBC"]


def test_stock_sector_theme_context_rates_both_advantages_high(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "get_themes",
        lambda market_type: {"AI": ["AAA"], "Other": ["BBB"]},
    )
    monkeypatch.setattr(
        diagnostics,
        "get_stock_info",
        lambda ticker, include_summary=False: {
            "revenueGrowth": 30,
            "earningsGrowth": 35,
            "operatingMargins": 25,
            "returnOnEquity": 25,
            "forward_pe": 25,
            "pe_ratio": 35,
            "pegRatio": 1.0,
        },
    )
    monkeypatch.setattr(
        diagnostics,
        "get_stock_data",
        lambda ticker, period: _history(100, 150 if ticker != "SPY" else 110),
    )

    context = diagnostics.evaluate_stock_sector_theme_context(
        "AAA",
        {
            "sector": "Technology",
            "industry": "Software",
            "revenueGrowth": 30,
            "earningsGrowth": 35,
            "operatingMargins": 25,
            "returnOnEquity": 25,
            "forward_pe": 25,
            "pe_ratio": 35,
            "pegRatio": 1.0,
        },
    )

    assert context["combined_rating"] == "high"
    assert context["fundamental_advantage"] is True
    assert context["flow_advantage"] is True


def test_missing_fundamentals_are_unavailable_not_zero(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "get_themes",
        lambda market_type: {"Missing": ["AAA", "BBB"]},
    )
    monkeypatch.setattr(
        diagnostics,
        "get_stock_info",
        lambda ticker, include_summary=False: {},
    )
    monkeypatch.setattr(
        diagnostics,
        "get_stock_data",
        lambda ticker, period: _history(100, 120),
    )

    result = diagnostics.evaluate_theme_diagnostics("US")

    assert result[0].fundamental_score is None
    assert result[0].distortion_score is None
    assert result[0].classification == "unavailable"
    assert result[0].rating == "unavailable"


def test_stock_context_exposes_unavailable_score_display(monkeypatch):
    monkeypatch.setattr(diagnostics, "get_themes", lambda market_type: {})

    context = diagnostics.evaluate_stock_sector_theme_context(
        "AAA",
        {"sector": "Technology", "industry": "Software"},
        stock_price_df=pd.DataFrame(),
        benchmark_price_df=pd.DataFrame(),
    )

    assert context["combined_rating"] == "unavailable"
    assert context["stock_fundamental_score"] is None
    assert context["stock_fundamental_score_display"] == "算出不可"
