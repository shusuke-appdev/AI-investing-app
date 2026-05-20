"""Backward-compatible market data facade over DataProvider."""

from typing import Any

import pandas as pd

from src.constants import MARKET_US
from src.data_provider import DataProvider


def get_stock_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """Return historical stock data."""

    return DataProvider.get_historical_data(ticker, period)


def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Return option chain data."""

    return DataProvider.get_option_chain(ticker)


def get_market_indices(market_type: str = MARKET_US) -> dict[str, Any]:
    """Return configured market index and cross-asset data."""

    return DataProvider.get_market_indices(market_type)


def get_stock_news(ticker: str, max_items: int = 10) -> list[Any]:
    """Return stock news items."""

    return DataProvider.get_stock_news(ticker, max_items)


def get_stock_news_with_status(ticker: str, max_items: int = 10) -> dict[str, Any]:
    """Return stock news plus provider status metadata."""

    return DataProvider.get_stock_news_with_status(ticker, max_items)


def get_stock_info(
    ticker: str,
    *,
    translate_summary: bool = True,
    include_summary: bool = True,
) -> dict[str, Any]:
    """Return company profile and metrics."""

    return DataProvider.get_stock_info(
        ticker,
        translate_summary=translate_summary,
        include_summary=include_summary,
    )
