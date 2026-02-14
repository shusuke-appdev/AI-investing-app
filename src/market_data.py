"""
市場データ取得モジュール
(Facade for src.data_provider.DataProvider)
"""
import streamlit as st
import pandas as pd
from typing import Optional, Dict, List
from src.data_provider import DataProvider
from src.constants import MARKET_US

@st.cache_data(ttl=300) # 5分キャッシュ
def get_stock_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """
    指定銘柄の株価データを取得します。
    Delegates to DataProvider.
    """
    return DataProvider.get_historical_data(ticker, period)

def get_option_chain(ticker: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """
    オプションチェーンデータを取得します。
    Delegates to DataProvider.
    """
    return DataProvider.get_option_chain(ticker)

@st.cache_data(ttl=300)
def get_market_indices(market_type: str = MARKET_US) -> Dict[str, dict]:
    """
    主要市場指数のデータを取得。
    Delegates to DataProvider.
    """
    return DataProvider.get_market_indices(market_type)

def get_stock_news(ticker: str, max_items: int = 10) -> List[dict]:
    """
    銘柄ニュース取得。
    Delegates to DataProvider.
    """
    return DataProvider.get_stock_news(ticker, max_items)

@st.cache_data(ttl=86400) # 1日キャッシュ
def get_stock_info(ticker: str) -> dict:
    """
    企業概要を取得します。
    Delegates to DataProvider.
    """
    return DataProvider.get_stock_info(ticker)



