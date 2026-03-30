"""
Data Provider Module (Facade & Dependency Injection)
各データプロバイダーモジュールのFacadeとして機能し、後方互換性を保ちながら
テスト容易性のためのDependency Injection (DI) インターフェースを提供します。
"""

from typing import Protocol, runtime_checkable

import pandas as pd

# 実際の実装モジュールから関数をインポート
from src.market_index_provider import get_market_indices
from src.models import MarketIndex, NewsItem, StockInfo
from src.news_provider import get_company_news_raw, get_stock_news
from src.option_data_provider import get_option_chain
from src.stock_data_provider import (
    get_current_price,
    get_earnings_calendar,
    get_earnings_surprises,
    get_financials_reported,
    get_historical_data,
    get_quote,
    get_stock_info,
)


@runtime_checkable
class DataProviderProtocol(Protocol):
    """データ取得メソッドを定義するProtocol（テスト時のMock用インターフェース）"""
    def get_current_price(self, ticker: str) -> float: ...
    def get_historical_data(self, ticker: str, period: str = "1mo") -> pd.DataFrame: ...
    def get_option_chain(self, ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None: ...
    def get_market_indices(self, market_type: str = "US") -> dict[str, MarketIndex]: ...
    def get_stock_news(self, ticker: str, max_items: int = 10) -> list[NewsItem]: ...
    def get_company_news_raw(self, ticker: str) -> list[dict]: ...
    def get_stock_info(self, ticker: str) -> StockInfo: ...
    def get_quote(self, ticker: str) -> dict | None: ...
    def get_earnings_calendar(self, from_date: str | None = None, to_date: str | None = None) -> list[dict]: ...
    def get_earnings_surprises(self, symbol: str, limit: int = 4) -> list[dict]: ...
    def get_financials_reported(self, symbol: str, freq: str = "quarterly") -> list[dict]: ...

class DefaultDataProvider:
    """実際の実装モジュールを呼び出すデフォルトのプロバイダ"""
    def get_current_price(self, ticker: str) -> float:
        return get_current_price(ticker)

    def get_historical_data(self, ticker: str, period: str = "1mo") -> pd.DataFrame:
        return get_historical_data(ticker, period)

    def get_option_chain(self, ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
        return get_option_chain(ticker)

    def get_market_indices(self, market_type: str = "US") -> dict[str, MarketIndex]:
        return get_market_indices(market_type)

    def get_stock_news(self, ticker: str, max_items: int = 10) -> list[NewsItem]:
        return get_stock_news(ticker, max_items)

    def get_company_news_raw(self, ticker: str) -> list[dict]:
        return get_company_news_raw(ticker)

    def get_stock_info(self, ticker: str) -> StockInfo:
        return get_stock_info(ticker)

    def get_quote(self, ticker: str) -> dict | None:
        return get_quote(ticker)

    def get_earnings_calendar(self, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        return get_earnings_calendar(from_date, to_date)

    def get_earnings_surprises(self, symbol: str, limit: int = 4) -> list[dict]:
        return get_earnings_surprises(symbol, limit)

    def get_financials_reported(self, symbol: str, freq: str = "quarterly") -> list[dict]:
        return get_financials_reported(symbol, freq)

# グローバルなプロバイダインスタンス（DI用）
_global_provider: DataProviderProtocol = DefaultDataProvider()

def set_data_provider(provider: DataProviderProtocol) -> None:
    """テスト時などにMockプロバイダを注入するための関数"""
    global _global_provider
    _global_provider = provider

def get_data_provider() -> DataProviderProtocol:
    """現在のプロバイダを取得する"""
    return _global_provider

class DataProvider:
    """
    Centralized data provider for the application (Facade).
    Provides static methods that delegate to the configured global provider.
    This maintains backwards compatibility with existing code while enabling DI.
    """
    @staticmethod
    def get_current_price(ticker: str) -> float:
        return _global_provider.get_current_price(ticker)

    @staticmethod
    def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
        return _global_provider.get_historical_data(ticker, period)

    @staticmethod
    def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
        return _global_provider.get_option_chain(ticker)

    @staticmethod
    def get_market_indices(market_type: str = "US") -> dict[str, MarketIndex]:
        return _global_provider.get_market_indices(market_type)

    @staticmethod
    def get_stock_news(ticker: str, max_items: int = 10) -> list[NewsItem]:
        return _global_provider.get_stock_news(ticker, max_items)

    @staticmethod
    def get_company_news_raw(ticker: str) -> list[dict]:
        return _global_provider.get_company_news_raw(ticker)

    @staticmethod
    def get_stock_info(ticker: str) -> StockInfo:
        return _global_provider.get_stock_info(ticker)

    @staticmethod
    def get_quote(ticker: str) -> dict | None:
        return _global_provider.get_quote(ticker)

    @staticmethod
    def get_earnings_calendar(from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        return _global_provider.get_earnings_calendar(from_date, to_date)

    @staticmethod
    def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
        return _global_provider.get_earnings_surprises(symbol, limit)

    @staticmethod
    def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
        return _global_provider.get_financials_reported(symbol, freq)
