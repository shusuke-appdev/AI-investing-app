"""
Stock Data Provider
個別株関連のデータ取得（株価、ヒストリカルデータ、企業情報、決算等）を担当。
"""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf

from src.constants import CACHE_TTL_DAILY, CACHE_TTL_MEDIUM, CACHE_TTL_SHORT
from src.finnhub_client import (
    get_basic_financials,
    get_candles,
    get_company_profile,
    is_configured,
)
from src.finnhub_client import (
    get_earnings_calendar as _finnhub_get_earnings_calendar,
)
from src.finnhub_client import (
    get_earnings_surprises as _finnhub_get_earnings_surprises,
)
from src.finnhub_client import (
    get_financials_reported as _finnhub_get_financials_reported,
)
from src.finnhub_client import (
    get_quote as _finnhub_get_quote,
)
from src.log_config import get_logger
from src.models import StockInfo
from src.utils.translator import translate_to_japanese

logger = get_logger(__name__)


@st.cache_data(ttl=CACHE_TTL_SHORT)
def get_current_price(ticker: str) -> float:
    if is_configured():
        try:
            q = _finnhub_get_quote(ticker)
            if q and q.get("c"):
                return float(q["c"])
        except Exception:
            pass
    try:
        ticker_obj = yf.Ticker(ticker)
        if hasattr(ticker_obj, "fast_info") and "last_price" in ticker_obj.fast_info:
            price = ticker_obj.fast_info["last_price"]
            if price:
                return float(price)
        hist = ticker_obj.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0


@st.cache_data(ttl=CACHE_TTL_MEDIUM)
def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period)
        if not df.empty:
            return df
    except Exception:
        pass
    if is_configured():
        try:
            period_map = {
                "1d": 7,
                "5d": 7,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "max": 1825,
            }
            days = period_map.get(period, 30)
            now = datetime.now()
            _from = now - timedelta(days=days)
            _to = now
            df = get_candles(ticker, "D", _from, _to)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    return pd.DataFrame()


def _extract_finnhub_profile(ticker: str, info: StockInfo) -> None:
    try:
        profile = get_company_profile(ticker)
        if profile:
            info.update(
                {
                    "name": profile.get("name", ticker),
                    "ticker": profile.get("ticker", ticker),
                    "sector": profile.get("finnhubIndustry", "N/A"),
                    "industry": profile.get("finnhubIndustry", "N/A"),
                    "summary": profile.get("description", "情報なし"),
                    "website": profile.get("weburl", ""),
                    "logo": profile.get("logo", ""),
                    "exchange": profile.get("exchange", ""),
                    "country": profile.get("country", ""),
                    "market_cap": profile.get("marketCapitalization", 0) * 1e6,
                    "share_outstanding": profile.get("shareOutstanding", 0),
                }
            )
        basics = get_basic_financials(ticker)
        if basics and "metric" in basics:
            m = basics["metric"]
            info.update(
                {
                    "revenueGrowth": m.get("revenueGrowthQuarterlyYoy"),
                    "earningsGrowth": m.get("epsGrowthQuarterlyYoy"),
                    "grossMargins": m.get("grossMarginTTM"),
                    "operatingMargins": m.get("operatingMarginTTM"),
                    "currentRatio": m.get("currentRatioQuarterly"),
                    "debtToEquity": m.get("totalDebt/totalEquityQuarterly"),
                    "returnOnAssets": m.get("roaTTM"),
                    "pegRatio": m.get("pegRatioTTM"),
                    "priceToBook": m.get("pbAnnual"),
                    "beta": m.get("beta"),
                    "fifty_two_week_high": m.get("52WeekHigh"),
                    "fifty_two_week_low": m.get("52WeekLow"),
                    "pe_ratio": m.get("peTTM"),
                }
            )
        quote = _finnhub_get_quote(ticker)
        if quote:
            info["current_price"] = quote.get("c")
    except Exception as e:
        logger.warning(f"Finnhub profile fetch failed for {ticker}: {e}")


def _extract_yfinance_profile(ticker: str, info: StockInfo) -> None:
    needs_fallback = (
        info["summary"] == "情報なし"
        or info["sector"] == "N/A"
        or info["revenueGrowth"] is None
        or info["current_price"] is None
    )
    if not needs_fallback:
        return
    try:
        yf_ticker = yf.Ticker(ticker)
        yf_info = yf_ticker.info
        if yf_info:
            if info["name"] == ticker:
                info["name"] = yf_info.get("longName", yf_info.get("shortName", ticker))
            if info["sector"] == "N/A":
                info["sector"] = yf_info.get("sector", "N/A")
            if info["industry"] == "N/A":
                info["industry"] = yf_info.get("industry", "N/A")
            if info["summary"] == "情報なし":
                info["summary"] = yf_info.get("longBusinessSummary", "")
            if not info["website"]:
                info["website"] = yf_info.get("website", "")
            if not info["logo"]:
                info["logo"] = yf_info.get("logo_url", "")
            if info["employees"] == 0:
                info["employees"] = yf_info.get("fullTimeEmployees", 0)
            if info["market_cap"] is None:
                info["market_cap"] = yf_info.get("marketCap")
            if info["current_price"] is None:
                info["current_price"] = yf_info.get(
                    "currentPrice", yf_info.get("regularMarketPrice")
                )
            rg = yf_info.get("revenueGrowth")
            if info["revenueGrowth"] is None and rg is not None:
                info["revenueGrowth"] = rg * 100
            eg = yf_info.get("earningsGrowth")
            if info["earningsGrowth"] is None and eg is not None:
                info["earningsGrowth"] = eg * 100
            gm = yf_info.get("grossMargins")
            if info["grossMargins"] is None and gm is not None:
                info["grossMargins"] = gm * 100
            om = yf_info.get("operatingMargins")
            if info["operatingMargins"] is None and om is not None:
                info["operatingMargins"] = om * 100
            if info["currentRatio"] is None:
                info["currentRatio"] = yf_info.get("currentRatio")
            if info["debtToEquity"] is None:
                info["debtToEquity"] = yf_info.get("debtToEquity")
            ra = yf_info.get("returnOnAssets")
            if info["returnOnAssets"] is None and ra is not None:
                info["returnOnAssets"] = ra * 100
            if info["pegRatio"] is None:
                info["pegRatio"] = yf_info.get("pegRatio")
            if info["priceToBook"] is None:
                info["priceToBook"] = yf_info.get("priceToBook")
            if info["beta"] is None:
                info["beta"] = yf_info.get("beta")
            if info["fifty_two_week_high"] is None:
                info["fifty_two_week_high"] = yf_info.get("fiftyTwoWeekHigh")
            if info["forward_pe"] is None:
                info["forward_pe"] = yf_info.get("forwardPE")
            if info["target_price"] is None:
                info["target_price"] = yf_info.get("targetMeanPrice")
            if info["pe_ratio"] is None:
                info["pe_ratio"] = yf_info.get("trailingPE")
    except Exception as e:
        logger.warning(f"yfinance profile fallback failed for {ticker}: {e}")


@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_stock_info(ticker: str) -> StockInfo:
    info: StockInfo = {
        "name": ticker,
        "ticker": ticker,
        "sector": "N/A",
        "industry": "N/A",
        "summary": "情報なし",
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
    if is_configured():
        _extract_finnhub_profile(ticker, info)
    _extract_yfinance_profile(ticker, info)
    if info["summary"] and info["summary"] != "情報なし":
        info["summary"] = translate_to_japanese(info["summary"])
    return info


@st.cache_data(ttl=CACHE_TTL_SHORT)
def get_quote(ticker: str) -> dict | None:
    if not is_configured():
        return None
    try:
        return _finnhub_get_quote(ticker)
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_earnings_calendar(
    from_date: str | None = None, to_date: str | None = None
) -> list[dict]:
    if not is_configured():
        return []
    try:
        return _finnhub_get_earnings_calendar(from_date, to_date)
    except Exception:
        return []


@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
    if not is_configured():
        return []
    try:
        return _finnhub_get_earnings_surprises(symbol, limit)
    except Exception:
        return []


@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
    if not is_configured():
        return []
    try:
        return _finnhub_get_financials_reported(symbol, freq)
    except Exception:
        return []
