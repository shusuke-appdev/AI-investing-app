"""
Data Provider Module
アプリケーション全体の唯一のデータアクセスポイント。
Finnhub + yfinance のハイブリッドフェッチとキャッシュを管理。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import yfinance as yf

from src.constants import (
    CACHE_TTL_DAILY,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_SHORT,
    MARKET_US,
)
from src.finnhub_client import (
    get_basic_financials,
    get_candles,
    get_company_profile,
    is_configured,
)
from src.finnhub_client import (
    get_company_news as _finnhub_get_company_news,
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
    get_option_chain as _finnhub_get_option_chain,
)
from src.finnhub_client import (
    get_quote as _finnhub_get_quote,
)
from src.log_config import get_logger
from src.market_config import get_market_config
from src.models import MarketIndex, NewsItem, StockInfo
from src.utils.translator import translate_to_japanese


logger = get_logger(__name__)


# --- 日本市場用 Stooq データ取得 ---

JP_STOOQ_TICKERS: Dict[str, str] = {
    "日経225": "^NKX",
    "TOPIX": "^TPX",
    "10年国債": "10YJP.B",
}


def _get_stooq_data(ticker: str) -> Optional[Tuple[float, float]]:
    """
    Stooqから日本市場データを取得する。

    Args:
        ticker: Stooqティッカー

    Returns:
        (current_price, change_percent) のタプル、または None
    """
    try:
        url = f"https://stooq.com/q/l/?s={ticker}&f=sd2t2ohlcv&h&e=csv"
        df = pd.read_csv(url)
        if df.empty or "Close" not in df.columns:
            return None
        close = float(df["Close"].iloc[0])
        open_price = float(df["Open"].iloc[0])
        change = ((close - open_price) / open_price * 100) if open_price != 0 else 0.0
        return close, round(change, 2)
    except Exception as e:
        logger.info(f"[STOOQ_WARN] Failed to fetch {ticker}: {e}")
        return None


class DataProvider:
    """
    Centralized data provider for the application.
    Handles switching between Finnhub and yfinance, and caching strategies.
    """

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_current_price(ticker: str) -> float:
        """
        Get current price for a ticker.
        Priority: Finnhub Quote -> yfinance fallback.
        """
        if is_configured():
            try:
                q = _finnhub_get_quote(ticker)
                if q and q.get("c"):
                    return float(q["c"])
            except Exception:
                pass

        try:
            ticker_obj = yf.Ticker(ticker)
            if (
                hasattr(ticker_obj, "fast_info")
                and "last_price" in ticker_obj.fast_info
            ):
                price = ticker_obj.fast_info["last_price"]
                if price:
                    return float(price)
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass

        return 0.0

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
        """
        Get OHLCV data.
        Priority: yfinance (most periods) -> Finnhub candles (fallback).
        """
        # 1. yfinance (primary)
        try:
            df = yf.Ticker(ticker).history(period=period)
            if not df.empty:
                return df
        except Exception:
            pass

        # 2. Finnhub candles (fallback)
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
                _from = int((now - timedelta(days=days)).timestamp())
                _to = int(now.timestamp())
                df = get_candles(ticker, "D", _from, _to)
                if df is not None and not df.empty:
                    return df
            except Exception:
                pass

        return pd.DataFrame()

    @staticmethod
    def get_option_chain(ticker: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Get option chain data.
        Priority: Finnhub (Greeks included) -> yfinance fallback.
        """
        # 1. Finnhub (推奨: Greeks含む)
        if is_configured():
            try:
                result = _finnhub_get_option_chain(ticker)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(
                    f"[DataProvider] Finnhub option chain error for {ticker}: {e}"
                )

        # 2. yfinance Fallback (Greeksなし)
        try:
            stock = yf.Ticker(ticker)
            try:
                expirations = stock.options
            except Exception:
                return None

            if not expirations:
                return None

            all_calls = []
            all_puts = []
            # Finnhubと同一の満期日数（4）を取得して一貫性を確保
            for exp in expirations[:4]:
                try:
                    opt = stock.option_chain(exp)
                    calls = opt.calls.copy()
                    puts = opt.puts.copy()
                    calls["expiration"] = exp
                    puts["expiration"] = exp
                    all_calls.append(calls)
                    all_puts.append(puts)
                except Exception:
                    continue

            if not all_calls:
                return None

            return pd.concat(all_calls, ignore_index=True), pd.concat(
                all_puts, ignore_index=True
            )
        except Exception as e:
            logger.error(f"[DataProvider] Option fetch error for {ticker}: {e}")
            return None

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_market_indices(market_type: str = MARKET_US) -> Dict[str, MarketIndex]:
        """
        Get major market indices data.
        US: Finnhub quote, JP: Stooq, Global: Finnhub quote.
        """
        config = get_market_config(market_type)
        result: Dict[str, MarketIndex] = {}

        # --- 日本市場 (Stooq) ---
        if market_type == "JP":
            for name, ticker in JP_STOOQ_TICKERS.items():
                data = _get_stooq_data(ticker)
                if data:
                    result[name] = {
                        "price": data[0],
                        "change": data[1],
                        "ticker": ticker,
                    }
            return result

        # --- 米国市場 (Finnhub移行 + YF併用) ---

        # 1. Finnhub Targets
        finnhub_targets = {
            **config["indices"],
            **config["sectors"],
            **config["commodities"],
            **config["crypto"],
        }

        # 2. yfinance Targets
        yf_targets = {**config["treasuries"], **config["forex"]}

        if not is_configured():
            yf_targets.update(finnhub_targets)
            finnhub_targets = {}

        # --- Fetch from Finnhub ---
        for name, ticker in finnhub_targets.items():
            try:
                q = _finnhub_get_quote(ticker)
                if isinstance(q, dict) and q.get("c") not in (0, None):
                    result[name] = {
                        "price": q.get("c"),
                        "change": q.get("dp", 0),
                        "ticker": ticker,
                    }
                else:
                    yf_targets[name] = ticker
            except Exception:
                yf_targets[name] = ticker

        # --- Fetch from yfinance ---
        if yf_targets:
            try:
                tickers_list = list(yf_targets.values())
                if tickers_list:
                    batch_data = yf.download(tickers_list, period="5d", progress=False)

                    for name, ticker in yf_targets.items():
                        try:
                            if len(tickers_list) > 1:
                                hist = (
                                    batch_data.xs(ticker, level=1, axis=1)
                                    if isinstance(batch_data.columns, pd.MultiIndex)
                                    else batch_data
                                )
                            else:
                                hist = batch_data

                            # Handle MultiIndex column issue where xs might fail or result is still DataFrame
                            if isinstance(hist, pd.DataFrame):
                                # If columns are MultiIndex, try to droplevel or access
                                if isinstance(hist.columns, pd.MultiIndex):
                                    try:
                                        hist = hist.xs(ticker, level=1, axis=1)
                                    except Exception:
                                        pass
                            
                            # Fallback: specific manual fetch if batch failed for this ticker
                            if hist.empty:
                                try:
                                    # Fallback for individual ticker (especially ^TNX can be tricky in batch)
                                    hist = yf.Ticker(ticker).history(period="5d")
                                except Exception:
                                    pass

                            if not hist.empty and len(hist) >= 1:
                                current = hist["Close"].iloc[-1]
                                prev = (
                                    hist["Close"].iloc[-2]
                                    if len(hist) >= 2
                                    else current
                                )
                                change = (
                                    ((current - prev) / prev) * 100 if prev != 0 else 0
                                )

                                result[name] = {
                                    "price": float(current),
                                    "change": float(change),
                                    "ticker": ticker,
                                }
                            else:
                                result[name] = {
                                    "price": 0.0,
                                    "change": 0.0,
                                    "ticker": ticker,
                                }
                        except Exception:
                            pass
            except Exception:
                pass

        return result

    @staticmethod
    def get_stock_news(ticker: str, max_items: int = 10) -> List[NewsItem]:
        """
        Get stock news.
        Uses Finnhub Company News.
        """
        if not is_configured():
            return []

        try:
            news = _finnhub_get_company_news(ticker)
            results: List[NewsItem] = []
            for item in news[:max_items]:
                results.append(
                    {
                        "title": item.get("headline", ""),
                        "publisher": item.get("source", ""),
                        "link": item.get("url", ""),
                        "published": datetime.fromtimestamp(
                            item.get("datetime", 0)
                        ).strftime("%Y-%m-%d %H:%M"),
                        "summary": item.get("summary", ""),
                    }
                )
            return results
        except Exception:
            return []

    @staticmethod
    def get_company_news_raw(ticker: str) -> list[dict]:
        """Finnhub Company Newsの生データを返す（market_analyst_service用）"""
        if not is_configured():
            return []
        try:
            return _finnhub_get_company_news(ticker) or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_DAILY)
    def get_stock_info(ticker: str) -> StockInfo:
        """
        Get company profile (Finnhub priority -> yfinance Fallback).
        """
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

        # 1. Finnhub Data
        if is_configured():
            try:
                # A. Profile
                profile = get_company_profile(ticker)
                if profile:
                    info.update(
                        {
                            "name": profile.get("name", ticker),
                            "ticker": profile.get("ticker", ticker),
                            "sector": profile.get("finnhubIndustry", "N/A"),
                            "industry": profile.get("finnhubIndustry", "N/A"),
                            # "description" is often where the summary is in Finnhub profile2
                            "summary": profile.get("description", "情報なし"),
                            "website": profile.get("weburl", ""),
                            "logo": profile.get("logo", ""),
                            "exchange": profile.get("exchange", ""),
                            "country": profile.get("country", ""),
                            "market_cap": profile.get("marketCapitalization", 0)
                            * 1e6,  # Finnhub results in Millions
                            "share_outstanding": profile.get("shareOutstanding", 0),
                        }
                    )

                # B. Basic Financials (Metrics)
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

                # C. Quote for Current Price
                quote = _finnhub_get_quote(ticker)
                if quote:
                    info["current_price"] = quote.get("c")

            except Exception as e:
                logger.warning(f"Finnhub fetch failed for {ticker}: {e}")

        # 2. yfinance Fallback (補完・代替)
        try:
            # Finnhubで情報が不足している場合、またはキー未設定の場合に実行
            # 必要なキーがNoneかどうかで判断
            needs_fallback = (
                info["summary"] == "情報なし"
                or info["sector"] == "N/A"
                or info["revenueGrowth"] is None
                or info["current_price"] is None
            )

            if needs_fallback:
                # Note: Do not pass custom session to yf.Ticker
                yf_ticker = yf.Ticker(ticker)
                yf_info = yf_ticker.info

                if yf_info:
                    # Basic Info
                    if info["name"] == ticker:
                        info["name"] = yf_info.get(
                            "longName", yf_info.get("shortName", ticker)
                        )
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

                    # Metrics Fallback
                    if info["market_cap"] is None:
                        info["market_cap"] = yf_info.get("marketCap")
                    if info["current_price"] is None:
                        info["current_price"] = yf_info.get(
                            "currentPrice", yf_info.get("regularMarketPrice")
                        )
                    if info["revenueGrowth"] is None:
                        info["revenueGrowth"] = (
                            yf_info.get("revenueGrowth", 0) * 100
                        )  # yf is fraction
                    if info["earningsGrowth"] is None:
                        info["earningsGrowth"] = yf_info.get("earningsGrowth", 0) * 100
                    if info["grossMargins"] is None:
                        info["grossMargins"] = yf_info.get("grossMargins", 0) * 100
                    if info["operatingMargins"] is None:
                        info["operatingMargins"] = (
                            yf_info.get("operatingMargins", 0) * 100
                        )
                    if info["currentRatio"] is None:
                        info["currentRatio"] = yf_info.get("currentRatio")
                    if info["debtToEquity"] is None:
                        info["debtToEquity"] = yf_info.get("debtToEquity")
                    if info["returnOnAssets"] is None:
                        info["returnOnAssets"] = yf_info.get("returnOnAssets", 0) * 100
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

        except Exception as e:
            logger.warning(f"yfinance profile fallback failed for {ticker}: {e}")

        # Translate summary to Japanese if needed
        # This is cached by st.cache_data on get_stock_info, so we don't need extra caching here
        if info["summary"] and info["summary"] != "情報なし":
             info["summary"] = translate_to_japanese(info["summary"])

        return info

    # --- 追加メソッド（finnhub_client直接呼び出しを排除するためのラッパー） ---

    @staticmethod
    def get_quote(ticker: str) -> Optional[dict]:
        """Finnhub Quote APIのラッパー。"""
        if not is_configured():
            return None
        try:
            return _finnhub_get_quote(ticker)
        except Exception:
            return None

    @staticmethod
    def get_earnings_calendar(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[dict]:
        """決算カレンダーを取得（Finnhub経由）。"""
        if not is_configured():
            return []
        try:
            return _finnhub_get_earnings_calendar(from_date, to_date)
        except Exception:
            return []

    @staticmethod
    def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
        """EPSサプライズデータを取得（Finnhub経由）。"""
        if not is_configured():
            return []
        try:
            return _finnhub_get_earnings_surprises(symbol, limit)
        except Exception:
            return []

    @staticmethod
    def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
        """報告済み財務諸表を取得（Finnhub経由）。"""
        if not is_configured():
            return []
        try:
            return _finnhub_get_financials_reported(symbol, freq)
        except Exception:
            return []
