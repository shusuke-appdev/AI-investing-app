from src import option_analyst


def test_major_indices_option_status_not_applicable_for_jp():
    result = option_analyst.get_major_indices_option_status("JP")

    assert result["items"] == []
    assert result["status"] == "not_applicable"
    assert result["failed_tickers"] == []
    assert "JP" in result["error_message"]


def test_major_indices_option_status_reports_partial_failure(monkeypatch):
    def fake_analysis(ticker):
        if ticker == "SPY":
            return {"ticker": ticker}
        return None

    monkeypatch.setattr(option_analyst, "analyze_option_sentiment", fake_analysis)
    monkeypatch.setattr(option_analyst.time, "sleep", lambda seconds: None)

    result = option_analyst.get_major_indices_option_status("US")

    assert result["items"] == [{"ticker": "SPY"}]
    assert result["status"] == "partial"
    assert result["failed_tickers"] == ["QQQ", "IWM"]
    assert "QQQ" in result["error_message"]


def test_major_indices_option_status_reports_all_failed(monkeypatch):
    monkeypatch.setattr(option_analyst, "analyze_option_sentiment", lambda ticker: None)
    monkeypatch.setattr(option_analyst.time, "sleep", lambda seconds: None)

    result = option_analyst.get_major_indices_option_status("US")

    assert result["items"] == []
    assert result["status"] == "failed"
    assert result["failed_tickers"] == ["SPY", "QQQ", "IWM"]
