"""
Data Provider Module
Abstrating data fetching logic (Finnhub + yfinance fallback).
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import importlib

# Use late import for yfinance to avoid circular deps if any, 
# though direct import is usually fine.
import yfinance as yf
import pandas as pd

from src.finnhub_client import (
    get_candles, get_quote, get_company_profile, 
    get_basic_financials, get_company_news, is_configured,
    get_option_chain as finnhub_get_option_chain,
)
from src.market_config import get_market_config
from src.constants import MARKET_US
from src.models import StockInfo, NewsItem, MarketIndex


# We will move hybrid logic from market_data.py to here.

class DataProvider:
    """
    Centralized data provider for the application.
    Handles switching between Finnhub and yfinance, and caching strategies.
    """
    
    @staticmethod
    def get_current_price(ticker: str) -> float:
        """
        Get current price for a ticker.
        Priority:
        1. Finnhub Quote (US Stocks)
        2. yfinance fast_info / history (Fallback)
        """
        # 1. Finnhub
        if is_finnhub_configured():
            try:
                q = get_quote(ticker)
                if q and q.get("c"):
                    return float(q["c"])
            except Exception as e:
                # print(f"[DataProvider] Finnhub error for {ticker}: {e}")
                pass
        
        # 3. yfinance Fallback
        try:
            # Note: Do not use custom session for yf to avoid anti-bot issues
            ticker_obj = yf.Ticker(ticker)
            # Try fast info first
            if hasattr(ticker_obj, "fast_info") and "last_price" in ticker_obj.fast_info:
                 price = ticker_obj.fast_info["last_price"]
                 if price: return float(price)
            
            # Fallback to history
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            print(f"[DataProvider] yfinance error for {ticker}: {e}")
            
        return 0.0
            
    @staticmethod
    def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
        """
        Get OHLCV data.
        Logic ported from market_data.py
        """
        # 1. Finnhub
        if is_finnhub_configured():
            try:
                # Map period to resolution/start_date
                 from datetime import timedelta
                 resolution = "D"
                 if period in ["1d", "5d"]: resolution = "60"
                 
                 now = datetime.now()
                 start = now - timedelta(days=30)
                 if period == "1d": start = now - timedelta(days=1); resolution="5"
                 elif period == "5d": start = now - timedelta(days=5); resolution="60"
                 elif period == "3mo": start = now - timedelta(days=90)
                 elif period == "6mo": start = now - timedelta(days=180)
                 elif period == "1y": start = now - timedelta(days=365)
                 elif period == "ytd": start = datetime(now.year, 1, 1)
                 elif period == "max": start = now - timedelta(days=365*5)

                 df = get_candles(ticker, resolution, start, now)
                 if df is not None and not df.empty:
                     return df
            except Exception as e:
                print(f"[DataProvider] Finnhub candle error for {ticker}: {e}")

        # 2. yfinance Fallback
        try:
            return yf.Ticker(ticker).history(period=period)
        except Exception as e:
             print(f"[DataProvider] yfinance history error for {ticker}: {e}")
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
                result = finnhub_get_option_chain(ticker)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[DataProvider] Finnhub option chain error for {ticker}: {e}")

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
                
            return pd.concat(all_calls, ignore_index=True), pd.concat(all_puts, ignore_index=True)
        except Exception as e:
            print(f"[DataProvider] Option fetch error for {ticker}: {e}")
            return None

    @staticmethod
    def get_market_indices(market_type: str = MARKET_US) -> Dict[str, MarketIndex]:
        """
        Get major market indices data.
        US: Finnhub quote
        JP: Stooq
        Global: Finnhub quote
        """
        config = get_market_config(market_type)
        result: Dict[str, MarketIndex] = {}
        
        # --- 日本市場 (Stooq優先) ---
        if market_type == "JP":
            from src.market_data import _get_stooq_data, JP_STOOQ_TICKERS
            
            for name, ticker in JP_STOOQ_TICKERS.items():
                data = _get_stooq_data(ticker)
                if data:
                    result[name] = {"price": data[0], "change": data[1], "ticker": ticker}
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
        yf_targets = {
            **config["treasuries"],
            **config["forex"]
        }
        
        if not is_finnhub_configured():
            yf_targets.update(finnhub_targets)
            finnhub_targets = {}

        # --- Fetch from Finnhub ---
        for name, ticker in finnhub_targets.items():
            try:
                q = get_quote(ticker)
                if isinstance(q, dict) and q.get("c") not in (0, None):
                    result[name] = {"price": q.get("c"), "change": q.get("dp", 0), "ticker": ticker}
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
                                hist = batch_data.xs(ticker, level=1, axis=1) if isinstance(batch_data.columns, pd.MultiIndex) else batch_data
                            else:
                                hist = batch_data
                            
                            if not hist.empty and len(hist) >= 1:
                                current = hist["Close"].iloc[-1]
                                prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                                change = ((current - prev) / prev) * 100 if prev != 0 else 0
                                
                                result[name] = {"price": float(current), "change": float(change), "ticker": ticker}
                            else:
                                result[name] = {"price": 0.0, "change": 0.0, "ticker": ticker}
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
            news = get_company_news(ticker)
            # Format conversion
            results: List[NewsItem] = []
            for item in news[:max_items]:
                results.append({
                    "title": item.get("headline", ""),
                    "publisher": item.get("source", ""),
                    "link": item.get("url", ""),
                    "published": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%d %H:%M"),
                    "summary": item.get("summary", "")
                })
            return results
        except Exception:
            return []

    @staticmethod
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
            
            "revenueGrowth": None, "earningsGrowth": None, 
            "grossMargins": None, "operatingMargins": None, "currentRatio": None,
            "debtToEquity": None, "returnOnAssets": None, "pegRatio": None,
            "priceToBook": None, "beta": None,
            "fifty_two_week_high": None, "fifty_two_week_low": None,
            "target_price": None, "current_price": None,
            "market_cap": None, "forward_pe": None, "pe_ratio": None,
            "share_outstanding": None
        }

        # 1. Finnhub Data
        if is_configured():
            try:
                # A. Profile
                profile = get_company_profile(ticker)
                if profile:
                    info.update({
                        "name": profile.get("name", ticker),
                        "ticker": profile.get("ticker", ticker),
                        "sector": profile.get("finnhubIndustry", "N/A"),
                        "industry": profile.get("finnhubIndustry", "N/A"),
                        "website": profile.get("weburl", ""),
                        "logo": profile.get("logo", ""),
                        "exchange": profile.get("exchange", ""),
                        "country": profile.get("country", ""),
                        "market_cap": profile.get("marketCapitalization", 0) * 1e6, # Finnhub results in Millions
                        "share_outstanding": profile.get("shareOutstanding", 0)
                    })

                # B. Basic Financials (Metrics)
                basics = get_basic_financials(ticker)
                if basics and "metric" in basics:
                    m = basics["metric"]
                    info.update({
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
                    })
                
                # C. Quote for Current Price
                quote = get_quote(ticker)
                if quote:
                    info["current_price"] = quote.get("c")

            except Exception as e:
                print(f"[DATA_WARN] Finnhub fetch failed for {ticker}: {e}")

        # 2. yfinance Fallback (補完・代替)
        try:
            # Finnhubで情報が不足している場合、またはキー未設定の場合に実行
            # 必要なキーがNoneかどうかで判断
            needs_fallback = (
                info["summary"] == "情報なし" or 
                info["sector"] == "N/A" or 
                info["revenueGrowth"] is None or
                info["current_price"] is None
            )
            
            if needs_fallback:
                # Note: Do not pass custom session to yf.Ticker
                yf_ticker = yf.Ticker(ticker)
                yf_info = yf_ticker.info
                
                if yf_info:
                    # Basic Info
                    if info["name"] == ticker: info["name"] = yf_info.get("longName", yf_info.get("shortName", ticker))
                    if info["sector"] == "N/A": info["sector"] = yf_info.get("sector", "N/A")
                    if info["industry"] == "N/A": info["industry"] = yf_info.get("industry", "N/A")
                    if info["summary"] == "情報なし": info["summary"] = yf_info.get("longBusinessSummary", "")
                    if not info["website"]: info["website"] = yf_info.get("website", "")
                    if not info["logo"]: info["logo"] = yf_info.get("logo_url", "")
                    if info["employees"] == 0: info["employees"] = yf_info.get("fullTimeEmployees", 0)
                    
                    # Metrics Fallback
                    if info["market_cap"] is None: info["market_cap"] = yf_info.get("marketCap")
                    if info["current_price"] is None: info["current_price"] = yf_info.get("currentPrice", yf_info.get("regularMarketPrice"))
                    if info["revenueGrowth"] is None: info["revenueGrowth"] = yf_info.get("revenueGrowth", 0) * 100 # yf is fraction
                    if info["earningsGrowth"] is None: info["earningsGrowth"] = yf_info.get("earningsGrowth", 0) * 100
                    if info["grossMargins"] is None: info["grossMargins"] = yf_info.get("grossMargins", 0) * 100
                    if info["operatingMargins"] is None: info["operatingMargins"] = yf_info.get("operatingMargins", 0) * 100
                    if info["currentRatio"] is None: info["currentRatio"] = yf_info.get("currentRatio")
                    if info["debtToEquity"] is None: info["debtToEquity"] = yf_info.get("debtToEquity")
                    if info["returnOnAssets"] is None: info["returnOnAssets"] = yf_info.get("returnOnAssets", 0) * 100
                    if info["pegRatio"] is None: info["pegRatio"] = yf_info.get("pegRatio")
                    if info["priceToBook"] is None: info["priceToBook"] = yf_info.get("priceToBook")
                    if info["beta"] is None: info["beta"] = yf_info.get("beta")
                    if info["fifty_two_week_high"] is None: info["fifty_two_week_high"] = yf_info.get("fiftyTwoWeekHigh")
                    if info["forward_pe"] is None: info["forward_pe"] = yf_info.get("forwardPE")
                    if info["target_price"] is None: info["target_price"] = yf_info.get("targetMeanPrice")
                    if info["pe_ratio"] is None: info["pe_ratio"] = yf_info.get("trailingPE")
                    
        except Exception as e:
            print(f"[DATA_WARN] yfinance profile fallback failed for {ticker}: {e}")

        return info
