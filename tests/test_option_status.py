from src import option_analyst


def test_major_indices_option_status_not_applicable_for_jp():
    result = option_analyst.get_major_indices_option_status("JP")

    assert result["items"] == []
    assert result["status"] == "not_applicable"
    assert result["failed_tickers"] == []
    assert "JP" in result["error_message"]
    assert result["source"] == "not_applicable"


def test_major_indices_option_status_reports_partial_failure(monkeypatch):
    def fake_analysis(ticker, **kwargs):
        if ticker == "SPY":
            return {"ticker": ticker, "data_quality": "available"}
        return None

    monkeypatch.setattr(option_analyst, "analyze_option_sentiment", fake_analysis)

    result = option_analyst.get_major_indices_option_status("US")

    assert result["items"] == [{"ticker": "SPY", "data_quality": "available"}]
    assert result["status"] == "partial"
    assert result["failed_tickers"] == ["QQQ", "IWM"]
    assert "QQQ" in result["error_message"]
    assert result["source"] == "yfinance"


def test_major_indices_option_status_reports_quality_limitations(monkeypatch):
    def fake_analysis(ticker, **kwargs):
        return {
            "ticker": ticker,
            "data_quality": "partial",
            "quality_warnings": [
                "Greeks/Gamma are missing from yfinance; GEX is hidden."
            ],
            "source": "persistent_cache",
            "fetched_at": "2026-05-21T00:00:00+00:00",
            "is_stale": False,
        }

    monkeypatch.setattr(option_analyst, "analyze_option_sentiment", fake_analysis)

    result = option_analyst.get_major_indices_option_status("US")

    assert result["status"] == "partial"
    assert result["failed_tickers"] == []
    assert result["source"] == "persistent_cache"
    assert result["quality_warnings"]


def test_major_indices_option_status_reports_all_failed(monkeypatch):
    monkeypatch.setattr(
        option_analyst, "analyze_option_sentiment", lambda ticker, **kwargs: None
    )

    result = option_analyst.get_major_indices_option_status("US")

    assert result["items"] == []
    assert result["status"] == "failed"
    assert result["failed_tickers"] == ["SPY", "QQQ", "IWM"]
