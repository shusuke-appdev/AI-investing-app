from typing import Optional

from src.market_data import (
    get_market_indices,
    get_stock_data,
    get_stock_info,
    get_stock_news,
)

from .models import PortfolioHolding
from .technical import analyze_technical


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
    for key in ["WTI Oil", "Gold", "Copper"]:
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
    """セクター別パフォーマンスを取得"""
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

    results = {}
    for sector, etf in sector_etfs.items():
        try:
            df = get_stock_data(etf, "1mo")
            if not df.empty and len(df) >= 2:
                start = df["Close"].iloc[0]
                end = df["Close"].iloc[-1]
                change = ((end - start) / start) * 100
                results[sector] = {
                    "etf": etf,
                    "change_1m": change,
                }
        except Exception:
            continue

    return results


def get_theme_exposure_analysis(holdings: list[dict]) -> dict:
    """ポートフォリオのテーマ別エクスポージャーを分析"""
    try:
        from themes_config import THEMES
    except ImportError:
        return {}

    theme_values = {}
    total_value = sum(h.get("value", 0) for h in holdings)

    for h in holdings:
        ticker = h["ticker"]
        value = h.get("value", 0)

        for theme_name, theme_tickers in THEMES.items():
            if ticker in theme_tickers:
                if theme_name not in theme_values:
                    theme_values[theme_name] = 0
                theme_values[theme_name] += value

    if total_value > 0:
        return {
            theme: {"value": val, "weight": (val / total_value) * 100}
            for theme, val in sorted(
                theme_values.items(), key=lambda x: x[1], reverse=True
            )[:10]
        }

    return {}


def get_holdings_news(holdings: list[dict], max_per_stock: int = 3) -> list[dict]:
    """保有銘柄に関連するニュースを取得"""
    all_news = []

    for h in holdings[:5]:  # 上位5銘柄のみ
        ticker = h["ticker"]
        news = get_stock_news(ticker, max_per_stock)
        for n in news:
            n["ticker"] = ticker
            all_news.append(n)

    return all_news[:15]


def analyze_portfolio(
    holdings: list[PortfolioHolding], market_context: Optional[str] = None
) -> dict:
    """ポートフォリオ全体を分析"""
    results = []
    total_value = 0

    for holding in holdings:
        info = get_stock_info(holding.ticker)
        tech = analyze_technical(holding.ticker)

        current_price = info.get("current_price", 0)
        value = current_price * holding.shares
        total_value += value

        # 損益計算
        if holding.avg_cost:
            pnl_pct = (current_price - holding.avg_cost) / holding.avg_cost * 100
        else:
            pnl_pct = None

        results.append(
            {
                "ticker": holding.ticker,
                "name": info.get("name", holding.ticker),
                "shares": holding.shares,
                "current_price": current_price,
                "value": value,
                "avg_cost": holding.avg_cost,
                "pnl_pct": pnl_pct,
                "technical": tech,
                "sector": info.get("sector", "不明"),
            }
        )

    # ウェイト計算
    for r in results:
        r["weight"] = (r["value"] / total_value * 100) if total_value > 0 else 0

    return {
        "holdings": results,
        "total_value": total_value,
        "num_holdings": len(holdings),
    }


def parse_csv_portfolio(csv_content: str) -> list[PortfolioHolding]:
    """CSVからポートフォリオを読み込み"""
    holdings = []
    lines = csv_content.strip().split("\n")

    for line in lines[1:]:  # ヘッダーをスキップ
        parts = line.strip().split(",")
        if len(parts) >= 2:
            ticker = parts[0].strip().upper()
            try:
                shares = float(parts[1].strip())
                avg_cost = (
                    float(parts[2].strip())
                    if len(parts) > 2 and parts[2].strip()
                    else None
                )
                holdings.append(PortfolioHolding(ticker, shares, avg_cost))
            except ValueError:
                continue

    return holdings
