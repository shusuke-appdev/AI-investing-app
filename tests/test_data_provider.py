from unittest.mock import patch

from src.data_provider import DataProvider


class TestDataProvider:
    @patch("src.stock_data_provider.is_japanese_stock", return_value=False)
    @patch("src.stock_data_provider._extract_openbb_profile")
    def test_get_stock_info_structure(
        self, mock_extract, mock_is_jp
    ):
        """Test if get_stock_info returns correct StockInfo TypedDict structure."""

        # Mock responses
        def side_effect_extract(ticker, info):
             info["name"] = "Test Inc."
             info["ticker"] = "TEST"
             info["market_cap"] = 1000 * 1e6
             info["pe_ratio"] = 20.5
             info["current_price"] = 145.0
             info["beta"] = 1.1

        mock_extract.side_effect = side_effect_extract

        info = DataProvider.get_stock_info("TEST")

        assert info["ticker"] == "TEST"
        assert info["name"] == "Test Inc."
        assert info["market_cap"] == 1000 * 1e6  # Conversion check
        assert info["pe_ratio"] == 20.5
        assert info["current_price"] == 145.0
        assert "beta" in info  # Check key existence even if None

    @patch("src.news_provider._finnhub_get_company_news")
    @patch("src.news_provider.is_configured", return_value=True)
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

    def test_dependency_injection(self):
        """Test if a custom provider can be injected via set_data_provider."""
        from unittest.mock import MagicMock

        from src.data_provider import DefaultDataProvider, set_data_provider

        try:
            # 1. Provide Mock
            mock_provider = MagicMock()
            mock_provider.get_current_price.return_value = 999.0

            set_data_provider(mock_provider)

            # 2. Call Facade
            price = DataProvider.get_current_price("MOCK")

            # 3. Assert
            assert price == 999.0
            mock_provider.get_current_price.assert_called_once_with("MOCK")
        finally:
            # Cleanup to avoid side-effects on other tests
            set_data_provider(DefaultDataProvider())
