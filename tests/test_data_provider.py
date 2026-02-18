from unittest.mock import patch

from src.data_provider import DataProvider


class TestDataProvider:
    @patch("src.data_provider.get_company_profile")
    @patch("src.data_provider.get_basic_financials")
    @patch("src.data_provider._finnhub_get_quote")
    @patch("src.data_provider.is_configured", return_value=True)
    def test_get_stock_info_structure(
        self, mock_is_conf, mock_quote, mock_basic, mock_profile
    ):
        """Test if get_stock_info returns correct StockInfo TypedDict structure."""

        # Mock responses
        mock_profile.return_value = {
            "name": "Test Inc.",
            "ticker": "TEST",
            "finnhubIndustry": "Tech",
            "marketCapitalization": 1000,
            "shareOutstanding": 50,
        }
        mock_basic.return_value = {"metric": {"peTTM": 20.5, "52WeekHigh": 150}}
        mock_quote.return_value = {"c": 145.0}

        info = DataProvider.get_stock_info("TEST")

        assert info["ticker"] == "TEST"
        assert info["name"] == "Test Inc."
        assert info["market_cap"] == 1000 * 1e6  # Conversion check
        assert info["pe_ratio"] == 20.5
        assert info["current_price"] == 145.0
        assert "beta" in info  # Check key existence even if None

    @patch("src.data_provider._finnhub_get_company_news")
    @patch("src.data_provider.is_configured", return_value=True)
    def test_get_stock_news_structure(self, mock_is_conf, mock_news):
        """Test news item structure."""
        mock_news.return_value = [
            {
                "headline": "Big News",
                "source": "WSJ",
                "url": "http://...",
                "datetime": 1700000000,
                "summary": "Summary",
            }
        ]

        news = DataProvider.get_stock_news("TEST")
        assert len(news) == 1
        item = news[0]
        assert item["title"] == "Big News"
        assert "published" in item
