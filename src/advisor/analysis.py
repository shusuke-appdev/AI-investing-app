from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.market_data import (
    get_market_indices,
    get_stock_data,
    get_stock_info,
    get_stock_news,
)
from src.services.analysis_context import ProvenanceItem, ProvenanceKind
from src.stock_data_provider import get_quote_with_status

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
        from src.themes_config import JP_THEMES, THEMES
    except ImportError:
        return {}

    theme_values = {}
    total_value = sum(h.get("value_jpy") or 0 for h in holdings)

    for h in holdings:
        ticker = h["ticker"]
        value = h.get("value_jpy") or 0

        themes = JP_THEMES if ticker.endswith(".T") else THEMES
        for theme_name, theme_tickers in themes.items():
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
    holdings: list[PortfolioHolding],
    market_context: Any | None = None,
) -> dict:
    """Analyze holdings in native currency and aggregate only after JPY conversion."""

    results: list[dict[str, Any]] = []
    excluded_holdings: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(holdings)))) as executor:
        future_map = {
            executor.submit(_analyze_portfolio_holding, holding): holding
            for holding in holdings
        }
        for future in as_completed(future_map):
            holding = future_map[future]
            try:
                item = future.result()
            except Exception as exc:
                excluded_holdings.append(
                    {
                        "ticker": holding.ticker,
                        "reason": f"分析処理に失敗しました: {exc}",
                    }
                )
                continue
            if item is None:
                excluded_holdings.append(
                    {
                        "ticker": holding.ticker,
                        "reason": "現在価格を取得できないため分析対象から除外しました。",
                    }
                )
                continue
            results.append(item)

    results.sort(key=lambda item: item["ticker"])
    currencies = {str(item["native_currency"]) for item in results}
    usd_jpy, fx_source, fx_warning = _resolve_usd_jpy(market_context, currencies)
    currency_subtotals: dict[str, float] = {}
    conversion_complete = True
    for item in results:
        currency = str(item["native_currency"])
        native_value = float(item["native_value"])
        currency_subtotals[currency] = (
            currency_subtotals.get(currency, 0.0) + native_value
        )
        if currency == "JPY":
            item["fx_rate_to_jpy"] = 1.0
            item["value_jpy"] = native_value
        elif currency == "USD" and usd_jpy is not None:
            item["fx_rate_to_jpy"] = usd_jpy
            item["value_jpy"] = native_value * usd_jpy
        else:
            item["fx_rate_to_jpy"] = None
            item["value_jpy"] = None
            conversion_complete = False

    total_value_jpy = (
        sum(float(item["value_jpy"]) for item in results)
        if results and conversion_complete
        else None
    )
    for item in results:
        weight = (
            float(item["value_jpy"]) / total_value_jpy * 100
            if total_value_jpy and item["value_jpy"] is not None
            else None
        )
        item["weight_pct"] = weight
        item["weight"] = weight

    sector_exposure = _group_exposure(results, "sector", total_value_jpy)
    theme_exposure = get_theme_exposure_analysis(results) if total_value_jpy else {}
    concentration = _concentration_summary(results)
    valuation_status = (
        "converted"
        if total_value_jpy is not None
        else "currency_subtotals_only"
        if results
        else "unavailable"
    )
    warnings = [f"{item['ticker']}: {item['reason']}" for item in excluded_holdings]
    if fx_warning:
        warnings.append(fx_warning)

    return {
        "holdings": results,
        "base_currency": "JPY",
        "total_value_jpy": total_value_jpy,
        "total_value": total_value_jpy,
        "currency_subtotals": {
            key: round(value, 2) for key, value in sorted(currency_subtotals.items())
        },
        "valuation_status": valuation_status,
        "usd_jpy": usd_jpy,
        "fx_source": fx_source,
        "num_holdings": len(results),
        "sector_exposure": sector_exposure,
        "theme_exposure": theme_exposure,
        "concentration": concentration,
        "excluded_holdings": excluded_holdings,
        "quality_warnings": warnings,
        "provenance": [
            ProvenanceItem(
                item_id="portfolio.current_prices",
                label="ポートフォリオ現在価格",
                kind=ProvenanceKind.DIRECT if results else ProvenanceKind.UNAVAILABLE,
                source="market_data providers + USD/JPY",
                method=(
                    "各銘柄を現地通貨で評価し、USD/JPYが確認できた場合だけ円換算して"
                    "総額と構成比を計算。"
                ),
                limitation=(
                    "為替未取得の通貨があるため通貨別小計のみ表示。"
                    if valuation_status == "currency_subtotals_only"
                    else f"価格未取得により {len(excluded_holdings)} 銘柄を除外。"
                    if excluded_holdings
                    else ""
                ),
                risk_level="high" if excluded_holdings else "low",
            ).to_dict(),
            ProvenanceItem(
                item_id="portfolio.ai_advice",
                label="AIポートフォリオ助言",
                kind=ProvenanceKind.MODEL_OUTPUT,
                source="Gemini",
                method="取得済みポートフォリオ分析結果を基に生成。",
                limitation="生成AIの助言であり、売買判断を保証しない。",
                risk_level="high",
            ).to_dict(),
        ],
    }


def _analyze_portfolio_holding(holding: PortfolioHolding) -> dict[str, Any] | None:
    info = get_stock_info(holding.ticker)
    history = get_stock_data(holding.ticker, "1y")
    technical = analyze_technical(holding.ticker, "1y", history)
    current_price = info.get("current_price")
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        return None
    currency = str(info.get("currency") or "").upper()
    if not currency:
        currency = "JPY" if holding.ticker.endswith(".T") else "USD"
    native_value = float(current_price) * holding.shares
    pnl_pct = (
        (float(current_price) - holding.avg_cost) / holding.avg_cost * 100
        if holding.avg_cost
        else None
    )
    return {
        "ticker": holding.ticker,
        "name": info.get("name", holding.ticker),
        "shares": holding.shares,
        "current_price": float(current_price),
        "native_currency": currency,
        "native_value": native_value,
        "value": native_value,
        "avg_cost": holding.avg_cost,
        "pnl_pct": pnl_pct,
        "technical": technical,
        "sector": info.get("sector", "不明"),
    }


def _resolve_usd_jpy(
    market_context: Any | None, currencies: set[str]
) -> tuple[float | None, str, str]:
    if "USD" not in currencies:
        return None, "not_required", ""
    context = (
        market_context.to_dict()
        if hasattr(market_context, "to_dict")
        else market_context
        if isinstance(market_context, dict)
        else {}
    )
    market_data = context.get("market_data", {}) if context else {}
    item = market_data.get("USD/JPY") or market_data.get("JPY=X") or {}
    rate = item.get("price") if isinstance(item, dict) else None
    if isinstance(rate, (int, float)) and rate > 0:
        return float(rate), "shared_market_context", ""
    quote = get_quote_with_status("JPY=X")
    quote_rate = (quote.data or {}).get("c") if quote.data else None
    if isinstance(quote_rate, (int, float)) and quote_rate > 0:
        return float(quote_rate), quote.source or "yfinance", ""
    reason = quote.error or "; ".join(quote.warnings) or "USD/JPYを取得できません。"
    return (
        None,
        quote.source or "yfinance",
        f"USD/JPY未取得のため円換算総額・構成比は表示しません: {reason}",
    )


def _group_exposure(
    holdings: list[dict[str, Any]], key: str, total_value_jpy: float | None
) -> dict[str, dict[str, float]]:
    if not total_value_jpy:
        return {}
    grouped: dict[str, float] = {}
    for item in holdings:
        label = str(item.get(key) or "不明")
        grouped[label] = grouped.get(label, 0.0) + float(item.get("value_jpy") or 0)
    return {
        label: {"value_jpy": value, "weight": value / total_value_jpy * 100}
        for label, value in sorted(
            grouped.items(), key=lambda pair: pair[1], reverse=True
        )
    }


def _concentration_summary(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        (item for item in holdings if item.get("weight_pct") is not None),
        key=lambda item: float(item["weight_pct"]),
        reverse=True,
    )
    weights = [float(item["weight_pct"]) for item in ranked]
    return {
        "top_holdings": [
            {"ticker": item["ticker"], "weight": item["weight_pct"]}
            for item in ranked[:5]
        ],
        "top1_pct": weights[0] if weights else None,
        "top3_pct": sum(weights[:3]) if weights else None,
        "hhi": sum((weight / 100) ** 2 for weight in weights) if weights else None,
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
