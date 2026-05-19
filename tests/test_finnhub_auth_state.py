from src import finnhub_client


def test_invalid_finnhub_key_is_suppressed_for_process(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "bad-key")
    monkeypatch.setattr(finnhub_client, "_disabled_api_key", None)

    assert finnhub_client.is_configured() is True

    finnhub_client._mark_current_api_key_invalid()

    assert finnhub_client.is_configured() is False
