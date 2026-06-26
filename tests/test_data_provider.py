from unittest.mock import patch

import pandas as pd

from src.data_provider import DataProvider
from src.persistent_cache import PersistentJsonCache


class FakeYFinanceTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.fast_info = {
            "lastPrice": 145.0,
            "dayHigh": 150.0,
            "dayLow": 140.0,
            "open": 142.0,
            "previousClose": 141.0,
            "marketCap": 1_000_000_000,
            "yearHigh": 180.0,
            "yearLow": 100.0,
        }
        self.info = {
            "longName": "Test Inc.",
            "sector": "Technology",
            "industry": "Software",
            "longBusinessSummary": "English business summary.",
            "website": "https://example.com",
            "country": "US",
            "fullTimeEmployees": 1234,
            "marketCap": 1_000_000_000,
            "revenueGrowth": 0.12,
            "earningsGrowth": 0.08,
            "grossMargins": 0.55,
            "operatingMargins": 0.25,
            "currentRatio": 1.5,
            "debtToEquity": 20.0,
            "returnOnAssets": 0.1,
            "returnOnEquity": 0.2,
            "trailingPE": 20.5,
            "forwardPE": 18.0,
            "priceToBook": 5.0,
            "beta": 1.1,
            "targetMeanPrice": 175.0,
            "sharesOutstanding": 10_000_000,
        }

    def history(self, period):
        return pd.DataFrame(
            {
                "open": [140.0, 142.0],
                "high": [146.0, 150.0],
                "low": [138.0, 140.0],
                "close": [141.0, 145.0],
                "volume": [1_000_000, 1_100_000],
            },
            index=pd.date_range("2026-01-01", periods=2),
        )


class FastInfoOnlyTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.fast_info = {
            "lastPrice": 145.0,
            "previousClose": 141.0,
            "marketCap": 1_000_000_000,
        }
        self.info = {}

    def history(self, period):
        return pd.DataFrame(
            {
                "open": [140.0, 142.0],
                "high": [146.0, 150.0],
                "low": [138.0, 140.0],
                "close": [141.0, 145.0],
                "volume": [1_000_000, 1_100_000],
            },
            index=pd.date_range("2026-01-01", periods=2),
        )


class TestDataProvider:
    @patch("src.stock_data_provider.is_japanese_stock", return_value=False)
    def test_get_stock_info_structure(self, mock_is_jp, monkeypatch):
        """Test if get_stock_info returns correct StockInfo TypedDict structure."""
        from src import stock_data_provider

        stock_data_provider.get_stock_info.clear_cache()
        monkeypatch.setattr(stock_data_provider.yf, "Ticker", FakeYFinanceTicker)

        info = DataProvider.get_stock_info("TEST", translate_summary=False)

        assert info["ticker"] == "TEST"
        assert info["name"] == "Test Inc."
        assert info["market_cap"] == 1000 * 1e6  # Conversion check
        assert info["pe_ratio"] == 20.5
        assert info["current_price"] == 145.0
        assert "beta" in info  # Check key existence even if None

    @patch("src.stock_data_provider.is_japanese_stock", return_value=False)
    def test_get_stock_info_uses_fast_info_when_profile_is_unavailable(
        self, mock_is_jp, monkeypatch, tmp_path
    ):
        from src import stock_data_provider

        stock_data_provider.get_stock_info.clear_cache()
        monkeypatch.setattr(stock_data_provider.yf, "Ticker", FastInfoOnlyTicker)
        monkeypatch.setattr(
            stock_data_provider,
            "repo_state_cache",
            lambda namespace: PersistentJsonCache(tmp_path, namespace),
        )

        info = DataProvider.get_stock_info("TEST", translate_summary=False)

        assert info["name"] == "TEST"
        assert info["market_cap"] == 1_000_000_000
        assert info["current_price"] == 145.0

    @patch("src.stock_data_provider.is_japanese_stock", return_value=False)
    def test_yfinance_price_history_quote_and_valuation(self, mock_is_jp, monkeypatch):
        from src import stock_data_provider

        stock_data_provider.get_current_price.clear_cache()
        stock_data_provider.get_historical_data.clear_cache()
        stock_data_provider.get_quote.clear_cache()
        stock_data_provider.get_valuation_metrics.clear_cache()
        monkeypatch.setattr(stock_data_provider.yf, "Ticker", FakeYFinanceTicker)

        assert DataProvider.get_current_price("TEST") == 145.0

        history = DataProvider.get_historical_data("TEST", "1mo")
        assert list(history.columns[:5]) == ["Open", "High", "Low", "Close", "Volume"]
        assert history["Close"].iloc[-1] == 145.0

        quote = DataProvider.get_quote("TEST")
        assert quote == {
            "c": 145.0,
            "d": 4.0,
            "dp": 2.8368794326241136,
            "h": 150.0,
            "l": 140.0,
            "o": 142.0,
            "pc": 141.0,
        }

        metrics = stock_data_provider.get_valuation_metrics("TEST")
        assert metrics == {
            "current_price": 145.0,
            "market_cap": 1_000_000_000,
            "forward_pe": 18.0,
            "pe_ratio": 20.5,
            "dividend_yield": None,
        }

    def test_generic_japanese_price_and_history_do_not_use_delayed_jquants(
        self, monkeypatch, tmp_path
    ):
        from src import stock_data_provider

        stock_data_provider.get_current_price.clear_cache()
        stock_data_provider.get_historical_data.clear_cache()
        monkeypatch.setattr(stock_data_provider.yf, "Ticker", FakeYFinanceTicker)
        monkeypatch.setattr(
            stock_data_provider,
            "repo_state_cache",
            lambda namespace: PersistentJsonCache(tmp_path, namespace),
        )
        monkeypatch.setattr(
            stock_data_provider.jquants_client,
            "get_current_price",
            lambda ticker: (_ for _ in ()).throw(
                AssertionError("delayed J-Quants price was used")
            ),
        )
        monkeypatch.setattr(
            stock_data_provider.jquants_client,
            "get_daily_quotes",
            lambda ticker, period: (_ for _ in ()).throw(
                AssertionError("delayed J-Quants history was used")
            ),
        )

        assert stock_data_provider.get_current_price("7203.T") == 145.0
        history = stock_data_provider.get_historical_data("7203.T", "1mo")
        assert history["Close"].iloc[-1] == 145.0

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

    def test_market_data_option_facade_forwards_cache_only(self):
        from src import market_data
        from src.data_provider import DefaultDataProvider, set_data_provider

        calls = []

        class FakeProvider:
            def get_option_chain(
                self,
                ticker,
                *,
                allow_marketdata=False,
                cache_only=False,
                target_dte=None,
                min_dte=0,
            ):
                calls.append(
                    (ticker, allow_marketdata, cache_only, target_dte, min_dte)
                )
                return None

        try:
            set_data_provider(FakeProvider())

            assert (
                market_data.get_option_chain(
                    "SPY", allow_marketdata=True, cache_only=True
                )
                is None
            )
        finally:
            set_data_provider(DefaultDataProvider())

            assert calls == [("SPY", True, True, None, 0)]
