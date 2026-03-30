"""
Stock Data Provider
個別株関連のデータ取得（株価、ヒストリカルデータ、企業情報、決算等）を担当。
OpenBB (v4) および EDINET API を活用する。
"""
import os
# Streamlit CloudなどのRead-Only環境でのPermissionErrorを防ぐ
os.environ["OPENBB_AUTO_BUILD"] = "False"

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from openbb import obb

from src.constants import CACHE_TTL_DAILY, CACHE_TTL_MEDIUM, CACHE_TTL_SHORT
from src.log_config import get_logger
from src.models import StockInfo
from src.utils.translator import translate_to_japanese
from src.edinet_client import get_company_finance

logger = get_logger(__name__)

def is_japanese_stock(ticker: str) -> bool:
    """日本株（証券コード4桁等）か判定する"""
    code = "".join(filter(str.isdigit, str(ticker)))
    return (len(code) == 4 and str(ticker).startswith(code)) or str(ticker).endswith(".T")

@st.cache_data(ttl=CACHE_TTL_SHORT)
def get_current_price(ticker: str) -> float:
    try:
        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        if q and "last_price" in q and q["last_price"]:
            price = q["last_price"][0]
            if price is not None:
                return float(price)
    except Exception as e:
        logger.warning(f"Failed to get current price for {ticker}: {e}")
    return 0.0

@st.cache_data(ttl=CACHE_TTL_MEDIUM)
def get_historical_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    try:
        period_map = {
            "1d": timedelta(days=2),
            "5d": timedelta(days=7),
            "1mo": timedelta(days=30),
            "3mo": timedelta(days=90),
            "6mo": timedelta(days=180),
            "1y": timedelta(days=365),
            "max": timedelta(days=1825),
        }
        days = period_map.get(period, timedelta(days=30))
        start_date = (datetime.now() - days).strftime("%Y-%m-%d")
        
        hist = obb.equity.price.historical(symbol=ticker, start_date=start_date, provider="yfinance").to_df()
        
        if not hist.empty:
            hist.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            return hist
    except Exception as e:
        logger.warning(f"Failed to get historical data for {ticker}: {e}")
    return pd.DataFrame()

def _extract_openbb_profile(ticker: str, info: StockInfo) -> None:
    try:
        profile_obj = obb.equity.profile(symbol=ticker, provider="yfinance")
        if profile_obj:
            p = profile_obj.to_dict()
            info["name"] = p.get("name", [ticker])[0] if p.get("name") else ticker
            info["sector"] = p.get("sector", ["N/A"])[0] if p.get("sector") else "N/A"
            info["industry"] = p.get("industry_category", ["N/A"])[0] if p.get("industry_category") else "N/A"
            desc = p.get("long_description", [])
            info["summary"] = desc[0] if desc else "情報なし"
            info["website"] = p.get("company_url", [""])[0] if p.get("company_url") else ""
            info["country"] = p.get("hq_country", [""])[0] if p.get("hq_country") else ""
            info["employees"] = p.get("employees", [0])[0] if p.get("employees") else 0
            
            try:
                metrics_obj = obb.equity.fundamental.metrics(symbol=ticker, provider="yfinance")
                if metrics_obj:
                    m = metrics_obj.to_dict()
                    info["market_cap"] = m.get("market_cap", [None])[0]
                    
                    rg = m.get("revenue_growth", [None])[0]
                    if rg is not None: info["revenueGrowth"] = rg * 100
                    
                    eg = m.get("earnings_growth", [None])[0]
                    if eg is not None: info["earningsGrowth"] = eg * 100
                    
                    gm = m.get("gross_margin", [None])[0]
                    if gm is not None: info["grossMargins"] = gm * 100
                    
                    om = m.get("operating_margin", [None])[0]
                    if om is not None: info["operatingMargins"] = om * 100
                    
                    info["currentRatio"] = m.get("current_ratio", [None])[0]
                    info["debtToEquity"] = m.get("debt_to_equity", [None])[0]
                    
                    ra = m.get("return_on_assets", [None])[0]
                    if ra is not None: info["returnOnAssets"] = ra * 100
                    
                    info["pe_ratio"] = m.get("pe_ratio", [None])[0]
                    info["priceToBook"] = m.get("price_to_book", [None])[0]
                    info["beta"] = m.get("beta", [None])[0]
                    info["forward_pe"] = m.get("forward_pe", [None])[0]
            except Exception as e:
                logger.debug(f"Metrics fetch failed for {ticker}: {e}")

        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        if q:
            info["current_price"] = q.get("last_price", [None])[0]
            info["fifty_two_week_high"] = q.get("year_high", [None])[0]
            info["fifty_two_week_low"] = q.get("year_low", [None])[0]
            
    except Exception as e:
        logger.warning(f"OpenBB profile fetch failed for {ticker}: {e}")

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
    
    _extract_openbb_profile(ticker, info)
    
    if is_japanese_stock(ticker):
        edinet_data = get_company_finance(ticker)
        if edinet_data and edinet_data["financials"]:
            latest_finance = edinet_data["financials"][0]
            if edinet_data.get("company_name"):
                info["name"] = edinet_data["company_name"]
            
            if latest_finance.get("net_sales") and latest_finance.get("operating_income"):
                 info["operatingMargins"] = (latest_finance["operating_income"] / latest_finance["net_sales"]) * 100
    
    if info["summary"] and info["summary"] != "情報なし":
        if not is_japanese_stock(ticker):
             info["summary"] = translate_to_japanese(info["summary"])
        
    return info

@st.cache_data(ttl=CACHE_TTL_SHORT)
def get_quote(ticker: str) -> dict | None:
    try:
        q = obb.equity.price.quote(symbol=ticker, provider="yfinance").to_dict()
        if q:
            return {
                "c": q.get("last_price", [0])[0],
                "h": q.get("high", [0])[0],
                "l": q.get("low", [0])[0],
                "o": q.get("open", [0])[0],
                "pc": q.get("prev_close", [0])[0]
            }
    except Exception as e:
        logger.warning(f"Quote fetch error for {ticker}: {e}")
    return None

@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_earnings_calendar(from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    # Placeholder: OpenBB implementation or other data source needed
    return []

@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
    # Placeholder: OpenBB implementation or other data source needed
    return []

@st.cache_data(ttl=CACHE_TTL_DAILY)
def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
    # Placeholder: OpenBB implementation or other data source needed
    return []
