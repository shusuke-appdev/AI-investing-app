"""Stock data provider for prices, history, profile, and financial data."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

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


def _pick(source: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        try:
            value = source.get(key) if hasattr(source, "get") else None
        except Exception:
            value = None
        if value is None:
            try:
                value = getattr(source, key)
            except Exception:
                value = None
        if isinstance(value, list):
            value = value[0] if value else None
        if value is not None and not pd.isna(value):
            return value
    return default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _percent(value: Any) -> float | None:
    result = _safe_float(value)
    if result is None:
        return None
    return result * 100


def _get_fast_info(stock: yf.Ticker) -> Any:
    try:
        return stock.fast_info
    except Exception as exc:
        logger.debug(f"yfinance fast_info fetch failed for {stock.ticker}: {exc}")
        return {}


def _get_info(stock: yf.Ticker) -> dict[str, Any]:
    try:
        raw_info = getattr(stock, "info", None)
    except Exception as exc:
        logger.warning(f"yfinance profile fetch failed for {stock.ticker}: {exc}")
        return {}
    return raw_info if isinstance(raw_info, dict) else {}


def _get_history(stock: yf.Ticker, period: str) -> pd.DataFrame:
    try:
        return stock.history(period=period)
    except Exception as exc:
        logger.warning(f"yfinance history fetch failed for {stock.ticker}: {exc}")
        return pd.DataFrame()


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    normalized.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    normalized.index.name = normalized.index.name or "Date"
    return normalized


def _latest_history_values(df: pd.DataFrame) -> dict[str, float | None]:
    if df.empty:
        return {}

    normalized = _normalize_history(df)
    if "Close" in normalized.columns:
        normalized = normalized.dropna(subset=["Close"])
    else:
        normalized = normalized.dropna()
    if normalized.empty:
        return {}

    latest = normalized.iloc[-1]
    previous = normalized.iloc[-2] if len(normalized) >= 2 else latest
    return {
        "current": _safe_float(latest.get("Close")),
        "previous_close": _safe_float(previous.get("Close")),
        "high": _safe_float(latest.get("High")),
        "low": _safe_float(latest.get("Low")),
        "open": _safe_float(latest.get("Open")),
    }


def _build_yfinance_quote(ticker: str) -> dict | None:
    stock = yf.Ticker(ticker)
    fast_info = _get_fast_info(stock)
    history_values = _latest_history_values(_get_history(stock, "5d"))

    current = _safe_float(
        _pick(
            fast_info,
            "lastPrice",
            "last_price",
            "regularMarketPrice",
            "currentPrice",
        )
    )
    current = current if current is not None else history_values.get("current")

    previous_close = _safe_float(
        _pick(
            fast_info,
            "previousClose",
            "previous_close",
            "regularMarketPreviousClose",
        )
    )
    previous_close = (
        previous_close
        if previous_close is not None
        else history_values.get("previous_close")
    )

    open_price = _safe_float(_pick(fast_info, "open", "regularMarketOpen"))
    high = _safe_float(_pick(fast_info, "dayHigh", "regularMarketDayHigh"))
    low = _safe_float(_pick(fast_info, "dayLow", "regularMarketDayLow"))

    open_price = open_price if open_price is not None else history_values.get("open")
    high = high if high is not None else history_values.get("high")
    low = low if low is not None else history_values.get("low")

    if all(value is None for value in (current, previous_close, open_price, high, low)):
        return None

    change = None
    change_percent = None
    if current is not None and previous_close not in (None, 0):
        change = current - previous_close
        change_percent = change / previous_close * 100

    return {
        "c": current or 0,
        "d": change,
        "dp": change_percent,
        "h": high or 0,
        "l": low or 0,
        "o": open_price or 0,
        "pc": previous_close or 0,
    }


@ttl_cache(ttl=CACHE_TTL_SHORT)
def get_current_price(ticker: str) -> float:
    if is_japanese_stock(ticker) and jquants_client.is_configured():
        price = jquants_client.get_current_price(ticker)
        if price > 0:
            return price

    try:
        q = _build_yfinance_quote(ticker)
        price = _safe_float(q.get("c") if q else None)
        if price is not None:
            return price
    except Exception as exc:
        logger.warning(f"Failed to get current price for {ticker}: {exc}")
    return 0.0


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    if is_japanese_stock(ticker) and jquants_client.is_configured():
        df = jquants_client.get_daily_quotes(ticker, period)
        if not df.empty:
            return df

    stock = yf.Ticker(ticker)
    return _normalize_history(_get_history(stock, period))


def _extract_yfinance_profile(
    ticker: str, info: StockInfo, *, include_summary: bool = True
) -> None:
    stock = yf.Ticker(ticker)
    profile = _get_info(stock)
    fast_info = _get_fast_info(stock)

    if profile:
        info["name"] = _first(profile, "longName", ticker)
        if info["name"] == ticker:
            info["name"] = _first(profile, "shortName", ticker)
        info["sector"] = _first(profile, "sector", "N/A")
        info["industry"] = _first(profile, "industry", "N/A")
        if include_summary:
            info["summary"] = _first(profile, "longBusinessSummary", NO_SUMMARY_TEXT)
        info["website"] = _first(profile, "website", "")
        info["logo"] = _first(profile, "logo_url", "")
        info["city"] = _first(profile, "city", "")
        info["state"] = _first(profile, "state", "")
        info["country"] = _first(profile, "country", "")
        info["employees"] = _first(profile, "fullTimeEmployees", 0)
        info["exchange"] = _first(profile, "exchange", "")
        _merge_yfinance_metrics(info, profile, fast_info)

    q = _build_yfinance_quote(ticker)
    if q:
        info["current_price"] = q.get("c")
        info["fifty_two_week_high"] = _pick(
            fast_info, "yearHigh", "year_high", default=info["fifty_two_week_high"]
        )
        info["fifty_two_week_low"] = _pick(
            fast_info, "yearLow", "year_low", default=info["fifty_two_week_low"]
        )


def _merge_yfinance_metrics(
    info: StockInfo, metrics: dict[str, Any], fast_info: Any | None = None
) -> None:
    info["market_cap"] = _pick(metrics, "marketCap")
    if info["market_cap"] is None and fast_info is not None:
        info["market_cap"] = _pick(fast_info, "marketCap", "market_cap")
    info["revenueGrowth"] = _percent(_first(metrics, "revenueGrowth"))
    info["earningsGrowth"] = _percent(_first(metrics, "earningsGrowth"))
    info["grossMargins"] = _percent(_first(metrics, "grossMargins"))
    info["operatingMargins"] = _percent(_first(metrics, "operatingMargins"))
    info["currentRatio"] = _first(metrics, "currentRatio")
    info["debtToEquity"] = _first(metrics, "debtToEquity")
    info["returnOnAssets"] = _percent(_first(metrics, "returnOnAssets"))
    info["returnOnEquity"] = _percent(_first(metrics, "returnOnEquity"))
    info["pegRatio"] = _first(metrics, "pegRatio")
    info["pe_ratio"] = _first(metrics, "trailingPE")
    info["priceToBook"] = _first(metrics, "priceToBook")
    info["beta"] = _first(metrics, "beta")
    info["forward_pe"] = _first(metrics, "forwardPE")
    info["fifty_two_week_high"] = _first(metrics, "fiftyTwoWeekHigh")
    info["fifty_two_week_low"] = _first(metrics, "fiftyTwoWeekLow")
    info["target_price"] = _first(metrics, "targetMeanPrice")
    info["share_outstanding"] = _first(metrics, "sharesOutstanding")


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_valuation_metrics(ticker: str) -> dict[str, Any]:
    """Return valuation metrics without fetching or translating summary text."""

    metrics: dict[str, Any] = {
        "current_price": None,
        "market_cap": None,
        "forward_pe": None,
        "pe_ratio": None,
    }
    stock = yf.Ticker(ticker)
    profile = _get_info(stock)
    fast_info = _get_fast_info(stock)

    metrics["market_cap"] = _pick(profile, "marketCap")
    if metrics["market_cap"] is None:
        metrics["market_cap"] = _pick(fast_info, "marketCap", "market_cap")
    metrics["forward_pe"] = _first(profile, "forwardPE")
    metrics["pe_ratio"] = _first(profile, "trailingPE")

    q = _build_yfinance_quote(ticker)
    if q:
        metrics["current_price"] = q.get("c")

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

    _extract_yfinance_profile(ticker, info, include_summary=include_summary)
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
    try:
        return _build_yfinance_quote(ticker)
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
