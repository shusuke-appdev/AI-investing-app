from datetime import datetime, timezone

from src import finnhub_client


def test_get_candles_normalizes_and_sorts_response(monkeypatch, mock_finnhub_client):
    mock_finnhub_client.stock_candles.return_value = {
        "s": "ok",
        "t": [1_704_153_600, 1_704_067_200],
        "o": [102.0, 100.0],
        "h": [103.0, 101.0],
        "l": [101.0, 99.0],
        "c": [102.5, 100.5],
        "v": [1_200, 1_000],
    }
    monkeypatch.setattr(
        finnhub_client,
        "_rate_limited_call",
        lambda function, *args: function(*args),
    )

    result = finnhub_client.get_candles(
        "AAPL",
        from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_date=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.index.is_monotonic_increasing
    assert result.iloc[0]["Close"] == 100.5
    mock_finnhub_client.stock_candles.assert_called_once()
