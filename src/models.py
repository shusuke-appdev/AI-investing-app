"""
Data Models for Type Hinting
Using TypedDict for dictionary-based structures to maintain compatibility with existing Streamlit code
while providing better developer experience and validation capabilities.
"""
from typing import TypedDict, Optional, List, Dict, Any

class StockInfo(TypedDict, total=False):
    """Basic company information and key metrics."""
    name: str
    ticker: str
    sector: str
    industry: str
    summary: str
    website: str
    logo: str
    city: str
    state: str
    country: str
    employees: int
    exchange: str
    
    # Financial Metrics
    market_cap: Optional[float]
    current_price: Optional[float]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    beta: Optional[float]
    
    revenueGrowth: Optional[float]
    earningsGrowth: Optional[float]
    grossMargins: Optional[float]
    operatingMargins: Optional[float]
    currentRatio: Optional[float]
    debtToEquity: Optional[float]
    returnOnAssets: Optional[float]
    pegRatio: Optional[float]
    priceToBook: Optional[float]
    
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    target_price: Optional[float]
    
    share_outstanding: Optional[float]

class NewsItem(TypedDict):
    """News article structure."""
    title: str
    publisher: str
    link: str
    published: str
    summary: str

class MarketIndex(TypedDict):
    """Market index or asset data."""
    price: float
    change: float
    ticker: str

class OptionData(TypedDict, total=False):
    """Option chain summary data."""
    contractName: str
    strike: float
    lastPrice: float
    bid: float
    ask: float
    change: float
    changePercent: float
    volume: int
    openInterest: int
    impliedVolatility: float
    inTheMoney: str
    expiration: str
    # Greeks (Finnhub APIから直接取得)
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]
    intrinsicValue: Optional[float]
    timeValue: Optional[float]
