"""Theme-led next-leader discovery with verified external and fundamental evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, TypedDict
from urllib.parse import urlparse

import pandas as pd

from src.advisor.minervini_analyzer import analyze_stage, detect_vcp
from src.advisor.price_action_metrics import (
    atr_contraction,
    atr_series,
    ma_extension_atr,
    normalize_price_frame,
    period_returns,
    recent_pivot,
    relative_returns,
    relative_volume,
    rs_line_near_high,
    volume_contraction,
)
from src.log_config import get_logger
from src.persistent_cache import PersistentCacheRead, repo_state_cache
from src.provider_result import FetchResult
from src.services.batched_history_provider import fetch_batched_history
from src.services.fundamental_profile_service import evaluate_fundamental_profile
from src.services.theme_grounded_research_service import (
    ValidatedExternalTicker,
    discover_external_theme_tickers,
)
from src.services.trend_ranking_service import build_trend_ranking_context
from src.stock_data_provider import get_stock_info
from src.theme_measurement import get_theme_measurement_baskets
from src.themes_config import get_themes

logger = get_logger(__name__)

BENCHMARKS = {"US": "SPY", "JP": "1306.T"}
MIN_HISTORY_SESSIONS = 200
MIN_THEME_COVERAGE = 0.4
MAX_SELECTED_THEMES = 5
MAX_UNIVERSE_TICKERS = 40
MAX_REGISTERED_TICKERS = 20
MAX_EXTERNAL_TICKERS = 20
MAX_FUNDAMENTAL_PROFILES = 15
MAX_CANDIDATES = 10
MAX_FUNDAMENTAL_PENDING = 5
MIN_MEDIAN_DOLLAR_VOLUME = {"US": 2_000_000.0, "JP": 200_000_000.0}
DISCOVERY_CACHE_FRESH_SECONDS = 12 * 60 * 60
DISCOVERY_CACHE_STALE_SECONDS = 3 * 24 * 60 * 60
_DISCOVERY_CACHE = repo_state_cache("theme_leader_discovery")


class ThemeLeaderCandidate(TypedDict, total=False):
    """One research candidate backed only by theme ranking and OHLCV evidence."""

    ticker: str
    market_type: str
    primary_theme: str
    themes: list[str]
    status: str
    score: float
    research_priority_score: float
    candidate_source: str
    source_urls: list[str]
    source_titles: list[str]
    external_official_domain: str
    company_name: str
    fundamental_status: str
    fundamental_category: str
    fundamental_score: float
    fundamental_coverage: float
    fundamental_summary: str
    median_dollar_volume_20d: float
    stage_pass_count: int
    stage_total_count: int
    stage_conditions: list[dict[str, Any]]
    market_relative_20d: float
    market_relative_63d: float
    theme_relative_20d: float
    theme_relative_63d: float
    rs_line_near_high: bool
    vcp: bool
    atr_contraction: bool
    pivot_price: float
    pivot_distance_pct: float
    rvol: float
    volume_contraction: bool
    ma50_extension_atr: float
    rank: int
    rank_1w: int
    rank_1m: int
    rank_6m: int
    rank_acceleration: int
    coverage_1w: float
    coverage_1m: float
    coverage_6m: float
    performance_1w: float
    performance_1m: float
    performance_6m: float
    score_breakdown: dict[str, float]
    candidate_reason: str
    next_condition: str
    invalidation_condition: str
    data_quality: str
    fetched_at: str


class ThemeLeaderDiscoveryContext(TypedDict, total=False):
    """Serializable discovery result for the Theme page."""

    market_type: str
    benchmark: str
    status: str
    candidates: list[ThemeLeaderCandidate]
    fundamental_pending: list[ThemeLeaderCandidate]
    gemini_unverified: list[dict[str, Any]]
    gemini_status: str
    gemini_model: str
    gemini_input_tokens: int
    gemini_output_tokens: int
    gemini_total_tokens: int
    gemini_search_query_count: int
    gemini_cache_status: str
    selected_themes: list[dict[str, Any]]
    excluded_reasons: dict[str, int]
    warnings: list[str]
    fetched_at: str
    is_stale: bool
    is_partial: bool
    source: str
    universe_count: int
    fetched_count: int


def get_theme_leader_discovery_result(
    market_type: str = "US",
    themes: list[str] | None = None,
    *,
    force_refresh: bool = False,
) -> FetchResult[ThemeLeaderDiscoveryContext]:
    """Fetch one candidate OHLCV batch and return a cached discovery context."""

    market = market_type.upper()
    if market not in BENCHMARKS:
        return FetchResult(
            data=_empty_context(market, status="unavailable"),
            source="theme_leader_discovery",
            status="unavailable",
            error_code="unsupported_market",
        )

    requested_themes = sorted(
        {theme.strip() for theme in themes or [] if theme.strip()}
    )
    cache_key = _discovery_cache_key(market, requested_themes)
    cached = _DISCOVERY_CACHE.read(
        cache_key,
        fresh_seconds=DISCOVERY_CACHE_FRESH_SECONDS,
        stale_seconds=DISCOVERY_CACHE_STALE_SECONDS,
    )
    if cached.status == "fresh" and not force_refresh:
        return _result_from_cache(cached, stale=False)

    live = _build_live_discovery(
        market,
        themes=requested_themes or None,
        force_refresh=force_refresh,
    )
    if live.status in {"available", "partial"} and bool(
        live.data.get("candidates") or live.data.get("fundamental_pending")
    ):
        _DISCOVERY_CACHE.write(
            cache_key,
            {"context": live.data},
            fetched_at=live.fetched_at or None,
        )
        return live

    if cached.status == "stale":
        stale = _result_from_cache(cached, stale=True)
        previous_count = len(stale.data.get("candidates", [])) + len(
            stale.data.get("fundamental_pending", [])
        )
        stale.data["candidates"] = []
        stale.data["fundamental_pending"] = []
        stale.data["status"] = "stale_unavailable"
        stale.data["excluded_reasons"] = {
            **stale.data.get("excluded_reasons", {}),
            "古いキャッシュ": previous_count,
        }
        stale.warnings = list(
            dict.fromkeys(
                [
                    *stale.warnings,
                    *live.warnings,
                    "最新取得に失敗し、12時間を超えた前回結果は候補から除外しました。",
                ]
            )
        )
        stale.data["warnings"] = stale.warnings
        stale.error_code = live.error_code
        stale.error = live.error
        return stale
    return live


def get_cached_theme_leader_discovery_result(
    market_type: str = "US",
    themes: list[str] | None = None,
) -> FetchResult[ThemeLeaderDiscoveryContext]:
    """Read a fresh prior result without starting any provider or AI request."""

    market = market_type.upper()
    requested = sorted({theme.strip() for theme in themes or [] if theme.strip()})
    cached = _DISCOVERY_CACHE.read(
        _discovery_cache_key(market, requested),
        fresh_seconds=DISCOVERY_CACHE_FRESH_SECONDS,
        stale_seconds=DISCOVERY_CACHE_STALE_SECONDS,
    )
    if cached.status == "fresh":
        return _result_from_cache(cached, stale=False)
    return FetchResult(
        data=_empty_context(market, status="idle"),
        source="persistent_cache",
        status="unavailable",
        cache_status=cached.status,
        error_code="cache_miss",
    )


def _build_live_discovery(
    market_type: str,
    *,
    themes: list[str] | None = None,
    force_refresh: bool = False,
) -> FetchResult[ThemeLeaderDiscoveryContext]:
    ranking = build_trend_ranking_context(
        market_type,
        include_options=False,
        top_n=100,
    )
    selected = _selected_ranking_rows(ranking.get("items", []), themes)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if not selected:
        warning = "3期間の順位と必要取得率を満たすテーマがありません。"
        return FetchResult(
            data=_empty_context(
                market_type,
                status="unavailable",
                warnings=[warning, *ranking.get("quality_warnings", [])],
                fetched_at=fetched_at,
            ),
            source="theme_rankings",
            fetched_at=fetched_at,
            status="unavailable",
            warnings=[warning],
            error_code="insufficient_theme_coverage",
        )

    registered_memberships = _representative_memberships(market_type, selected)
    external = discover_external_theme_tickers(
        market_type,
        [str(row.get("theme") or "") for row in selected],
        force_refresh=force_refresh,
    )
    external_candidates = list(external.get("validated") or [])[:MAX_EXTERNAL_TICKERS]
    ticker_memberships = _merge_candidate_memberships(
        registered_memberships,
        external_candidates,
    )
    tickers = list(ticker_memberships)[:MAX_UNIVERSE_TICKERS]
    benchmark = BENCHMARKS[market_type]
    request_tickers = [*tickers]
    if benchmark not in request_tickers:
        request_tickers.append(benchmark)

    batch = fetch_batched_history(request_tickers, period="2y", timeout=20)
    if not batch.is_available:
        return FetchResult(
            data=_empty_context(
                market_type,
                status="unavailable",
                warnings=["候補銘柄の日足を取得できませんでした。"],
                fetched_at=fetched_at,
            ),
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            warnings=["候補銘柄の日足を取得できませんでした。"],
            error_code=batch.error_code,
            error=batch.error,
        )
    frames = dict(batch.data or {})
    benchmark_frame = frames.pop(benchmark, pd.DataFrame())
    context = build_theme_leader_discovery(
        market_type=market_type,
        ranking_rows=selected,
        price_frames=frames,
        benchmark_frame=benchmark_frame,
        ticker_memberships={ticker: ticker_memberships[ticker] for ticker in tickers},
        external_candidates=external_candidates,
        fetched_at=fetched_at,
        is_partial=len(frames) < len(tickers) or benchmark_frame.empty,
        candidate_limit=MAX_FUNDAMENTAL_PROFILES,
    )
    context = enrich_theme_leader_fundamentals(context, market_type=market_type)
    context["source"] = "yfinance_batch"
    warnings = list(
        dict.fromkeys(
            [
                *ranking.get("quality_warnings", []),
                *external.get("warnings", []),
                *batch.warnings,
                *context.get("warnings", []),
            ]
        )
    )
    context["warnings"] = warnings
    context["gemini_unverified"] = list(external.get("unverified") or [])
    context["gemini_status"] = str(external.get("status") or "unavailable")
    context["gemini_model"] = str(external.get("model") or "")
    context["gemini_input_tokens"] = int(external.get("input_tokens") or 0)
    context["gemini_output_tokens"] = int(external.get("output_tokens") or 0)
    context["gemini_total_tokens"] = int(external.get("total_tokens") or 0)
    context["gemini_search_query_count"] = int(external.get("search_query_count") or 0)
    context["gemini_cache_status"] = str(external.get("cache_status") or "")
    for reason, count in dict(external.get("excluded_reasons") or {}).items():
        context["excluded_reasons"][f"Gemini未検証: {reason}"] = int(count)
    available = bool(context.get("candidates"))
    pending_only = bool(context.get("fundamental_pending")) and not available
    partial = bool(context.get("is_partial"))
    return FetchResult(
        data=context,
        source="yfinance_batch",
        fetched_at=fetched_at,
        is_partial=partial,
        status="partial"
        if (partial and available) or pending_only
        else "available"
        if available
        else "unavailable",
        warnings=warnings,
        error_code="" if available or pending_only else "no_eligible_candidates",
    )


def select_candidate_themes(
    ranking_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select top integrated themes plus materially accelerating themes."""

    eligible = [row for row in ranking_rows if _theme_has_required_data(row)]
    integrated = sorted(eligible, key=lambda row: int(row.get("rank") or 10_000))[:3]
    accelerators = sorted(
        [row for row in eligible if int(row.get("rank_acceleration") or 0) >= 5],
        key=lambda row: (
            -int(row.get("rank_acceleration") or 0),
            int(row.get("rank_1w") or 10_000),
            str(row.get("theme") or ""),
        ),
    )[:2]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*integrated, *accelerators]:
        theme = str(row.get("theme") or "")
        if theme and theme not in seen:
            selected.append(dict(row))
            seen.add(theme)
    return selected[:MAX_SELECTED_THEMES]


def _selected_ranking_rows(
    ranking_rows: list[dict[str, Any]], themes: list[str] | None
) -> list[dict[str, Any]]:
    if not themes:
        return select_candidate_themes(ranking_rows)
    lookup = {str(row.get("theme") or ""): row for row in ranking_rows}
    return [
        dict(lookup[theme])
        for theme in themes[:MAX_SELECTED_THEMES]
        if theme in lookup and _theme_has_required_data(lookup[theme])
    ]


def _representative_memberships(
    market_type: str, selected: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Allocate registered representatives fairly across selected themes."""

    baskets = get_theme_measurement_baskets(market_type)
    theme_names = [str(row.get("theme") or "") for row in selected]
    by_theme = {
        theme: list(baskets.get(theme, {}).get("measurement_tickers") or [])
        for theme in theme_names
    }
    memberships: dict[str, list[str]] = {}
    positions = {theme: 0 for theme in theme_names}

    def add_one(theme: str) -> bool:
        tickers = by_theme[theme]
        while positions[theme] < len(tickers):
            ticker = tickers[positions[theme]]
            positions[theme] += 1
            if ticker not in memberships and len(memberships) >= MAX_REGISTERED_TICKERS:
                return False
            memberships.setdefault(ticker, [])
            if theme not in memberships[ticker]:
                memberships[ticker].append(theme)
            return True
        return False

    for _ in range(3):
        for theme in theme_names:
            add_one(theme)
    while len(memberships) < MAX_REGISTERED_TICKERS:
        added = False
        for theme in theme_names:
            added = add_one(theme) or added
            if len(memberships) >= MAX_REGISTERED_TICKERS:
                break
        if not added:
            break
    return memberships


def _merge_candidate_memberships(
    registered: dict[str, list[str]],
    external: list[ValidatedExternalTicker],
) -> dict[str, list[str]]:
    merged = {ticker: list(themes) for ticker, themes in registered.items()}
    for item in external[:MAX_EXTERNAL_TICKERS]:
        ticker = str(item.get("ticker") or "")
        if not ticker:
            continue
        merged.setdefault(ticker, [])
        for theme in item.get("themes", []):
            if theme not in merged[ticker]:
                merged[ticker].append(theme)
    return dict(list(merged.items())[:MAX_UNIVERSE_TICKERS])


def enrich_theme_leader_fundamentals(
    context: ThemeLeaderDiscoveryContext,
    *,
    market_type: str,
) -> ThemeLeaderDiscoveryContext:
    """Evaluate fundamentals only after the deterministic technical screen."""

    candidates = list(context.get("candidates") or [])[:MAX_FUNDAMENTAL_PROFILES]
    if not candidates:
        context["fundamental_pending"] = []
        return context
    results: dict[str, tuple[dict[str, Any], dict[str, Any] | None, str]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fetch_fundamental, item["ticker"], market_type): item
            for item in candidates
        }
        for future in as_completed(futures):
            ticker = futures[future]["ticker"]
            try:
                results[ticker] = future.result()
            except Exception as exc:
                logger.warning("Fundamental profile failed for %s: %s", ticker, exc)
                results[ticker] = ({}, None, str(exc))

    main: list[ThemeLeaderCandidate] = []
    pending: list[ThemeLeaderCandidate] = []
    excluded = Counter(context.get("excluded_reasons") or {})
    for candidate in candidates:
        info, profile, error = results.get(candidate["ticker"], ({}, None, ""))
        security_reason = _security_validation_reason(info)
        if security_reason:
            excluded[security_reason] += 1
            continue
        if candidate.get(
            "candidate_source"
        ) == "Gemini探索" and not _external_primary_domain_matches_profile(
            candidate, info
        ):
            excluded["外部一次資料ドメイン不一致"] += 1
            continue
        score = _finite_float((profile or {}).get("score"))
        coverage = _finite_float((profile or {}).get("coverage"))
        candidate["company_name"] = str(
            info.get("name") or candidate.get("company_name") or ""
        )
        candidate["fundamental_coverage"] = round((coverage or 0) * 100, 1)
        candidate["fundamental_summary"] = str(
            (profile or {}).get("summary") or error or "取得できませんでした。"
        )
        if score is None or coverage is None or coverage < 0.60:
            candidate["fundamental_status"] = "unavailable"
            candidate["fundamental_category"] = "ファンダメンタル確認待ち"
            pending.append(candidate)
            continue
        candidate["fundamental_score"] = round(score, 1)
        candidate["fundamental_status"] = str(
            (profile or {}).get("status") or "available"
        )
        if score < 40:
            excluded["ファンダメンタル裏付け不足"] += 1
            continue
        category = "研究優先" if score >= 55 else "技術先行"
        candidate["fundamental_category"] = category
        candidate["research_priority_score"] = round(
            float(candidate.get("score") or 0) * 0.70 + score * 0.30,
            1,
        )
        main.append(candidate)

    main.sort(
        key=lambda item: (
            -float(item.get("research_priority_score") or 0),
            -int(item.get("stage_pass_count") or 0),
            -float(item.get("market_relative_63d") or 0),
            item["ticker"],
        )
    )
    context["candidates"] = main[:MAX_CANDIDATES]
    context["fundamental_pending"] = pending[:MAX_FUNDAMENTAL_PENDING]
    context["excluded_reasons"] = dict(sorted(excluded.items()))
    if context["candidates"]:
        context["status"] = "partial" if context.get("is_partial") else "available"
    elif pending:
        context["status"] = "fundamental_pending"
    else:
        context["status"] = "no_candidates"
    return context


def _fetch_fundamental(
    ticker: str, market_type: str
) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    try:
        info = dict(
            get_stock_info(
                ticker,
                include_summary=False,
                translate_summary=False,
            )
        )
        profile = evaluate_fundamental_profile(
            ticker,
            info,
            market_type=market_type,
        )
        return info, profile, ""
    except Exception as exc:
        return {}, None, str(exc)


def _security_validation_reason(info: dict[str, Any]) -> str:
    exchange = str(info.get("exchange") or "").upper()
    if "OTC" in exchange or "PINK" in exchange:
        return "対象外市場またはOTC"
    quote_type = str(info.get("quote_type") or "").upper()
    if quote_type and quote_type not in {"EQUITY", "STOCK"}:
        return "ETF・投資信託等"
    return ""


def _external_primary_domain_matches_profile(
    candidate: ThemeLeaderCandidate, info: dict[str, Any]
) -> bool:
    regulatory = {
        "sec.gov",
        "www.sec.gov",
        "edinet-fsa.go.jp",
        "disclosure2.edinet-fsa.go.jp",
        "jpx.co.jp",
        "www.jpx.co.jp",
        "nasdaq.com",
        "www.nasdaq.com",
        "nyse.com",
        "www.nyse.com",
    }
    source_hosts = {
        urlparse(url).netloc.lower().split(":", 1)[0]
        for url in candidate.get("source_urls", [])
    }
    if source_hosts & regulatory:
        return True
    website = str(info.get("website") or "")
    website_host = (
        urlparse(website).netloc.lower().split(":", 1)[0].removeprefix("www.")
    )
    if not website_host:
        return False
    return any(
        host.removeprefix("www.") == website_host
        or host.removeprefix("www.").endswith(f".{website_host}")
        for host in source_hosts
    )


def build_theme_leader_discovery(
    *,
    market_type: str,
    ranking_rows: list[dict[str, Any]],
    price_frames: dict[str, pd.DataFrame],
    benchmark_frame: pd.DataFrame,
    ticker_memberships: dict[str, list[str]] | None = None,
    external_candidates: list[ValidatedExternalTicker] | None = None,
    fetched_at: str = "",
    is_stale: bool = False,
    is_partial: bool = False,
    candidate_limit: int = MAX_CANDIDATES,
) -> ThemeLeaderDiscoveryContext:
    """Build discovery deterministically from supplied rankings and OHLCV frames."""

    selected = select_candidate_themes(ranking_rows)
    benchmark = BENCHMARKS.get(market_type, "")
    warnings: list[str] = []
    excluded: Counter[str] = Counter()
    benchmark_prices = normalize_price_frame(benchmark_frame)
    if len(benchmark_prices) < 64:
        warnings.append("市場ベンチマークの履歴が不足しています。")

    theme_rows = {str(row.get("theme")): row for row in selected}
    memberships = ticker_memberships or _ticker_memberships(market_type, selected)
    external_lookup = {
        str(item.get("ticker") or ""): item for item in (external_candidates or [])
    }
    theme_returns = _theme_return_medians(memberships, price_frames)
    candidates: list[ThemeLeaderCandidate] = []

    for ticker, themes in memberships.items():
        stock = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
        if is_stale:
            excluded["古いキャッシュ"] += 1
            continue
        if len(stock) < MIN_HISTORY_SESSIONS:
            excluded["履歴不足"] += 1
            continue
        if len(benchmark_prices) < 64:
            excluded["市場ベンチマーク不足"] += 1
            continue

        stage = analyze_stage(stock)
        pass_count = int(stage.get("stage2_pass_count") or 0)
        if int(stage.get("stage") or 0) in {3, 4}:
            excluded["ステージ3/4"] += 1
            continue
        if stage.get("ma200_rising") is not True:
            excluded["200日線下降"] += 1
            continue
        if pass_count < 6:
            excluded["ステージ2条件不足"] += 1
            continue

        close = stock["Close"].astype(float)
        high = stock["High"].astype(float)
        low = stock["Low"].astype(float)
        volume = stock["Volume"].astype(float)
        median_dollar_volume = _finite_float((close * volume).tail(20).median())
        if (
            median_dollar_volume is None
            or median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME[market_type]
        ):
            excluded["低流動性"] += 1
            continue
        market_rs = relative_returns(
            close,
            benchmark_prices["Close"].astype(float),
            periods=(20, 63),
        )
        if (
            "20d" not in market_rs
            or "63d" not in market_rs
            or market_rs["20d"] <= 0
            or market_rs["63d"] <= 0
        ):
            excluded["市場相対強度不足"] += 1
            continue

        primary_theme = min(
            themes,
            key=lambda name: int(theme_rows[name].get("rank") or 10_000),
        )
        theme_rs = _theme_relative_returns(
            close,
            theme_returns,
            primary_theme,
        )
        if theme_rs is None:
            excluded["テーマ相対強度不足"] += 1
            continue
        if theme_rs["20d"] <= 0 and theme_rs["63d"] <= 0:
            excluded["テーマ相対強度不足"] += 1
            continue

        atr_values = atr_series(high, low, close)
        atr = _finite_float(atr_values.iloc[-1])
        ma50 = _finite_float(close.rolling(50).mean().iloc[-1])
        current = _finite_float(close.iloc[-1])
        if atr is None or atr <= 0 or ma50 is None or current is None:
            excluded["必須データ欠損"] += 1
            continue
        extension = ma_extension_atr(current, ma50, atr)
        if extension is None:
            excluded["必須データ欠損"] += 1
            continue
        if extension > 4:
            excluded["過熱"] += 1
            continue

        pivot = recent_pivot(high, lookback=50)
        if pivot is None or pivot <= 0:
            excluded["節目判定不能"] += 1
            continue
        pivot_distance = (current / pivot - 1) * 100
        rvol = relative_volume(volume, lookback=50)
        if rvol is None:
            excluded["出来高不足"] += 1
            continue
        status = _candidate_status(pass_count, pivot_distance, rvol)
        if not status:
            reason = (
                "節目待ち"
                if pivot_distance < -5
                else "出来高確認待ち"
                if 0 < pivot_distance <= 2 and rvol < 1.5
                else "過熱"
                if pivot_distance > 2
                else "節目条件外"
            )
            excluded[reason] += 1
            continue

        vcp, _ = detect_vcp(stock)
        is_atr_contraction = atr_contraction(atr_values)
        is_volume_contraction = volume_contraction(volume)
        rs_near_high = rs_line_near_high(
            close,
            benchmark_prices["Close"],
            threshold=0.98,
            min_sessions=200,
        )
        row = theme_rows[primary_theme]
        score_parts = _score_candidate(
            row=row,
            pass_count=pass_count,
            market_rs=market_rs,
            theme_rs=theme_rs,
            rs_near_high=rs_near_high,
            vcp=vcp,
            atr_contraction=is_atr_contraction,
            pivot_distance=pivot_distance,
            volume_contraction=is_volume_contraction,
            rvol=rvol,
        )
        candidate = _candidate_payload(
            ticker=ticker,
            market_type=market_type,
            themes=themes,
            primary_theme=primary_theme,
            status=status,
            row=row,
            stage=stage,
            market_rs=market_rs,
            theme_rs=theme_rs,
            rs_near_high=rs_near_high,
            vcp=vcp,
            atr_contraction=is_atr_contraction,
            pivot=pivot,
            pivot_distance=pivot_distance,
            rvol=rvol,
            volume_contraction=is_volume_contraction,
            extension=extension,
            score_parts=score_parts,
            median_dollar_volume=median_dollar_volume,
            external_candidate=external_lookup.get(ticker),
            fetched_at=fetched_at,
            is_partial=is_partial,
        )
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            -float(item["score"]),
            -int(item["stage_pass_count"]),
            -float(item["market_relative_63d"]),
            item["ticker"],
        )
    )
    status = "available" if candidates else "no_candidates"
    if is_stale:
        status = "stale_unavailable"
    elif is_partial:
        status = "partial"
        warnings.append(
            "一部銘柄の日足を取得できず、取得できた銘柄だけで判定しました。"
        )
    return {
        "market_type": market_type,
        "benchmark": benchmark,
        "status": status,
        "candidates": candidates[:candidate_limit],
        "fundamental_pending": [],
        "gemini_unverified": [],
        "selected_themes": [_theme_summary(row) for row in selected],
        "excluded_reasons": dict(sorted(excluded.items())),
        "warnings": warnings,
        "fetched_at": fetched_at,
        "is_stale": is_stale,
        "is_partial": is_partial,
        "source": "supplied_ohlcv",
        "universe_count": len(memberships),
        "fetched_count": sum(
            1
            for ticker in memberships
            if not normalize_price_frame(price_frames.get(ticker, pd.DataFrame())).empty
        ),
    }


def _candidate_payload(
    *,
    ticker: str,
    market_type: str,
    themes: list[str],
    primary_theme: str,
    status: str,
    row: dict[str, Any],
    stage: dict[str, Any],
    market_rs: dict[str, float],
    theme_rs: dict[str, float],
    rs_near_high: bool,
    vcp: bool,
    atr_contraction: bool,
    pivot: float,
    pivot_distance: float,
    rvol: float,
    volume_contraction: bool,
    extension: float,
    score_parts: dict[str, float],
    median_dollar_volume: float,
    external_candidate: ValidatedExternalTicker | None,
    fetched_at: str,
    is_partial: bool,
) -> ThemeLeaderCandidate:
    score = round(sum(score_parts.values()), 1)
    next_condition = (
        "残るステージ2条件と節目接近を確認"
        if status == "ステージ2移行待ち"
        else "節目突破時にRVOL 1.5倍以上を確認"
        if status == "ブレイク準備"
        else "節目上を維持し、出来高が失速しないか確認"
    )
    reason = (
        f"{primary_theme}（統合{int(row.get('rank') or 0)}位）で、"
        f"ステージ2条件{int(stage.get('stage2_pass_count') or 0)}/7、"
        f"市場比63日 {market_rs['63d']:+.1f}%です。"
    )
    invalidation = (
        "200日線が下降へ転じる、ステージ3/4へ移行する、市場比20日または63日が0以下になる、"
        "または50日線から4 ATR超に過熱した場合。"
    )
    return {
        "ticker": ticker,
        "candidate_source": "Gemini探索" if external_candidate else "登録代表",
        "source_urls": list((external_candidate or {}).get("source_urls") or []),
        "source_titles": list((external_candidate or {}).get("source_titles") or []),
        "external_official_domain": str(
            (external_candidate or {}).get("official_domain") or ""
        ),
        "company_name": str((external_candidate or {}).get("company_name") or ""),
        "market_type": market_type,
        "primary_theme": primary_theme,
        "themes": themes,
        "status": status,
        "score": score,
        "stage_pass_count": int(stage.get("stage2_pass_count") or 0),
        "stage_total_count": 7,
        "stage_conditions": list(stage.get("conditions") or []),
        "market_relative_20d": round(market_rs["20d"], 2),
        "market_relative_63d": round(market_rs["63d"], 2),
        "theme_relative_20d": round(theme_rs["20d"], 2),
        "theme_relative_63d": round(theme_rs["63d"], 2),
        "rs_line_near_high": rs_near_high,
        "vcp": vcp,
        "atr_contraction": atr_contraction,
        "pivot_price": round(pivot, 2),
        "pivot_distance_pct": round(pivot_distance, 2),
        "rvol": round(rvol, 2),
        "volume_contraction": volume_contraction,
        "ma50_extension_atr": round(extension, 2),
        "median_dollar_volume_20d": round(median_dollar_volume, 0),
        "rank": int(row.get("rank") or 0),
        "rank_1w": int(row.get("rank_1w") or 0),
        "rank_1m": int(row.get("rank_1m") or 0),
        "rank_6m": int(row.get("rank_6m") or 0),
        "rank_acceleration": int(row.get("rank_acceleration") or 0),
        "coverage_1w": round(float(row.get("coverage_1w") or 0) * 100, 1),
        "coverage_1m": round(float(row.get("coverage_1m") or 0) * 100, 1),
        "coverage_6m": round(float(row.get("coverage_6m") or 0) * 100, 1),
        "performance_1w": round(float(row.get("performance_1w") or 0), 2),
        "performance_1m": round(float(row.get("performance_1m") or 0), 2),
        "performance_6m": round(float(row.get("performance_6m") or 0), 2),
        "score_breakdown": score_parts,
        "candidate_reason": reason,
        "next_condition": next_condition,
        "invalidation_condition": invalidation,
        "data_quality": "部分取得" if is_partial else "必要履歴を取得",
        "fetched_at": fetched_at,
    }


def _score_candidate(
    *,
    row: dict[str, Any],
    pass_count: int,
    market_rs: dict[str, float],
    theme_rs: dict[str, float],
    rs_near_high: bool,
    vcp: bool,
    atr_contraction: bool,
    pivot_distance: float,
    volume_contraction: bool,
    rvol: float,
) -> dict[str, float]:
    rank = int(row.get("rank") or 10_000)
    rank_score = (
        10.0 if rank <= 3 else 6.0 if rank <= 10 else 3.0 if rank <= 20 else 0.0
    )
    positive_periods = sum(
        1
        for key in ("performance_1w", "performance_1m", "performance_6m")
        if float(row.get(key) or 0) > 0
    )
    acceleration = max(0, int(row.get("rank_acceleration") or 0))
    theme_score = rank_score + positive_periods * 2.0 + min(acceleration / 10 * 9, 9)
    stage_score = 30 * pass_count / 7
    rs_score = (
        (6 if market_rs["20d"] > 0 else 0)
        + (6 if market_rs["63d"] > 0 else 0)
        + (6 if theme_rs["20d"] > 0 else 0)
        + (6 if theme_rs["63d"] > 0 else 0)
        + (1 if rs_near_high else 0)
    )
    setup_score = (
        (5 if vcp else 0)
        + (5 if atr_contraction else 0)
        + (5 if -5 <= pivot_distance <= 2 else 0)
        + (5 if volume_contraction or rvol >= 1.5 else 0)
    )
    return {
        "theme_strength": round(min(theme_score, 25), 1),
        "stage2_fit": round(stage_score, 1),
        "relative_strength": round(rs_score, 1),
        "setup_readiness": round(setup_score, 1),
    }


def _theme_has_required_data(row: dict[str, Any]) -> bool:
    required = (
        "rank",
        "rank_1w",
        "rank_1m",
        "rank_6m",
        "performance_1w",
        "performance_1m",
        "performance_6m",
        "coverage_1w",
        "coverage_1m",
        "coverage_6m",
    )
    if any(row.get(key) is None for key in required):
        return False
    return all(
        float(row.get(key) or 0) >= MIN_THEME_COVERAGE
        for key in ("coverage_1w", "coverage_1m", "coverage_6m")
    )


def _candidate_universe(market_type: str, selected: list[dict[str, Any]]) -> list[str]:
    themes = get_themes(market_type)
    result: list[str] = []
    seen: set[str] = set()
    for row in selected:
        for ticker in themes.get(str(row.get("theme") or ""), []):
            if ticker not in seen:
                result.append(ticker)
                seen.add(ticker)
            if len(result) >= MAX_UNIVERSE_TICKERS:
                return result
    return result


def _ticker_memberships(
    market_type: str, selected: list[dict[str, Any]]
) -> dict[str, list[str]]:
    themes = get_themes(market_type)
    allowed_tickers = _candidate_universe(market_type, selected)
    memberships: dict[str, list[str]] = {ticker: [] for ticker in allowed_tickers}
    for row in selected:
        theme = str(row.get("theme") or "")
        theme_tickers = set(themes.get(theme, []))
        for ticker in allowed_tickers:
            if ticker in theme_tickers:
                memberships[ticker].append(theme)
    return dict(memberships)


def _theme_return_medians(
    memberships: dict[str, list[str]],
    price_frames: dict[str, pd.DataFrame],
) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"20d": [], "63d": []}
    )
    for ticker, themes in memberships.items():
        frame = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
        if len(frame) < 64:
            continue
        returns = period_returns(frame["Close"].astype(float), periods=(20, 63))
        if "20d" not in returns or "63d" not in returns:
            continue
        for theme in themes:
            values[theme]["20d"].append(returns["20d"])
            values[theme]["63d"].append(returns["63d"])
    return {
        theme: {
            period: float(pd.Series(period_values).median())
            for period, period_values in by_period.items()
            if period_values
        }
        for theme, by_period in values.items()
    }


def _theme_relative_returns(
    close: pd.Series,
    medians: dict[str, dict[str, float]],
    primary_theme: str,
) -> dict[str, float] | None:
    stock_returns = period_returns(close, periods=(20, 63))
    primary = medians.get(primary_theme, {})
    if (
        "20d" not in stock_returns
        or "63d" not in stock_returns
        or "20d" not in primary
        or "63d" not in primary
    ):
        return None
    return {
        "20d": stock_returns["20d"] - primary["20d"],
        "63d": stock_returns["63d"] - primary["63d"],
    }


def _candidate_status(pass_count: int, pivot_distance: float, rvol: float) -> str:
    if pass_count == 6 and pivot_distance < 0:
        return "ステージ2移行待ち"
    if pass_count == 7 and -5 <= pivot_distance <= 0:
        return "ブレイク準備"
    if pass_count == 7 and 0 <= pivot_distance <= 2 and rvol >= 1.5:
        return "ブレイク確認"
    return ""


def _extract_ticker_frame(
    raw: pd.DataFrame, ticker: str, request_tickers: list[str]
) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy() if len(request_tickers) == 1 else pd.DataFrame()
    level_zero = raw.columns.get_level_values(0)
    level_one = raw.columns.get_level_values(1)
    if ticker in level_zero:
        return raw[ticker].copy()
    if ticker in level_one:
        return raw.xs(ticker, axis=1, level=1).copy()
    return pd.DataFrame()


def _theme_summary(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "theme",
        "rank",
        "rank_1w",
        "rank_1m",
        "rank_6m",
        "rank_acceleration",
        "coverage_1w",
        "coverage_1m",
        "coverage_6m",
    )
    return {key: row.get(key) for key in keys}


def _empty_context(
    market_type: str,
    *,
    status: str,
    warnings: list[str] | None = None,
    fetched_at: str = "",
) -> ThemeLeaderDiscoveryContext:
    return {
        "market_type": market_type,
        "benchmark": BENCHMARKS.get(market_type, ""),
        "status": status,
        "candidates": [],
        "fundamental_pending": [],
        "gemini_unverified": [],
        "gemini_status": "idle",
        "gemini_model": "",
        "gemini_input_tokens": 0,
        "gemini_output_tokens": 0,
        "gemini_total_tokens": 0,
        "gemini_search_query_count": 0,
        "gemini_cache_status": "",
        "selected_themes": [],
        "excluded_reasons": {},
        "warnings": warnings or [],
        "fetched_at": fetched_at,
        "is_stale": False,
        "is_partial": False,
        "source": "theme_leader_discovery",
        "universe_count": 0,
        "fetched_count": 0,
    }


def _discovery_cache_key(market_type: str, themes: list[str]) -> str:
    suffix = "__".join(sorted(themes)) if themes else "automatic"
    return f"{market_type}__{suffix}"


def _result_from_cache(
    cached: PersistentCacheRead, *, stale: bool
) -> FetchResult[ThemeLeaderDiscoveryContext]:
    raw = cached.payload.get("context")
    context = (
        dict(raw) if isinstance(raw, dict) else _empty_context("", status="unavailable")
    )
    context["is_stale"] = stale
    context["source"] = "persistent_cache"
    context["fetched_at"] = str(context.get("fetched_at") or cached.fetched_at)
    warnings = list(context.get("warnings") or [])
    return FetchResult(
        data=context,
        source="persistent_cache",
        fetched_at=str(context.get("fetched_at") or cached.fetched_at),
        is_stale=stale,
        is_partial=bool(context.get("is_partial")) or stale,
        cache_status="stale_cache" if stale else "persistent_cache",
        cache_age_seconds=cached.age_seconds,
        status="partial" if stale else str(context.get("status") or "available"),
        warnings=warnings,
    )


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None
