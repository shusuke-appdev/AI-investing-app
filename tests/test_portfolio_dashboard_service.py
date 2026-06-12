from types import SimpleNamespace

from src.services.portfolio_dashboard_service import (
    holdings_to_payload,
    run_portfolio_analysis,
    validate_holding_input,
)


def test_validate_holding_input_requires_positive_shares():
    result = validate_holding_input("AAPL", "0", "")

    assert not result.is_valid
    assert "0より大きい" in result.error


def test_validate_holding_input_normalizes_valid_values():
    result = validate_holding_input(" aapl ", "2.5", "150")

    assert result.is_valid
    assert result.ticker == "AAPL"
    assert result.shares == 2.5
    assert result.avg_cost == 150.0


def test_holdings_to_payload_filters_non_positive_rows():
    payload = holdings_to_payload(
        [
            SimpleNamespace(ticker="AAPL", shares=2, avg_cost=150.0),
            SimpleNamespace(ticker="MSFT", shares=0, avg_cost=None),
        ]
    )

    assert payload == [{"ticker": "AAPL", "shares": 2.0, "avg_cost": 150.0}]


def test_portfolio_analysis_excludes_missing_prices(monkeypatch):
    from src.advisor import analysis

    monkeypatch.setattr(
        analysis,
        "get_stock_info",
        lambda ticker: {"current_price": 100.0 if ticker == "AAPL" else None},
    )
    monkeypatch.setattr(analysis, "analyze_technical", lambda ticker: None)

    result = run_portfolio_analysis(
        [
            {"ticker": "AAPL", "shares": 2, "avg_cost": 90},
            {"ticker": "MISSING", "shares": 3, "avg_cost": 10},
        ]
    )

    assert result["total_value"] == 200.0
    assert result["num_holdings"] == 1
    assert result["excluded_holdings"][0]["ticker"] == "MISSING"
    assert result["provenance"][0]["kind"] == "direct"
