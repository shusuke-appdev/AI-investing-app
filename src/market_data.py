"""
市場データ取得モジュール
DataProvider への後方互換リエクスポート。

Note: キャッシュは DataProvider 側で管理。
      このモジュールは既存13箇所の import を壊さないための薄いラッパー。
"""

from typing import Dict, List, Optional

import pandas as pd

from src.constants import MARKET_US
from src.data_provider import DataProvider


def get_stock_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """株価データを取得（DataProvider委譲）。"""
    return DataProvider.get_historical_data(ticker, period)


def get_option_chain(ticker: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """オプションチェーンデータを取得（DataProvider委譲）。"""
    return DataProvider.get_option_chain(ticker)


def get_market_indices(market_type: str = MARKET_US) -> Dict[str, dict]:
    """主要市場指数のデータを取得（DataProvider委譲）。"""
    return DataProvider.get_market_indices(market_type)


def get_stock_news(ticker: str, max_items: int = 10) -> List[dict]:
    """銘柄ニュース取得（DataProvider委譲）。"""
    return DataProvider.get_stock_news(ticker, max_items)


def get_stock_info(ticker: str) -> dict:
    """企業概要を取得（DataProvider委譲）。"""
    return DataProvider.get_stock_info(ticker)
