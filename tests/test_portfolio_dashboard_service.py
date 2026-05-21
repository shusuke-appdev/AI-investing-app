from types import SimpleNamespace

from src.services.portfolio_dashboard_service import (
    holdings_to_payload,
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
