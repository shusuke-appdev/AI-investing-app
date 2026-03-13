"""
Data Models for Type Hinting
Using TypedDict for dictionary-based structures to maintain compatibility with existing Streamlit code
while providing better developer experience and validation capabilities.
"""

from typing import TypedDict


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
    market_cap: float | None
    current_price: float | None
    pe_ratio: float | None
    forward_pe: float | None
    beta: float | None

    revenueGrowth: float | None
    earningsGrowth: float | None
    grossMargins: float | None
    operatingMargins: float | None
    currentRatio: float | None
    debtToEquity: float | None
    returnOnAssets: float | None
    pegRatio: float | None
    priceToBook: float | None

    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    target_price: float | None

    share_outstanding: float | None


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
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    rho: float | None
    intrinsicValue: float | None
    timeValue: float | None
