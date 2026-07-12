"""Declarative data-fetch requirements for user-visible analysis surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.services.analysis_context import DataResult


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
    data_result_names: tuple[str, ...] = ()

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
        data_result_names=("market_indices",),
    ),
    DataFetchRequirement(
        surface="market_options",
        name="index_option_horizons",
        provider="MarketData.app preferred, yfinance/cache fallback",
        required=True,
        max_stale_seconds=15 * 60,
        fallback="horizon-specific persistent cache",
        notes="Fetch current, 1W, and 1M expirations for SPY/QQQ/IWM.",
        data_result_names=("options",),
    ),
    DataFetchRequirement(
        surface="market_ai_recap",
        name="shared_market_context",
        provider="computed from MarketContext",
        required=True,
        max_stale_seconds=24 * 60 * 60,
        fallback="last successful MarketContext cache",
        notes="AI prompt must include data quality and provenance.",
        data_result_names=("market_indices",),
    ),
    DataFetchRequirement(
        surface="stock_analysis",
        name="price_history_profile",
        provider="yfinance/J-Quants/EDINET",
        required=True,
        max_stale_seconds=24 * 60 * 60,
        fallback="persistent history/profile cache; unavailable fields stay N/A",
        notes="Normal stock load keeps theme-option enrichment cache-only.",
        data_result_names=("stock_profile", "price_history"),
    ),
    DataFetchRequirement(
        surface="portfolio",
        name="position_quotes",
        provider="yfinance",
        required=True,
        max_stale_seconds=15 * 60,
        fallback="exclude unavailable quotes from market-value aggregation",
        notes="A missing quote must not become a real zero market value.",
        data_result_names=("position_quotes",),
    ),
    DataFetchRequirement(
        surface="news",
        name="company_news",
        provider="Finnhub/GNews",
        required=False,
        max_stale_seconds=24 * 60 * 60,
        fallback="empty news section with provider status",
        notes="News absence must not block quantitative analysis.",
        data_result_names=("news",),
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


def requirement_failures(surface: str, results: list[DataResult]) -> list[str]:
    """Return required dependency failures for one user-visible surface."""

    requirements = [
        item
        for item in DATA_FETCH_MANIFEST
        if item.surface == surface.strip().lower() and item.required
    ]
    by_name = {item.name: item for item in results}
    failures: list[str] = []
    for requirement in requirements:
        result_names = requirement.data_result_names or (requirement.name,)
        missing = [name for name in result_names if name not in by_name]
        if missing:
            failures.append(
                f"{requirement.name}: required status missing ({', '.join(missing)})"
            )
            continue
        degraded = [
            name
            for name in result_names
            if by_name[name].is_partial or bool(by_name[name].error)
        ]
        if degraded:
            failures.append(
                f"{requirement.name}: required dependency degraded ({', '.join(degraded)})"
            )
            continue
        expired = [
            name
            for name in result_names
            if by_name[name].is_stale
            and by_name[name].cache_age_seconds is not None
            and by_name[name].cache_age_seconds > requirement.max_stale_seconds
        ]
        if expired:
            failures.append(
                f"{requirement.name}: stale limit exceeded ({', '.join(expired)})"
            )
    return failures
