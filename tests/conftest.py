from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import tomllib

# NOTE: 全オプショナルパッケージ (arch, finnhub, edinet_tools) は
# インストール済みのため、sys.modules への MagicMock 注入は行わない。
# 外部APIの呼び出しは、以下の autouse fixture で個別にパッチする。


@pytest.fixture
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


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client for all tests."""
    with patch("src.gemini_client.generate_content") as mock_gen:
        mock_gen.return_value = "Mocked advice response."
        yield mock_gen


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for all tests."""
    with patch("src.supabase_client.get_supabase_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_settings_storage():
    """Mock settings storage to force local storage."""
    with patch("src.settings_storage.get_storage_type") as mock_get:
        mock_get.return_value = "local"
        yield mock_get


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply execution markers from the canonical test inventory."""

    inventory_path = Path(__file__).with_name("test_inventory.toml")
    inventory = tomllib.loads(inventory_path.read_text(encoding="utf-8"))
    metadata = {
        filename: suite for suite in inventory["suite"] for filename in suite["files"]
    }
    for item in items:
        filename = Path(str(item.fspath)).name
        suite = metadata.get(filename)
        if not suite:
            continue
        nature = suite["nature"]
        if nature in {"contract", "integration"}:
            item.add_marker(getattr(pytest.mark, nature))
        if suite["profile"] == "slow":
            item.add_marker(pytest.mark.slow)
