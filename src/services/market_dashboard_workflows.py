"""FOMO, option, and derived market-monitor workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.advisor.fomo_volatility_regime import (
    DEFAULT_FOMO_UNIVERSE,
)
from src.advisor.fomo_volatility_regime import (
    scan_fomo_universe as _default_scan_fomo_universe,
)
from src.advisor.market_environment import (
    evaluate_market_environment as _default_evaluate_market_environment,
)
from src.advisor.market_monitor import (
    detect_market_climax as _default_detect_market_climax,
)
from src.advisor.market_monitor import (
    evaluate_yield_spread as _default_evaluate_yield_spread,
)
from src.advisor.market_monitor import (
    track_distribution_days as _default_track_distribution_days,
)
from src.market_data import get_stock_data as _default_get_stock_data
from src.market_microstructure import (
    analyze_market_structure as _default_analyze_market_structure,
)
from src.services import market_dashboard_service as _service
from src.services.analysis_context import DataResult, MarketContext
from src.services.data_fetch_manifest import (
    requirement_failures as _default_requirement_failures,
)
from src.services.market_composite_sentiment import (
    build_market_composite_sentiment as _default_build_market_composite_sentiment,
)
from src.services.market_dashboard_service import (
    build_market_high_context as _default_build_market_high_context,
)
from src.services.market_dashboard_service import (
    build_market_summary_context as _default_build_market_summary_context,
)
from src.services.market_dashboard_service import (
    build_market_theme_flow_context as _default_build_market_theme_flow_context,
)
from src.services.market_dashboard_service import (
    build_market_volatility_sentiment_context as _default_build_market_volatility_sentiment_context,
)
from src.services.market_dashboard_support import (
    _build_option_context,
    _coerce_context,
    _extract_pe,
    _extract_spy_pcr,
    _merge_ibd_signal,
    _merge_provenance,
    _merge_warnings,
    _normalize_microstructure,
    _option_item,
    _replace_data_status,
    _run_stage_tasks,
    _safe_call,
    _save_context_cache,
    _stage_task_values,
    _updated_stage_statuses,
    _utc_now,
)
from src.services.market_strategy_service import (
    build_market_strategy_context as _default_build_market_strategy_context,
)
from src.services.provenance_service import (
    option_provenance as _default_option_provenance,
)
from src.services.trend_ranking_service import (
    build_opportunity_themes as _default_build_opportunity_themes,
)
from src.services.trend_ranking_service import (
    build_trend_ranking_context as _default_build_trend_ranking_context,
)
from src.stock_data_provider import (
    get_valuation_metrics as _default_get_valuation_metrics,
)


@dataclass(frozen=True, slots=True)
class MarketDashboardWorkflowDependencies:
    """Explicit orchestration dependencies for market workflows."""

    scan_fomo_universe: Callable[..., dict[str, Any]]
    get_stock_data: Callable[..., Any]
    build_market_summary_context: Callable[..., MarketContext]
    build_market_theme_flow_context: Callable[..., MarketContext]
    build_market_high_context: Callable[..., MarketContext]
    build_market_volatility_sentiment_context: Callable[..., MarketContext]
    build_market_options_context: Callable[..., MarketContext]
    build_option_context: Callable[..., Any]
    analyze_market_structure: Callable[..., dict[str, Any]]
    build_market_monitor_context: Callable[..., dict[str, Any]]
    evaluate_market_environment: Callable[..., dict[str, Any]]
    build_trend_ranking_context: Callable[..., dict[str, Any]]
    build_opportunity_themes: Callable[..., dict[str, Any]]
    build_market_composite_sentiment: Callable[..., dict[str, Any]]
    build_market_strategy_context: Callable[..., dict[str, Any]]
    option_provenance: Callable[..., list[Any]]
    requirement_failures: Callable[..., list[str]]
    save_context_cache: Callable[..., None]
    track_distribution_days: Callable[..., dict[str, Any]]
    detect_market_climax: Callable[..., dict[str, Any]]
    get_valuation_metrics: Callable[..., dict[str, Any]]
    evaluate_yield_spread: Callable[..., dict[str, Any]]


def _facade_dependency(name: str, default: Callable[..., Any]) -> Callable[..., Any]:
    """Resolve one explicitly named compatibility patch from the facade."""

    candidate = getattr(_service, name, default)
    return candidate if callable(candidate) else default


def _workflow_dependencies(
    dependencies: MarketDashboardWorkflowDependencies | None = None,
) -> MarketDashboardWorkflowDependencies:
    """Build a stable dependency object while honoring legacy test patches."""

    if dependencies is not None:
        return dependencies

    return MarketDashboardWorkflowDependencies(
        scan_fomo_universe=_facade_dependency(
            "scan_fomo_universe", _default_scan_fomo_universe
        ),
        get_stock_data=_facade_dependency("get_stock_data", _default_get_stock_data),
        build_market_summary_context=_facade_dependency(
            "build_market_summary_context", _default_build_market_summary_context
        ),
        build_market_theme_flow_context=_facade_dependency(
            "build_market_theme_flow_context",
            _default_build_market_theme_flow_context,
        ),
        build_market_high_context=_facade_dependency(
            "build_market_high_context", _default_build_market_high_context
        ),
        build_market_volatility_sentiment_context=_facade_dependency(
            "build_market_volatility_sentiment_context",
            _default_build_market_volatility_sentiment_context,
        ),
        build_market_options_context=_facade_dependency(
            "build_market_options_context", build_market_options_context
        ),
        build_option_context=_facade_dependency(
            "_build_option_context", _build_option_context
        ),
        analyze_market_structure=_facade_dependency(
            "analyze_market_structure", _default_analyze_market_structure
        ),
        build_market_monitor_context=_facade_dependency(
            "build_market_monitor_context", build_market_monitor_context
        ),
        evaluate_market_environment=_facade_dependency(
            "evaluate_market_environment", _default_evaluate_market_environment
        ),
        build_trend_ranking_context=_facade_dependency(
            "build_trend_ranking_context", _default_build_trend_ranking_context
        ),
        build_opportunity_themes=_facade_dependency(
            "build_opportunity_themes", _default_build_opportunity_themes
        ),
        build_market_composite_sentiment=_facade_dependency(
            "build_market_composite_sentiment",
            _default_build_market_composite_sentiment,
        ),
        build_market_strategy_context=_facade_dependency(
            "build_market_strategy_context", _default_build_market_strategy_context
        ),
        option_provenance=_facade_dependency(
            "option_provenance", _default_option_provenance
        ),
        requirement_failures=_facade_dependency(
            "requirement_failures", _default_requirement_failures
        ),
        save_context_cache=_facade_dependency(
            "_save_context_cache", _save_context_cache
        ),
        track_distribution_days=_facade_dependency(
            "track_distribution_days", _default_track_distribution_days
        ),
        detect_market_climax=_facade_dependency(
            "detect_market_climax", _default_detect_market_climax
        ),
        get_valuation_metrics=_facade_dependency(
            "get_valuation_metrics", _default_get_valuation_metrics
        ),
        evaluate_yield_spread=_facade_dependency(
            "evaluate_yield_spread", _default_evaluate_yield_spread
        ),
    )


def build_fomo_scan_context(
    tickers: list[str] | None = None,
    *,
    dependencies: MarketDashboardWorkflowDependencies | None = None,
) -> dict[str, Any]:
    """Run the explicit, bounded high-volatility watchlist scan."""

    deps = _workflow_dependencies(dependencies)
    return deps.scan_fomo_universe(
        deps.get_stock_data, tickers or DEFAULT_FOMO_UNIVERSE
    )


def build_market_options_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
    *,
    dependencies: MarketDashboardWorkflowDependencies | None = None,
) -> MarketContext:
    """Refresh option data and option-dependent monitoring without reloading all data."""

    deps = _workflow_dependencies(dependencies)
    base = _coerce_context(market_context) or deps.build_market_summary_context(
        market_type
    )
    errors: list[str] = []
    options = deps.build_option_context(market_type)
    if options.error_message:
        errors.append(options.error_message)

    def microstructure_task() -> dict[str, Any]:
        return _normalize_microstructure(
            deps.analyze_market_structure(
                "SPY",
                _option_item(options.items, "SPY") or {},
                allow_option_fetch=False,
            )
        )

    def monitor_task() -> dict[str, Any]:
        return deps.build_market_monitor_context(options.items)

    results = _stage_task_values(
        _run_stage_tasks(
            {
                "microstructure": microstructure_task,
                "monitor": monitor_task,
            },
            errors,
            stage_name="options",
            max_workers=2,
        )
    )
    microstructure = results.get("microstructure") or base.microstructure
    raw_evaluation = _safe_call(
        lambda: deps.evaluate_market_environment(
            market_type,
            options.items,
            microstructure=microstructure,
            allow_microstructure_fetch=False,
        ),
        base.evaluation,
        errors,
    )
    evaluation = _merge_ibd_signal(
        raw_evaluation,
        base.ibd_regime,
    )
    trend_ranking = _safe_call(
        lambda: deps.build_trend_ranking_context(
            market_type,
            sector_flow=base.sector_flow,
            distortions=base.market_distortions,
            include_options=market_type == "US",
        ),
        base.trend_ranking,
        errors,
    )
    opportunity_themes = deps.build_opportunity_themes(
        trend_ranking,
        market_distortions=base.market_distortions,
    )
    composite_sentiment = (
        _safe_call(
            lambda: deps.build_market_composite_sentiment(
                options.items,
                refresh_occ=False,
            ),
            base.composite_sentiment,
            errors,
        )
        if market_type == "US"
        else {}
    )
    strategy_bundle = _safe_call(
        lambda: deps.build_market_strategy_context(
            market_type,
            options=options.items,
            option_horizons=options.horizons,
            ibd_regime=base.ibd_regime,
            evaluation=evaluation,
            volatility_regime=base.volatility_regime,
            short_horizon_forecast=base.short_horizon_forecast,
            composite_sentiment=composite_sentiment,
            credit_stress=base.credit_stress,
            trend_ranking=trend_ranking,
            important_levels=base.important_levels or None,
            market_driver_monitor=base.market_driver_monitor or None,
        ),
        {},
        errors,
    )

    context = MarketContext(
        market_type=market_type,
        market_data=base.market_data,
        market_config=base.market_config,
        options=options,
        evaluation=evaluation,
        ibd_regime=base.ibd_regime,
        regime_playbook=base.regime_playbook,
        microstructure=microstructure,
        momentum=base.momentum,
        monitor=results.get("monitor") or base.monitor,
        market_distortions=base.market_distortions,
        trend_ranking=trend_ranking,
        opportunity_themes=opportunity_themes,
        important_levels=strategy_bundle.get("important_levels", base.important_levels),
        market_timeframes=strategy_bundle.get(
            "market_timeframes", base.market_timeframes
        ),
        strategy_regime=strategy_bundle.get("strategy_regime", base.strategy_regime),
        market_driver_monitor=strategy_bundle.get(
            "market_driver_monitor", base.market_driver_monitor
        ),
        japan_conditions=base.japan_conditions,
        sector_flow=base.sector_flow,
        credit_stress=base.credit_stress,
        flow_monitor=base.flow_monitor,
        flow_alignment=base.flow_alignment,
        cross_market=base.cross_market,
        volatility_regime=base.volatility_regime,
        vix_sq_alert=base.vix_sq_alert,
        sentiment=base.sentiment,
        short_horizon_forecast=base.short_horizon_forecast,
        composite_sentiment=composite_sentiment,
        top_risk_signposts=base.top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=_replace_data_status(
            base.data_status,
            DataResult(
                name="options",
                source=options.source,
                fetched_at=options.fetched_at,
                is_stale=options.is_stale,
                is_partial=options.is_partial,
                error=options.error_message,
                cache_status=options.cache_status,
                cache_age_seconds=options.cache_age_seconds,
            ),
            DataResult(
                name="integrated_trend_ranking",
                source="trend_ranking_service",
                fetched_at=_utc_now(),
                is_partial=not bool(trend_ranking.get("items")),
                error="; ".join(trend_ranking.get("quality_warnings", [])),
                cache_status="computed",
            ),
            DataResult(
                name="opportunity_themes",
                source="trend_ranking_service",
                fetched_at=_utc_now(),
                is_partial=not bool(opportunity_themes.get("items")),
                cache_status="computed",
            ),
            DataResult(
                name="market_strategy_regime",
                source="market_strategy_service",
                fetched_at=_utc_now(),
                is_partial=not bool(strategy_bundle.get("strategy_regime")),
                cache_status="computed",
            ),
            DataResult(
                name="composite_market_sentiment",
                source=composite_sentiment.get("source", ""),
                fetched_at=composite_sentiment.get("as_of", ""),
                is_stale=bool(composite_sentiment.get("is_stale", False)),
                is_partial=composite_sentiment.get("status") != "confirmed",
                error="; ".join(composite_sentiment.get("quality_warnings", [])[:3]),
                cache_status="computed",
            ),
        ),
        provenance=_merge_provenance(
            base.provenance,
            deps.option_provenance(
                fetched_at=options.fetched_at or _utc_now(),
                source=options.source,
                status=options.status,
                items=options.items,
            ),
        ),
        errors=errors,
        source="live_options",
        fetched_at=_utc_now(),
        is_stale=base.is_stale or options.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            options.quality_warnings,
            composite_sentiment.get("quality_warnings", []),
            trend_ranking.get("quality_warnings", []),
            strategy_bundle.get("important_levels", {}).get("quality_warnings", []),
            strategy_bundle.get("market_driver_monitor", {}).get(
                "quality_warnings", []
            ),
            errors,
        ),
        cache_status=options.cache_status
        if options.cache_status != "live"
        else base.cache_status,
        cache_age_seconds=options.cache_age_seconds or base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "options",
            "partial"
            if options.is_partial
            or composite_sentiment.get("status") != "confirmed"
            or bool(errors)
            else "live",
            cache_status=options.cache_status,
            fetched_at=options.fetched_at or _utc_now(),
            summary="主要ETFのオプション分析を更新しました。",
            warnings=options.quality_warnings
            + ([options.error_message] if options.error_message else []),
        ),
    )
    manifest_failures = deps.requirement_failures("market_options", context.data_status)
    if manifest_failures:
        context.errors = _merge_warnings(context.errors, manifest_failures)
        context.quality_warnings = _merge_warnings(
            context.quality_warnings, manifest_failures
        )
        context.is_partial = True
    if context.market_data:
        deps.save_context_cache(context, "full")
    return context


def build_market_context(
    market_type: str = "US",
    *,
    dependencies: MarketDashboardWorkflowDependencies | None = None,
) -> MarketContext:
    """Build the full context for legacy callers and tests."""

    deps = _workflow_dependencies(dependencies)
    summary = deps.build_market_summary_context(market_type)
    theme_flow = deps.build_market_theme_flow_context(market_type, summary)
    credit = deps.build_market_high_context(market_type, theme_flow)
    volatility = deps.build_market_volatility_sentiment_context(market_type, credit)
    return deps.build_market_options_context(market_type, volatility)


def build_market_monitor_context(
    option_data: list[dict[str, Any]] | None,
    *,
    dependencies: MarketDashboardWorkflowDependencies | None = None,
) -> dict:
    """Build Distribution Day, climax, and yield-spread monitoring context."""

    deps = _workflow_dependencies(dependencies)
    spy_df = deps.get_stock_data("SPY", "6mo")
    ndx_df = deps.get_stock_data("^NDX", "6mo")

    dist_spy = deps.track_distribution_days(spy_df)
    dist_ndx = deps.track_distribution_days(ndx_df)
    climax = deps.detect_market_climax(spy_df, ndx_df, _extract_spy_pcr(option_data))

    tnx_df = deps.get_stock_data("^TNX", "5d")
    tnx_yield = (
        float(tnx_df["Close"].iloc[-1]) / 10.0
        if tnx_df is not None and not tnx_df.empty
        else None
    )

    spy_pe = _extract_pe(deps.get_valuation_metrics("SPY"))
    ndx_pe = _extract_pe(deps.get_valuation_metrics("QQQ"))
    spread = deps.evaluate_yield_spread(tnx_yield, {"SPY": spy_pe, "NDX": ndx_pe})

    return {
        "distribution_spy": dist_spy,
        "distribution_ndx": dist_ndx,
        "climax": climax,
        "yield_spread": spread,
    }


def build_flow_alignment_context(
    flow_monitor: dict[str, Any] | None,
    sector_flow: dict[str, Any] | None,
) -> dict[str, Any]:
    """Explain how ETF leadership proxy and sector-flow diagnostics should be read."""

    flow = flow_monitor or {}
    sectors = sector_flow or {}
    etf_leader = (flow.get("leaders") or [{}])[0]
    us_leader = ((sectors.get("markets") or {}).get("US", {}).get("leaders") or [{}])[0]
    jp_leader = ((sectors.get("markets") or {}).get("JP", {}).get("leaders") or [{}])[0]
    flow_status = str(flow.get("status") or "unavailable")
    if flow_status == "risk_off":
        alignment_label = "注意"
        summary = (
            "ETFリーダーシップproxyはリスクオフ寄りです。"
            "セクター/テーマ候補は小さく扱い、信用・銀行系の弱さを優先確認します。"
        )
    elif etf_leader and us_leader:
        alignment_label = "整合"
        summary = (
            "ETFリーダーシップproxyで市場全体の資金圧力を確認し、"
            "セクター/テーマ資金流入判定で具体候補を絞ります。"
        )
    else:
        alignment_label = "未判定"
        summary = "片方のデータが不足しているため、役割分担だけを表示します。"

    return {
        "alignment_label": alignment_label,
        "summary": summary,
        "etf_role": "市場全体のリスクオン/オフ、信用・銀行・成長株の確認シグナル。",
        "sector_role": "具体的なセクター/テーマ候補、押し目待ち・観察などの調査ラベル。",
        "etf_leader": {
            "ticker": etf_leader.get("ticker", ""),
            "label": etf_leader.get("label", ""),
            "score": etf_leader.get("leadership_score", 0.0),
        },
        "us_sector_leader": {
            "theme": us_leader.get("theme", ""),
            "score": us_leader.get("flow_score", 0.0),
            "action": us_leader.get("action", ""),
        },
        "jp_theme_leader": {
            "theme": jp_leader.get("theme", ""),
            "score": jp_leader.get("flow_score", 0.0),
            "action": jp_leader.get("action", ""),
        },
    }
