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
        surface="theme_ranking",
        name="measurement_ohlcv",
        provider="yfinance single batch",
        required=True,
        max_stale_seconds=12 * 60 * 60,
        fallback="exclude themes below 60% coverage; never zero-fill missing components",
        notes="Versioned audited representatives, ETF proxies, and the market benchmark share one batch.",
        data_result_names=("measurement_ohlcv",),
    ),
    DataFetchRequirement(
        surface="theme_ranking",
        name="market_benchmark",
        provider="yfinance single batch",
        required=True,
        max_stale_seconds=12 * 60 * 60,
        fallback="return no comprehensive ranks when SPY or 1306.T is insufficient",
        notes="Required for 20-day and 63-day market relative strength.",
        data_result_names=("market_benchmark",),
    ),
    DataFetchRequirement(
        surface="theme_leader_discovery",
        name="theme_rankings",
        provider="comprehensive theme ranking cache",
        required=True,
        max_stale_seconds=12 * 60 * 60,
        fallback="do not select themes when any 1W/1M/6M rank or coverage is missing",
        notes="All three horizons must meet 60% coverage and the theme remains unscored when evidence is missing.",
        data_result_names=("theme_rankings",),
    ),
    DataFetchRequirement(
        surface="theme_leader_discovery",
        name="candidate_ohlcv",
        provider="yfinance single batch",
        required=True,
        max_stale_seconds=12 * 60 * 60,
        fallback="exclude unavailable tickers and report partial coverage",
        notes="At most 40 deduplicated registered and source-verified external stocks; no news or option fetches.",
        data_result_names=("candidate_ohlcv",),
    ),
    DataFetchRequirement(
        surface="theme_leader_discovery",
        name="market_benchmark",
        provider="yfinance single batch",
        required=True,
        max_stale_seconds=12 * 60 * 60,
        fallback="return no candidates when SPY or 1306.T history is insufficient",
        notes="The benchmark is fetched in the same batch as candidate OHLCV.",
        data_result_names=("market_benchmark",),
    ),
    DataFetchRequirement(
        surface="theme_leader_discovery",
        name="gemini_external_universe",
        provider="Gemini Interactions API + Google Search",
        required=False,
        max_stale_seconds=24 * 60 * 60,
        fallback="continue with registered representatives only",
        notes="One manual structured request; only annotation-cited URLs may validate a candidate.",
        data_result_names=("gemini_external_universe",),
    ),
    DataFetchRequirement(
        surface="theme_leader_discovery",
        name="fundamental_profiles",
        provider="yfinance/J-Quants/EDINET",
        required=False,
        max_stale_seconds=24 * 60 * 60,
        fallback="show technical survivors as fundamental confirmation pending",
        notes="Maximum 15 post-technical profiles, three concurrent, without AI summary translation.",
        data_result_names=("fundamental_profiles",),
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
        provider="Finnhub",
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
