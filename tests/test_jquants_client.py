from unittest.mock import MagicMock, patch

from src.jquants_client import (
    _get_headers,
    get_daily_quotes,
    get_fins_statements,
    is_configured,
)


@patch("src.jquants_client.get_jquants_api_key")
def test_is_configured(mock_get_key):
    mock_get_key.return_value = "dummy_key"
    assert is_configured() is True

    mock_get_key.return_value = ""
    assert is_configured() is False


@patch("src.jquants_client.get_jquants_api_key")
def test_get_headers(mock_get_key):
    mock_get_key.return_value = "dummy_key"
    headers = _get_headers()
    assert headers == {"x-api-key": "dummy_key"}


@patch("src.jquants_client._get_headers")
@patch("src.jquants_client.requests.get")
def test_get_daily_quotes(mock_get, mock_get_headers):
    mock_get_headers.return_value = {"x-api-key": "dummy"}
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "daily_quotes": [
            {
                "Date": "2024-01-01",
                "Open": 100,
                "High": 110,
                "Low": 90,
                "Close": 105,
                "Volume": 1000,
                "AdjustmentOpen": 100,
                "AdjustmentHigh": 110,
                "AdjustmentLow": 90,
                "AdjustmentClose": 105,
                "AdjustmentVolume": 1000,
            }
        ]
    }
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    df = get_daily_quotes("7203.T", period="1d")
    assert not df.empty
    assert "Open" in df.columns
    assert df.iloc[0]["Close"] == 105


@patch("src.jquants_client._get_headers")
@patch("src.jquants_client.requests.get")
def test_get_fins_statements(mock_get, mock_get_headers):
    mock_get_headers.return_value = {"x-api-key": "dummy"}
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "statements": [
            {
                "DiscloseDate": "2024-02-01",
                "NetSales": "1000.5",
                "OperatingProfit": "100.2",
            }
        ]
    }
    mock_get.return_value = mock_response

    fins = get_fins_statements("7203.T")
    assert fins is not None
    assert fins["net_sales"] == 1000.5
    assert fins["operating_income"] == 100.2
