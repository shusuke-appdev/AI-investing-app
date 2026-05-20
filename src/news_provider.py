"""
News Provider
ニュース関連のデータ取得を担当。
"""

from datetime import datetime

from src.cache import ttl_cache
from src.constants import CACHE_TTL_MEDIUM
from src.finnhub_client import (
    get_auth_error_message,
    get_auth_status,
    is_configured,
)
from src.finnhub_client import (
    get_company_news as _finnhub_get_company_news,
)
from src.models import NewsItem


def _news_status_payload(
    *,
    items: list[NewsItem] | None = None,
    source_status: str,
    error_reason: str = "",
) -> dict:
    return {
        "items": items or [],
        "source": "finnhub",
        "source_status": source_status,
        "error_reason": error_reason,
    }


def _format_news_items(news: list[dict], max_items: int) -> list[NewsItem]:
    results: list[NewsItem] = []
    for item in news[:max_items]:
        results.append(
            {
                "title": item.get("headline", ""),
                "publisher": item.get("source", ""),
                "link": item.get("url", ""),
                "published": datetime.fromtimestamp(item.get("datetime", 0)).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "summary": item.get("summary", ""),
            }
        )
    return results


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_stock_news_with_status(ticker: str, max_items: int = 10) -> dict:
    """Get stock news with Finnhub source status for UI/AI context."""

    if not is_configured():
        status = get_auth_status()
        return _news_status_payload(
            source_status=status,
            error_reason=get_auth_error_message(),
        )

    try:
        raw_news = _finnhub_get_company_news(ticker)
    except Exception as exc:
        return _news_status_payload(source_status="error", error_reason=str(exc))

    auth_status = get_auth_status()
    if auth_status == "invalid":
        return _news_status_payload(
            source_status=auth_status,
            error_reason=get_auth_error_message(),
        )

    if not raw_news:
        return _news_status_payload(source_status="empty")

    return _news_status_payload(
        items=_format_news_items(raw_news, max_items),
        source_status="available",
    )


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_stock_news(ticker: str, max_items: int = 10) -> list[NewsItem]:
    """Get stock news."""
    return list(get_stock_news_with_status(ticker, max_items).get("items") or [])


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
def get_company_news_raw(ticker: str) -> list[dict]:
    """Finnhub Company Newsの生データを返す"""
    if not is_configured():
        return []
    try:
        return _finnhub_get_company_news(ticker) or []
    except Exception:
        return []
