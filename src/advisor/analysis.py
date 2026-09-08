from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.market_data import (
    get_market_indices,
    get_stock_data,
)


def get_macro_context() -> dict:
    """マクロ経済・市場環境のコンテキストを取得"""
    market_data = get_market_indices()

    context = {
        "indices": {},
        "rates": {},
        "commodities": {},
        "crypto": {},
        "fx": {},
    }

    # Indices
    for key in ["S&P 500", "Nasdaq", "Nikkei 225"]:
        if key in market_data:
            context["indices"][key] = market_data[key]

    # Rates
    for key in ["US 2Y", "US 10Y", "US 30Y"]:
        if key in market_data:
            context["rates"][key] = market_data[key]

    # Commodities
    for key in ["WTI Oil", "Gold", "Silver"]:
        if key in market_data:
            context["commodities"][key] = market_data[key]

    # Crypto
    for key in ["Bitcoin", "Ethereum"]:
        if key in market_data:
            context["crypto"][key] = market_data[key]

    # FX
    if "USD/JPY" in market_data:
        context["fx"]["USD/JPY"] = market_data["USD/JPY"]

    return context


def get_sector_performance() -> dict:
    """セクター別パフォーマンスを、上限付き並列取得で計算する。"""
    sector_etfs = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Communication Services": "XLC",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Consumer Staples": "XLP",
    }

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(_sector_performance_item, sector, etf): sector
            for sector, etf in sector_etfs.items()
        }
        for future in as_completed(future_map):
            sector = future_map[future]
            try:
                item = future.result()
            except Exception:
                continue
            if item is not None:
                results[sector] = item
    return results


def _sector_performance_item(sector: str, etf: str) -> dict[str, Any] | None:
    """1セクター分を取得し、取得不能ならNoneを返す。"""

    try:
        df = get_stock_data(etf, "1mo")
        if not df.empty and len(df) >= 2:
            start = float(df["Close"].iloc[0])
            end = float(df["Close"].iloc[-1])
            if start == 0:
                return None
            return {
                "etf": etf,
                "change_1m": ((end - start) / start) * 100,
            }
    except Exception:
        return None
    return None
