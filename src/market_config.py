"""
市場設定モジュール
米国/日本市場の設定を中央管理します。
"""

from enum import Enum
from typing import TypedDict


class MarketType(str, Enum):
    """市場タイプ"""

    US = "US"
    JP = "JP"


class MarketSettings(TypedDict):
    """市場設定の型定義"""

    name: str
    currency: str
    currency_symbol: str
    news_language: str
    news_country: str
    sample_tickers: list[str]
    default_ticker: str
    options_available: bool
    indices: dict[str, str]
    treasuries: dict[str, str]
    volatility: dict[str, str]
    sectors: dict[str, str]
    commodities: dict[str, str]
    crypto: dict[str, str]
    forex: dict[str, str]


SHARED_INDICES: dict[str, str] = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "Dow 30": "^DJI",
    "Russell 2000": "^RUT",
    "TOPIX": "1306.T",
    "日経平均": "^N225",
    "Euro 600": "^STOXX",
    "Hang Seng": "^HSI",
    "Sensex": "^BSESN",
    "KOSPI": "^KS11",
}

SHARED_TREASURIES: dict[str, str] = {
    "US 10Y Yield": "^TNX",
    "US 30Y Yield": "^TYX",
}

SHARED_VOLATILITY: dict[str, str] = {"VIX": "^VIX"}

SHARED_COMMODITIES: dict[str, str] = {
    "WTI Oil": "CL=F",
    "Gold": "GC=F",
}

SHARED_CRYPTO: dict[str, str] = {
    "Bitcoin": "BTC-USD",
}

SHARED_FOREX: dict[str, str] = {
    "USD/JPY": "JPY=X",
    "EUR/USD": "EURUSD=X",
}

US_SECTORS: dict[str, str] = {
    "情報技術": "XLK",
    "ヘルスケア": "XLV",
    "金融": "XLF",
    "一般消費財": "XLY",
    "通信": "XLC",
    "資本財": "XLI",
    "生活必需品": "XLP",
    "エネルギー": "XLE",
    "公益": "XLU",
    "不動産": "XLRE",
    "素材": "XLB",
}

JP_TOPIX17_SECTORS: dict[str, str] = {
    "TOPIX-17 食品": "1617.T",
    "TOPIX-17 エネルギー資源": "1618.T",
    "TOPIX-17 建設・資材": "1619.T",
    "TOPIX-17 素材・化学": "1620.T",
    "TOPIX-17 医薬品": "1621.T",
    "TOPIX-17 自動車・輸送機": "1622.T",
    "TOPIX-17 鉄鋼・非鉄": "1623.T",
    "TOPIX-17 機械": "1624.T",
    "TOPIX-17 電機・精密": "1625.T",
    "TOPIX-17 情報通信・サービスその他": "1626.T",
    "TOPIX-17 電力・ガス": "1627.T",
    "TOPIX-17 運輸・物流": "1628.T",
    "TOPIX-17 商社・卸売": "1629.T",
    "TOPIX-17 小売": "1630.T",
    "TOPIX-17 銀行": "1631.T",
    "TOPIX-17 金融(除く銀行)": "1632.T",
    "TOPIX-17 不動産": "1633.T",
}


# 米国市場設定
US_CONFIG: MarketSettings = {
    "name": "米国株",
    "currency": "USD",
    "currency_symbol": "$",
    "news_language": "en",
    "news_country": "US",
    "sample_tickers": ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"],
    "default_ticker": "AAPL",
    "options_available": True,
    "indices": SHARED_INDICES,
    "treasuries": SHARED_TREASURIES,
    "volatility": SHARED_VOLATILITY,
    "sectors": US_SECTORS,
    "commodities": SHARED_COMMODITIES,
    "crypto": SHARED_CRYPTO,
    "forex": SHARED_FOREX,
}

# 日本市場設定
JP_CONFIG: MarketSettings = {
    "name": "日本株",
    "currency": "JPY",
    "currency_symbol": "¥",
    "news_language": "ja",
    "news_country": "JP",
    "sample_tickers": ["7203.T", "6758.T", "9984.T", "8306.T", "6861.T"],
    "default_ticker": "7203.T",  # トヨタ
    "options_available": False,  # yfinanceでは日本株オプション取得不可
    "indices": SHARED_INDICES,
    "treasuries": SHARED_TREASURIES,
    "volatility": SHARED_VOLATILITY,
    "sectors": JP_TOPIX17_SECTORS,
    "commodities": SHARED_COMMODITIES,
    "crypto": SHARED_CRYPTO,
    "forex": SHARED_FOREX,
}

# 設定マップ
MARKET_CONFIGS: dict[str, MarketSettings] = {
    MarketType.US.value: US_CONFIG,
    MarketType.JP.value: JP_CONFIG,
}


def get_market_config(market_type: str = "US") -> MarketSettings:
    """
    指定された市場タイプの設定を取得します。

    Args:
        market_type: "US" または "JP"

    Returns:
        市場設定の辞書
    """
    return MARKET_CONFIGS.get(market_type, US_CONFIG)


def format_price(price: float, market_type: str = "US", decimals: int = 2) -> str:
    """
    市場に応じた通貨フォーマットで価格を表示します。

    Args:
        price: 価格
        market_type: "US" または "JP"
        decimals: 小数点以下桁数

    Returns:
        フォーマット済み価格文字列
    """
    config = get_market_config(market_type)
    symbol = config["currency_symbol"]

    if market_type == "JP":
        # 日本円は通常整数表示
        return f"{symbol}{price:,.0f}"
    return f"{symbol}{price:,.{decimals}f}"
