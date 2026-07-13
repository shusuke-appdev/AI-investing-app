"""FOMO, option, and derived market-monitor workflows."""

# ruff: noqa: F403, F405

from src.services import market_dashboard_service as _service
from src.services.market_dashboard_service import *
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


def _sync_compat_dependencies() -> None:
    """Honor patches against the historical facade during the migration window."""

    for name in tuple(globals()):
        if not name.startswith("__") and hasattr(_service, name):
            globals()[name] = getattr(_service, name)


def build_fomo_scan_context(tickers: list[str] | None = None) -> dict[str, Any]:
    """Run the explicit, bounded high-volatility watchlist scan."""

    _sync_compat_dependencies()
    return scan_fomo_universe(get_stock_data, tickers or DEFAULT_FOMO_UNIVERSE)


def build_market_options_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Refresh option data and option-dependent monitoring without reloading all data."""

    _sync_compat_dependencies()
    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors: list[str] = []
    options = _build_option_context(market_type)
    if options.error_message:
        errors.append(options.error_message)

    def microstructure_task() -> dict[str, Any]:
        return _normalize_microstructure(
            analyze_market_structure(
                "SPY",
                _option_item(options.items, "SPY") or {},
                allow_option_fetch=False,
            )
        )

    def monitor_task() -> dict[str, Any]:
        return build_market_monitor_context(options.items)

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
        lambda: evaluate_market_environment(
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
        lambda: build_trend_ranking_context(
            market_type,
            sector_flow=base.sector_flow,
            distortions=base.market_distortions,
            include_options=market_type == "US",
        ),
        base.trend_ranking,
        errors,
    )
    opportunity_themes = build_opportunity_themes(
        trend_ranking,
        market_distortions=base.market_distortions,
    )
    composite_sentiment = (
        _safe_call(
            lambda: build_market_composite_sentiment(
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
        lambda: build_market_strategy_context(
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
            option_provenance(
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
    manifest_failures = requirement_failures("market_options", context.data_status)
    if manifest_failures:
        context.errors = _merge_warnings(context.errors, manifest_failures)
        context.quality_warnings = _merge_warnings(
            context.quality_warnings, manifest_failures
        )
        context.is_partial = True
    if context.market_data:
        _save_context_cache(context, "full")
    return context


def build_market_context(market_type: str = "US") -> MarketContext:
    """Build the full context for legacy callers and tests."""

    _sync_compat_dependencies()
    summary = build_market_summary_context(market_type)
    theme_flow = build_market_theme_flow_context(market_type, summary)
    credit = build_market_high_context(market_type, theme_flow)
    volatility = build_market_volatility_sentiment_context(market_type, credit)
    return build_market_options_context(market_type, volatility)


def build_market_monitor_context(option_data: list[dict[str, Any]] | None) -> dict:
    """Build Distribution Day, climax, and yield-spread monitoring context."""

    _sync_compat_dependencies()
    spy_df = get_stock_data("SPY", "6mo")
    ndx_df = get_stock_data("^NDX", "6mo")

    dist_spy = track_distribution_days(spy_df)
    dist_ndx = track_distribution_days(ndx_df)
    climax = detect_market_climax(spy_df, ndx_df, _extract_spy_pcr(option_data))

    tnx_df = get_stock_data("^TNX", "5d")
    tnx_yield = (
        float(tnx_df["Close"].iloc[-1]) / 10.0
        if tnx_df is not None and not tnx_df.empty
        else None
    )

    spy_pe = _extract_pe(get_valuation_metrics("SPY"))
    ndx_pe = _extract_pe(get_valuation_metrics("QQQ"))
    spread = evaluate_yield_spread(tnx_yield, {"SPY": spy_pe, "NDX": ndx_pe})

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

    _sync_compat_dependencies()
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
