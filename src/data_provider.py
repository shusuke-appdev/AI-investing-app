"""
Data Provider Module (Facade)
各データプロバイダーモジュールのFacadeとして機能し、後方互換性を保ちます。
実際の実装は src/stock_data_provider.py, src/market_index_provider.py 等に分割されています。
"""

import pandas as pd

from src.market_index_provider import get_market_indices
from src.models import MarketIndex, NewsItem, StockInfo
from src.news_provider import get_company_news_raw, get_stock_news
from src.option_data_provider import get_option_chain

# 実際の実装モジュールから関数をインポート
from src.stock_data_provider import (
    _extract_finnhub_profile,
    _extract_yfinance_profile,
    get_current_price,
    get_earnings_calendar,
    get_earnings_surprises,
    get_financials_reported,
    get_historical_data,
    get_quote,
    get_stock_info,
)


class DataProvider:
    """
    Centralized data provider for the application (Facade).
    Provides static methods that delegate to specific data provider modules.
    """

    @staticmethod
    def _get_yf_session():
        from src.utils.http_session import get_yf_session

        return get_yf_session()

    @staticmethod
    def get_current_price(ticker: str) -> float:
        return get_current_price(ticker)

    @staticmethod
    def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
        return get_historical_data(ticker, period)

    @staticmethod
    def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
        return get_option_chain(ticker)

    @staticmethod
    def get_market_indices(market_type: str = "US") -> dict[str, MarketIndex]:
        return get_market_indices(market_type)

    @staticmethod
    def get_stock_news(ticker: str, max_items: int = 10) -> list[NewsItem]:
        return get_stock_news(ticker, max_items)

    @staticmethod
    def get_company_news_raw(ticker: str) -> list[dict]:
        return get_company_news_raw(ticker)

    @staticmethod
    def _extract_finnhub_profile(ticker: str, info: StockInfo) -> None:
        return _extract_finnhub_profile(ticker, info)

    @staticmethod
    def _extract_yfinance_profile(ticker: str, info: StockInfo) -> None:
        return _extract_yfinance_profile(ticker, info)

    @staticmethod
    def get_stock_info(ticker: str) -> StockInfo:
        return get_stock_info(ticker)

    @staticmethod
    def get_quote(ticker: str) -> dict | None:
        return get_quote(ticker)

    @staticmethod
    def get_earnings_calendar(
        from_date: str | None = None, to_date: str | None = None
    ) -> list[dict]:
        return get_earnings_calendar(from_date, to_date)

    @staticmethod
    def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
        return get_earnings_surprises(symbol, limit)

    @staticmethod
    def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
        return get_financials_reported(symbol, freq)
