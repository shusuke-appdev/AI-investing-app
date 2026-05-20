"""Stock data provider for prices, history, profile, and financial data."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

os.environ["OPENBB_AUTO_BUILD"] = "False"

try:
    from openbb import obb
except ImportError:
    obb = None

from src import jquants_client
from src.cache import ttl_cache
from src.constants import CACHE_TTL_DAILY, CACHE_TTL_MEDIUM, CACHE_TTL_SHORT
from src.edinet_client import get_company_finance
from src.log_config import get_logger
from src.models import StockInfo
from src.translator import translate_to_japanese
from src.yfinance_runtime import configure_yfinance_cache

logger = get_logger(__name__)
configure_yfinance_cache()

NO_SUMMARY_TEXT = "N/A"


def is_japanese_stock(ticker: str) -> bool:
    """Return True when a ticker looks like a Japanese listed stock."""

    code = "".join(filter(str.isdigit, str(ticker)))
    return (len(code) == 4 and str(ticker).startswith(code)) or str(ticker).endswith(
        ".T"
    )


def _first(source: dict[str, Any], key: str, default: Any = None) -> Any:
    value = source.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return default if value is None else value


def _percent(value: Any) -> float | None:
    if value is None:
        return None
    return float(value) * 100


@ttl_cache(ttl=CACHE_TTL_SHORT)
def get_current_price(ticker: str) -> float:
    if is_japanese_stock(ticker) and jquants_client.is_configured():
        price = jquants_client.get_current_price(ticker)
        if price > 0:
            return price

    if obb is None:
        logger.warning("OpenBB is not installed. Falling back to price=0.")
        return 0.0

    try:
        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        for key in ["last_price", "prev_close", "close", "open"]:
            price = _first(q, key)
            if price is not None:
                return float(price)
    except Exception as exc:
        logger.warning(f"Failed to get current price for {ticker}: {exc}")
    return 0.0


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    if is_japanese_stock(ticker) and jquants_client.is_configured():
        df = jquants_client.get_daily_quotes(ticker, period)
        if not df.empty:
            return df

    if obb is None:
        logger.warning("OpenBB is not installed. Returning empty historical data.")
        return pd.DataFrame()

    try:
        period_map = {
            "1d": timedelta(days=2),
            "5d": timedelta(days=7),
            "1mo": timedelta(days=30),
            "3mo": timedelta(days=90),
            "6mo": timedelta(days=180),
            "1y": timedelta(days=365),
            "2y": timedelta(days=730),
            "3y": timedelta(days=1095),
            "5y": timedelta(days=1825),
            "max": timedelta(days=3650),
        }
        start_date = (
            datetime.now() - period_map.get(period, timedelta(days=30))
        ).strftime("%Y-%m-%d")
        hist = obb.equity.price.historical(
            symbol=ticker, start_date=start_date, provider="yfinance"
        ).to_df()

        if not hist.empty:
            hist.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                },
                inplace=True,
            )
            return hist
    except Exception as exc:
        logger.warning(f"Failed to get historical data for {ticker}: {exc}")
    return pd.DataFrame()


def _extract_openbb_profile(
    ticker: str, info: StockInfo, *, include_summary: bool = True
) -> None:
    if obb is None:
        logger.warning("OpenBB is not installed. Skipping OpenBB profile fetch.")
        return

    try:
        profile_obj = obb.equity.profile(symbol=ticker, provider="yfinance")
        if profile_obj:
            profile = profile_obj.to_dict()
            info["name"] = _first(profile, "name", ticker)
            info["sector"] = _first(profile, "sector", "N/A")
            info["industry"] = _first(profile, "industry_category", "N/A")
            if include_summary:
                info["summary"] = _first(profile, "long_description", NO_SUMMARY_TEXT)
            info["website"] = _first(profile, "company_url", "")
            info["country"] = _first(profile, "hq_country", "")
            info["employees"] = _first(profile, "employees", 0)

            try:
                metrics_obj = obb.equity.fundamental.metrics(
                    symbol=ticker, provider="yfinance"
                )
                if metrics_obj:
                    _merge_openbb_metrics(info, metrics_obj.to_dict())
            except Exception as exc:
                logger.debug(f"Metrics fetch failed for {ticker}: {exc}")

        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        if q:
            info["current_price"] = _first(q, "last_price")
            info["fifty_two_week_high"] = _first(q, "year_high")
            info["fifty_two_week_low"] = _first(q, "year_low")
    except Exception as exc:
        logger.warning(f"OpenBB profile fetch failed for {ticker}: {exc}")


def _merge_openbb_metrics(info: StockInfo, metrics: dict[str, Any]) -> None:
    info["market_cap"] = _first(metrics, "market_cap")
    info["revenueGrowth"] = _percent(_first(metrics, "revenue_growth"))
    info["earningsGrowth"] = _percent(_first(metrics, "earnings_growth"))
    info["grossMargins"] = _percent(_first(metrics, "gross_margin"))
    info["operatingMargins"] = _percent(_first(metrics, "operating_margin"))
    info["currentRatio"] = _first(metrics, "current_ratio")
    info["debtToEquity"] = _first(metrics, "debt_to_equity")
    info["returnOnAssets"] = _percent(_first(metrics, "return_on_assets"))
    info["returnOnEquity"] = _percent(_first(metrics, "return_on_equity"))
    info["pe_ratio"] = _first(metrics, "pe_ratio")
    info["priceToBook"] = _first(metrics, "price_to_book")
    info["beta"] = _first(metrics, "beta")
    info["forward_pe"] = _first(metrics, "forward_pe")


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_valuation_metrics(ticker: str) -> dict[str, Any]:
    """Return valuation metrics without fetching or translating summary text."""

    metrics: dict[str, Any] = {
        "current_price": None,
        "market_cap": None,
        "forward_pe": None,
        "pe_ratio": None,
    }
    if obb is None:
        logger.warning("OpenBB is not installed. Skipping valuation metrics fetch.")
        return metrics

    try:
        metrics_obj = obb.equity.fundamental.metrics(symbol=ticker, provider="yfinance")
        if metrics_obj:
            raw = metrics_obj.to_dict()
            metrics["market_cap"] = _first(raw, "market_cap")
            metrics["forward_pe"] = _first(raw, "forward_pe")
            metrics["pe_ratio"] = _first(raw, "pe_ratio")
    except Exception as exc:
        logger.debug(f"Valuation metrics fetch failed for {ticker}: {exc}")

    try:
        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        for key in ["last_price", "prev_close", "close", "open"]:
            value = _first(q, key)
            if value is not None:
                metrics["current_price"] = value
                break
    except Exception as exc:
        logger.debug(f"Valuation quote fetch failed for {ticker}: {exc}")

    return metrics


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_stock_info(
    ticker: str,
    *,
    translate_summary: bool = True,
    include_summary: bool = True,
) -> StockInfo:
    info: StockInfo = {
        "name": ticker,
        "ticker": ticker,
        "sector": "N/A",
        "industry": "N/A",
        "summary": NO_SUMMARY_TEXT,
        "website": "",
        "logo": "",
        "city": "",
        "state": "",
        "country": "",
        "employees": 0,
        "exchange": "",
        "revenueGrowth": None,
        "earningsGrowth": None,
        "grossMargins": None,
        "operatingMargins": None,
        "currentRatio": None,
        "debtToEquity": None,
        "returnOnAssets": None,
        "pegRatio": None,
        "priceToBook": None,
        "beta": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
        "target_price": None,
        "current_price": None,
        "market_cap": None,
        "forward_pe": None,
        "pe_ratio": None,
        "share_outstanding": None,
    }

    _extract_openbb_profile(ticker, info, include_summary=include_summary)
    is_jp = is_japanese_stock(ticker)

    if is_jp and jquants_client.is_configured():
        jq_info = jquants_client.get_company_info(ticker)
        if jq_info:
            if jq_info.get("company_name"):
                info["name"] = jq_info["company_name"]
            if jq_info.get("sector_name"):
                info["sector"] = jq_info["sector_name"]
            if jq_info.get("industry_name") and info["industry"] == "N/A":
                info["industry"] = jq_info["industry_name"]

        jq_fins = jquants_client.get_fins_statements(ticker)
        if jq_fins and jq_fins.get("net_sales") and jq_fins.get("operating_income"):
            info["operatingMargins"] = (
                jq_fins["operating_income"] / jq_fins["net_sales"]
            ) * 100

    if is_jp and (
        not jquants_client.is_configured() or info["operatingMargins"] is None
    ):
        edinet_data = get_company_finance(ticker)
        if edinet_data and edinet_data["financials"]:
            latest_finance = edinet_data["financials"][0]
            if edinet_data.get("company_name") and info["name"] == ticker:
                info["name"] = edinet_data["company_name"]

            if latest_finance.get("net_sales") and latest_finance.get(
                "operating_income"
            ):
                info["operatingMargins"] = (
                    latest_finance["operating_income"] / latest_finance["net_sales"]
                ) * 100

    if (
        translate_summary
        and include_summary
        and info["summary"]
        and info["summary"] != NO_SUMMARY_TEXT
        and not is_japanese_stock(ticker)
    ):
        info["summary"] = translate_to_japanese(info["summary"])

    if not include_summary:
        info["summary"] = NO_SUMMARY_TEXT

    return info


@ttl_cache(ttl=CACHE_TTL_SHORT)
def get_quote(ticker: str) -> dict | None:
    if obb is None:
        logger.warning("OpenBB is not installed. Quote fetch skipped.")
        return None

    try:
        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        if q:
            last = None
            for key in ["last_price", "prev_close", "close", "open"]:
                value = _first(q, key)
                if value is not None:
                    last = value
                    break

            return {
                "c": last or 0,
                "h": _first(q, "high", 0),
                "l": _first(q, "low", 0),
                "o": _first(q, "open", 0),
                "pc": _first(q, "prev_close", 0),
            }
    except Exception as exc:
        logger.warning(f"Quote fetch error for {ticker}: {exc}")
    return None


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_earnings_calendar(
    from_date: str | None = None, to_date: str | None = None
) -> list[dict]:
    """Return earnings calendar data via Finnhub when configured."""

    from src.finnhub_client import get_earnings_calendar as _fh_earnings_calendar
    from src.finnhub_client import is_configured as _fh_configured

    if not _fh_configured():
        return []
    return _fh_earnings_calendar(from_date, to_date)


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
    """Return earnings surprise data via Finnhub when configured."""

    from src.finnhub_client import get_earnings_surprises as _fh_earnings_surprises
    from src.finnhub_client import is_configured as _fh_configured

    if not _fh_configured():
        return []
    return _fh_earnings_surprises(symbol, limit)


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
    """Return reported financial statements via Finnhub when configured."""

    from src.finnhub_client import get_financials_reported as _fh_financials_reported
    from src.finnhub_client import is_configured as _fh_configured

    if not _fh_configured():
        return []
    return _fh_financials_reported(symbol, freq)
