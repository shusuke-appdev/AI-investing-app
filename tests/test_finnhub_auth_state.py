from src import finnhub_client


def test_invalid_finnhub_key_is_suppressed_for_process(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "bad-key")
    monkeypatch.setattr(finnhub_client, "_disabled_api_key", None)
    monkeypatch.setattr(finnhub_client, "_disabled_reason", "")

    assert finnhub_client.is_configured() is True

    finnhub_client._mark_current_api_key_invalid("invalid test key")

    assert finnhub_client.is_configured() is False
    assert finnhub_client.get_auth_status() == "invalid"
    assert finnhub_client.get_auth_error_message() == "invalid test key"


def test_invalid_finnhub_key_short_circuits_stock_news(monkeypatch):
    from src import news_provider

    news_provider.get_stock_news.clear_cache()
    news_provider.get_stock_news_with_status.clear_cache()
    monkeypatch.setenv("FINNHUB_API_KEY", "bad-key")
    monkeypatch.setattr(finnhub_client, "_disabled_api_key", "bad-key")
    monkeypatch.setattr(finnhub_client, "_disabled_reason", "invalid test key")
    monkeypatch.setattr(
        news_provider,
        "_finnhub_get_company_news",
        lambda ticker: (_ for _ in ()).throw(AssertionError("Finnhub was called")),
    )

    result = news_provider.get_stock_news_with_status("AAPL", 5)

    assert result["items"] == []
    assert result["source_status"] == "invalid"
    assert result["error_reason"] == "invalid test key"
