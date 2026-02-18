from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_finnhub_client():
    """Mock Finnhub client for all tests."""
    with patch("src.finnhub_client._get_client") as mock_get:
        mock_client = MagicMock()
        # Mock common Finnhub methods
        mock_client.company_profile2.return_value = {
            "name": "Test Company",
            "ticker": "TEST",
            "finnhubIndustry": "Technology",
            "currency": "USD",
        }
        mock_client.quote.return_value = {
            "c": 150.0,
            "d": 1.5,
            "dp": 1.0,
            "h": 155.0,
            "l": 145.0,
            "o": 148.0,
            "pc": 148.5,
            "t": 1600000000,
        }
        mock_client.company_news.return_value = [
            {
                "category": "company",
                "datetime": 1600000000,
                "headline": "Test News Headline",
                "id": 12345,
                "image": "https://example.com/image.jpg",
                "related": "TEST",
                "source": "Test Source",
                "summary": "Test news summary.",
                "url": "https://example.com/news",
            }
        ]
        mock_client.recommendation_trends.return_value = [
            {
                "buy": 10,
                "hold": 5,
                "period": "2023-01-01",
                "sell": 2,
                "strongBuy": 8,
                "strongSell": 0,
                "symbol": "TEST",
            }
        ]

        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def mock_gemini_client():
    """Mock Gemini client for all tests."""
    with patch("src.advisor.llm.genai.GenerativeModel") as mock_model_class:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value.text = "Mocked advice response."
        mock_model_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_supabase_client():
    """Mock Supabase client for all tests."""
    with patch("src.supabase_client.get_supabase_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def mock_settings_storage():
    """Mock settings storage to force local storage."""
    with patch("src.settings_storage.get_storage_type") as mock_get:
        mock_get.return_value = "local"
        yield mock_get
