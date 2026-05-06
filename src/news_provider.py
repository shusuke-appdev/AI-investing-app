"""
News Provider
ニュース関連のデータ取得を担当。
"""

from datetime import datetime

from src.cache import ttl_cache

from src.constants import CACHE_TTL_MEDIUM
from src.finnhub_client import (
    get_company_news as _finnhub_get_company_news,
)
from src.finnhub_client import (
    is_configured,
)
from src.models import NewsItem


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_stock_news(ticker: str, max_items: int = 10) -> list[NewsItem]:
    """Get stock news."""
    if not is_configured():
        return []
    try:
        news = _finnhub_get_company_news(ticker)
        results: list[NewsItem] = []
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


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_company_news_raw(ticker: str) -> list[dict]:
    """Finnhub Company Newsの生データを返す"""
    if not is_configured():
        return []
    try:
        return _finnhub_get_company_news(ticker) or []
    except Exception:
        return []
