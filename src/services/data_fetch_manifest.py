"""Declarative data-fetch requirements for user-visible analysis surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DataFetchRequirement:
    """One required or optional external-data dependency."""

    surface: str
    name: str
    provider: str
    required: bool
    max_stale_seconds: int
    fallback: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DATA_FETCH_MANIFEST: tuple[DataFetchRequirement, ...] = (
    DataFetchRequirement(
        surface="market_summary",
        name="market_indices",
        provider="yfinance/finnhub",
        required=True,
        max_stale_seconds=15 * 60,
        fallback="persistent_cache; omit unavailable symbols",
        notes="Do not emit zero-valued index rows for unavailable quotes.",
    ),
    DataFetchRequirement(
        surface="market_options",
        name="index_option_horizons",
        provider="MarketData.app preferred, yfinance/cache fallback",
        required=True,
        max_stale_seconds=15 * 60,
        fallback="horizon-specific persistent cache",
        notes="Fetch current, 1W, and 1M expirations for SPY/QQQ/IWM.",
    ),
    DataFetchRequirement(
        surface="market_ai_recap",
        name="shared_market_context",
        provider="computed from MarketContext",
        required=True,
        max_stale_seconds=24 * 60 * 60,
        fallback="last successful MarketContext cache",
        notes="AI prompt must include data quality and provenance.",
    ),
    DataFetchRequirement(
        surface="stock_analysis",
        name="price_history_profile",
        provider="yfinance/J-Quants/EDINET",
        required=True,
        max_stale_seconds=24 * 60 * 60,
        fallback="persistent history/profile cache; unavailable fields stay N/A",
        notes="Normal stock load keeps theme-option enrichment cache-only.",
    ),
    DataFetchRequirement(
        surface="portfolio",
        name="position_quotes",
        provider="yfinance",
        required=True,
        max_stale_seconds=15 * 60,
        fallback="exclude unavailable quotes from market-value aggregation",
        notes="A missing quote must not become a real zero market value.",
    ),
    DataFetchRequirement(
        surface="news",
        name="company_news",
        provider="Finnhub/GNews",
        required=False,
        max_stale_seconds=24 * 60 * 60,
        fallback="empty news section with provider status",
        notes="News absence must not block quantitative analysis.",
    ),
)


def get_data_fetch_manifest(surface: str | None = None) -> list[dict[str, Any]]:
    """Return manifest rows, optionally filtered by surface."""

    rows = DATA_FETCH_MANIFEST
    if surface:
        normalized = surface.strip().lower()
        rows = tuple(item for item in rows if item.surface == normalized)
    return [item.to_dict() for item in rows]


def required_data_names(surface: str) -> list[str]:
    """Return required dependency names for a surface."""

    normalized = surface.strip().lower()
    return [
        item.name
        for item in DATA_FETCH_MANIFEST
        if item.surface == normalized and item.required
    ]
