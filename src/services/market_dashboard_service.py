"""Market monitoring orchestration shared by Reflex state and AI reporting."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from src.advisor.fomo_volatility_regime import DEFAULT_FOMO_UNIVERSE, scan_fomo_universe
from src.advisor.ibd_market_regime import classify_ibd_market_regime
from src.advisor.market_environment import evaluate_market_environment
from src.advisor.market_monitor import (
    detect_market_climax,
    evaluate_yield_spread,
    track_distribution_days,
)
from src.advisor.sector_theme_diagnostics import detect_market_distortions
from src.credit_stress_monitor import build_credit_stress_monitor
from src.market_config import get_market_config
from src.market_data import get_market_indices, get_stock_data
from src.market_microstructure import analyze_market_structure
from src.market_volatility_intelligence import (
    build_local_sentiment_composite,
    build_market_volatility_regime,
    build_top_risk_signposts,
    fetch_cboe_indices,
    fetch_cnn_fear_greed,
)
from src.momentum_monitor import get_momentum_themes
from src.option_analyst import get_major_indices_option_status
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
from src.sector_flow_monitor import build_sector_flow_monitor
from src.services.analysis_context import DataResult, MarketContext, OptionContext
from src.services.japan_market_conditions import build_japan_conditions_context
from src.services.market_playbook import get_market_playbook
from src.services.provenance_service import (
    market_high_provenance,
    market_medium_provenance,
    market_summary_provenance,
    option_provenance,
    stale_cache_provenance,
)
from src.services.sector_flow_service import (
    build_cross_market_context,
    build_sector_flow_context,
)
from src.stock_data_provider import get_valuation_metrics

MARKET_SUMMARY_FRESH_SECONDS = 300
MARKET_SUMMARY_STALE_SECONDS = 86400
MARKET_DETAILS_STALE_SECONDS = 3 * 86400
MARKET_CONTEXT_CACHE_NAMESPACE = "market_context_cache"
DETAIL_STAGE_ORDER = ("low", "medium", "high", "options")
DETAIL_STAGE_DEFAULTS = {
    "low": {
        "label": "低: サマリー/キャッシュ",
        "difficulty": "低",
        "summary": "主要指数と前回成功した監視結果を先に表示します。",
    },
    "medium": {
        "label": "中: 市場状態/フロー",
        "difficulty": "中",
        "summary": "IBD式市場状態、モメンタム、ETF proxy、セクター資金流入を更新します。",
    },
    "high": {
        "label": "高: 信用/FRED/歪み",
        "difficulty": "高",
        "summary": "FRED信用ストレスと市場の歪み検知を更新します。",
    },
    "options": {
        "label": "高: オプション",
        "difficulty": "高",
        "summary": "主要ETFのオプション分析を更新します。",
    },
}


def load_cached_market_summary_context(
    market_type: str = "US",
) -> MarketContext | None:
    """Load the last successful lightweight summary for fast startup."""

    return _load_context_cache(
        market_type,
        "summary",
        max_age_seconds=MARKET_SUMMARY_STALE_SECONDS,
        fresh_seconds=MARKET_SUMMARY_FRESH_SECONDS,
    )


def load_cached_market_full_context(
    market_type: str = "US",
) -> MarketContext | None:
    """Load the last successful detailed context for immediate watch display."""

    return _load_context_cache(
        market_type,
        "full",
        max_age_seconds=MARKET_DETAILS_STALE_SECONDS,
        fresh_seconds=MARKET_SUMMARY_FRESH_SECONDS,
    )


def build_market_summary_context(market_type: str = "US") -> MarketContext:
    """Fetch only the lightweight market overview used by initial page load."""

    errors: list[str] = []
    market_data = _safe_call(lambda: get_market_indices(market_type), {}, errors)
    market_config = _safe_call(lambda: get_market_config(market_type), {}, errors)
    context = MarketContext(
        market_type=market_type,
        market_data=market_data,
        market_config=market_config,
        data_status=[
            DataResult(
                name="market_indices",
                source="market_data",
                fetched_at=_utc_now(),
                is_partial=bool(errors) or not bool(market_data),
                error="; ".join(errors) if errors else "",
                cache_status="live",
            ),
            DataResult(
                name="market_config",
                source="local_config",
                fetched_at=_utc_now(),
                is_partial=not bool(market_config),
                cache_status="live",
            ),
        ],
        provenance=market_summary_provenance(
            fetched_at=_utc_now(), has_market_data=bool(market_data)
        ),
        source="live_summary",
        fetched_at=_utc_now(),
        is_partial=bool(errors),
        quality_warnings=list(errors),
        errors=errors,
        cache_status="live",
        detail_stages=_updated_stage_statuses(
            {},
            "low",
            "live",
            cache_status="live",
            fetched_at=_utc_now(),
            summary="主要指数と市場サマリーを取得しました。",
        ),
    )
    if market_data:
        _save_context_cache(context, "summary")
    return context


def build_market_details_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build detailed monitoring data for legacy callers.

    The UI now calls the medium/high builders separately so it can yield after
    each stage. This wrapper preserves the previous single-call behavior.
    """

    medium = build_market_medium_context(market_type, market_context)
    return build_market_high_context(market_type, medium)


def build_market_medium_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build medium-cost market state, momentum, and flow diagnostics."""

    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors = list(base.errors)
    options = base.options

    def evaluation_task() -> dict[str, Any]:
        return evaluate_market_environment(market_type, options.items)

    def ibd_task() -> dict[str, Any]:
        if market_type != "US":
            return {}
        return classify_ibd_market_regime(
            get_stock_data("SPY", "1y"),
            get_stock_data("^NDX", "1y"),
        ).to_dict()

    def microstructure_task() -> dict[str, Any]:
        return _normalize_microstructure(analyze_market_structure("SPY"))

    def momentum_task() -> dict[str, list[dict[str, Any]]]:
        return get_momentum_themes(market_type)

    def monitor_task() -> dict[str, Any]:
        return build_market_monitor_context(options.items)

    def sector_flow_task() -> dict[str, Any]:
        return build_sector_flow_context()

    def flow_monitor_task() -> dict[str, Any]:
        return build_sector_flow_monitor(market_type)

    def volatility_sentiment_task() -> dict[str, Any]:
        if market_type != "US":
            return {}
        spy = get_stock_data("SPY", "5y")
        if spy is None or spy.empty:
            return {}
        tlt = get_stock_data("TLT", "1y")
        cboe = fetch_cboe_indices()
        return {
            "volatility_regime": build_market_volatility_regime(
                spy,
                cboe_result=cboe,
                credit_stress=base.credit_stress,
                cnn_reference=fetch_cnn_fear_greed(),
                ibd_regime=base.ibd_regime,
            ),
            "sentiment": build_local_sentiment_composite(
                spy,
                tlt,
                cboe_result=cboe,
                credit_stress=base.credit_stress,
            ),
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            "evaluation": executor.submit(evaluation_task),
            "ibd_regime": executor.submit(ibd_task),
            "microstructure": executor.submit(microstructure_task),
            "momentum": executor.submit(momentum_task),
            "monitor": executor.submit(monitor_task),
            "sector_flow": executor.submit(sector_flow_task),
            "flow_monitor": executor.submit(flow_monitor_task),
            "volatility_sentiment": executor.submit(volatility_sentiment_task),
        }
        results = {
            name: _future_result(future, errors) for name, future in futures.items()
        }
    sector_flow = results.get("sector_flow") or base.sector_flow
    flow_monitor = results.get("flow_monitor") or base.flow_monitor
    japan_conditions = _safe_call(
        lambda: build_japan_conditions_context(base.market_data, sector_flow),
        base.japan_conditions,
        errors,
    )
    cross_market = _safe_call(
        lambda: build_cross_market_context(sector_flow),
        base.cross_market,
        errors,
    )
    ibd_regime = results.get("ibd_regime") or base.ibd_regime
    regime_playbook = (
        get_market_playbook(str(ibd_regime.get("status_key", ""))) if ibd_regime else {}
    )
    evaluation = _merge_ibd_signal(
        results.get("evaluation") or base.evaluation,
        ibd_regime,
    )
    flow_alignment = build_flow_alignment_context(flow_monitor, sector_flow)
    volatility_sentiment = results.get("volatility_sentiment") or {}
    volatility_regime = (
        volatility_sentiment.get("volatility_regime") or base.volatility_regime
    )
    sentiment = volatility_sentiment.get("sentiment") or base.sentiment

    context = MarketContext(
        market_type=market_type,
        market_data=base.market_data,
        market_config=base.market_config,
        options=options,
        evaluation=evaluation,
        ibd_regime=ibd_regime,
        regime_playbook=regime_playbook,
        microstructure=results.get("microstructure") or base.microstructure,
        momentum=results.get("momentum") or base.momentum,
        monitor=results.get("monitor") or base.monitor,
        market_distortions=base.market_distortions,
        japan_conditions=japan_conditions,
        sector_flow=sector_flow,
        credit_stress=base.credit_stress,
        flow_monitor=flow_monitor,
        flow_alignment=flow_alignment,
        cross_market=cross_market,
        volatility_regime=volatility_regime,
        sentiment=sentiment,
        top_risk_signposts=base.top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=[
            *base.data_status,
            DataResult(
                name="market_details_medium",
                source="market_dashboard_service",
                fetched_at=_utc_now(),
                is_partial=bool(errors),
                error="; ".join(errors) if errors else "",
                cache_status="live",
            ),
            DataResult(
                name="ibd_market_regime",
                source="local_ohlcv_classification",
                fetched_at=_utc_now(),
                is_partial=not bool(ibd_regime)
                or bool(ibd_regime.get("quality_warnings", [])),
                error="; ".join(ibd_regime.get("quality_warnings", []))
                if ibd_regime
                else "",
                cache_status="computed",
            ),
            DataResult(
                name="sector_flow",
                source="sector_flow_service",
                fetched_at=_utc_now(),
                is_partial=not bool(sector_flow),
                cache_status="live",
            ),
            DataResult(
                name="flow_monitor",
                source=flow_monitor.get("source", ""),
                fetched_at=_utc_now(),
                is_partial=bool(flow_monitor.get("is_partial", False)),
                error="; ".join(flow_monitor.get("warnings", [])),
                cache_status="live",
            ),
            DataResult(
                name="nikkei_conditions",
                source="japan_market_conditions",
                fetched_at=_utc_now(),
                is_partial=not bool(japan_conditions)
                or bool(japan_conditions.get("unavailable_count", 0)),
                error="; ".join(japan_conditions.get("quality_warnings", []))
                if japan_conditions
                else "",
                cache_status="live",
            ),
            DataResult(
                name="market_volatility_regime",
                source=volatility_regime.get("source", ""),
                fetched_at=_utc_now(),
                is_stale=bool(volatility_regime.get("is_stale", False)),
                is_partial=not bool(volatility_regime)
                or volatility_regime.get("regime") == "unavailable",
                error="; ".join(volatility_regime.get("warnings", [])),
                cache_status="computed",
            ),
        ],
        provenance=_merge_provenance(
            base.provenance,
            market_medium_provenance(
                fetched_at=_utc_now(),
                monitor=results.get("monitor") or base.monitor,
                ibd_regime=ibd_regime,
                microstructure=results.get("microstructure") or base.microstructure,
                sector_flow=sector_flow,
                flow_monitor=flow_monitor,
                japan_conditions=japan_conditions,
            ),
        ),
        errors=errors,
        source="live_details",
        fetched_at=_utc_now(),
        is_stale=base.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            options.quality_warnings,
            sector_flow.get("quality_warnings", []),
            flow_monitor.get("warnings", []),
            ibd_regime.get("quality_warnings", []) if ibd_regime else [],
            japan_conditions.get("quality_warnings", []) if japan_conditions else [],
            errors,
        ),
        cache_status="live" if not base.is_stale else base.cache_status,
        cache_age_seconds=base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "medium",
            "partial" if errors else "live",
            cache_status="live",
            fetched_at=_utc_now(),
            summary="市場状態、モメンタム、ETF proxy、セクター資金流入を更新しました。",
            warnings=errors,
        ),
    )
    if context.market_data:
        _save_context_cache(context, "full")
    return context


def build_market_high_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build high-cost credit stress and distortion diagnostics."""

    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors = list(base.errors)

    def credit_stress_task() -> dict[str, Any]:
        return build_credit_stress_monitor(market_type)

    def distortions_task() -> dict[str, Any]:
        if market_type != "US":
            return {}
        return detect_market_distortions(market_type, max_themes=30, top_n=5)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "credit_stress": executor.submit(credit_stress_task),
            "market_distortions": executor.submit(distortions_task),
        }
        results = {
            name: _future_result(future, errors) for name, future in futures.items()
        }

    credit_stress = results.get("credit_stress") or base.credit_stress
    market_distortions = results.get("market_distortions") or base.market_distortions
    sentiment = base.sentiment
    if market_type == "US":
        sentiment = _safe_call(
            lambda: build_local_sentiment_composite(
                get_stock_data("SPY", "1y"),
                get_stock_data("TLT", "1y"),
                credit_stress=credit_stress,
            ),
            base.sentiment,
            errors,
        )
    top_risk_signposts = (
        _safe_call(
            lambda: build_top_risk_signposts(
                sentiment=sentiment,
                credit_stress=credit_stress,
                low_pe_relative_6m=_low_pe_relative_return_6m(),
            ),
            base.top_risk_signposts,
            errors,
        )
        if market_type == "US"
        else {}
    )
    context = MarketContext(
        market_type=market_type,
        market_data=base.market_data,
        market_config=base.market_config,
        options=base.options,
        evaluation=base.evaluation,
        ibd_regime=base.ibd_regime,
        regime_playbook=base.regime_playbook,
        microstructure=base.microstructure,
        momentum=base.momentum,
        monitor=base.monitor,
        market_distortions=market_distortions,
        japan_conditions=base.japan_conditions,
        sector_flow=base.sector_flow,
        credit_stress=credit_stress,
        flow_monitor=base.flow_monitor,
        flow_alignment=base.flow_alignment,
        cross_market=base.cross_market,
        volatility_regime=base.volatility_regime,
        sentiment=sentiment,
        top_risk_signposts=top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=[
            *base.data_status,
            DataResult(
                name="market_details_high",
                source="market_dashboard_service",
                fetched_at=_utc_now(),
                is_partial=bool(errors),
                error="; ".join(errors) if errors else "",
                cache_status="live",
            ),
            DataResult(
                name="market_distortions",
                source="sector_theme_diagnostics",
                fetched_at=_utc_now(),
                is_partial=not bool(market_distortions),
                error="; ".join(market_distortions.get("quality_warnings", [])[:3]),
                cache_status="computed",
            ),
            DataResult(
                name="credit_stress",
                source=credit_stress.get("source", ""),
                fetched_at=credit_stress.get("fetched_at", ""),
                is_stale=bool(credit_stress.get("is_stale", False)),
                is_partial=bool(credit_stress.get("is_partial", False)),
                error="; ".join(credit_stress.get("warnings", [])),
                cache_status=credit_stress.get("cache_status", "live"),
                cache_age_seconds=_optional_float(
                    credit_stress.get("cache_age_seconds")
                ),
            ),
            DataResult(
                name="top_risk_signposts",
                source=top_risk_signposts.get("source", ""),
                fetched_at=_utc_now(),
                is_partial=not bool(top_risk_signposts),
                error="; ".join(top_risk_signposts.get("quality_warnings", [])),
                cache_status="computed",
            ),
        ],
        provenance=_merge_provenance(
            base.provenance,
            market_high_provenance(
                fetched_at=_utc_now(),
                credit_stress=credit_stress,
                distortions=market_distortions,
            ),
        ),
        errors=errors,
        source="live_details_high",
        fetched_at=_utc_now(),
        is_stale=base.is_stale or bool(credit_stress.get("is_stale", False)),
        is_partial=bool(errors)
        or base.is_partial
        or bool(credit_stress.get("is_partial", False))
        or not bool(market_distortions),
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            credit_stress.get("warnings", []),
            market_distortions.get("quality_warnings", []),
            errors,
        ),
        cache_status=credit_stress.get("cache_status", base.cache_status),
        cache_age_seconds=_optional_float(credit_stress.get("cache_age_seconds"))
        or base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "high",
            "partial"
            if errors or bool(credit_stress.get("is_partial", False))
            else "live",
            cache_status=credit_stress.get("cache_status", "live"),
            fetched_at=credit_stress.get("fetched_at", "") or _utc_now(),
            summary="信用ストレスと市場の歪み検知を更新しました。",
            warnings=_merge_warnings(
                credit_stress.get("warnings", []),
                market_distortions.get("quality_warnings", []),
                errors,
            ),
        ),
    )
    if context.market_data:
        _save_context_cache(context, "full")
    return context


def build_fomo_scan_context(tickers: list[str] | None = None) -> dict[str, Any]:
    """Run the explicit, bounded high-volatility watchlist scan."""

    return scan_fomo_universe(get_stock_data, tickers or DEFAULT_FOMO_UNIVERSE)


def build_market_options_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Refresh option data and option-dependent monitoring without reloading all data."""

    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors = list(base.errors)
    options = _build_option_context(market_type)
    if options.error_message:
        errors.append(options.error_message)

    def evaluation_task() -> dict[str, Any]:
        return evaluate_market_environment(market_type, options.items)

    def monitor_task() -> dict[str, Any]:
        return build_market_monitor_context(options.items)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "evaluation": executor.submit(evaluation_task),
            "monitor": executor.submit(monitor_task),
        }
        results = {
            name: _future_result(future, errors) for name, future in futures.items()
        }

    context = MarketContext(
        market_type=market_type,
        market_data=base.market_data,
        market_config=base.market_config,
        options=options,
        evaluation=_merge_ibd_signal(
            results.get("evaluation") or base.evaluation,
            base.ibd_regime,
        ),
        ibd_regime=base.ibd_regime,
        regime_playbook=base.regime_playbook,
        microstructure=base.microstructure,
        momentum=base.momentum,
        monitor=results.get("monitor") or base.monitor,
        market_distortions=base.market_distortions,
        japan_conditions=base.japan_conditions,
        sector_flow=base.sector_flow,
        credit_stress=base.credit_stress,
        flow_monitor=base.flow_monitor,
        flow_alignment=base.flow_alignment,
        cross_market=base.cross_market,
        volatility_regime=base.volatility_regime,
        sentiment=base.sentiment,
        top_risk_signposts=base.top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=[
            *base.data_status,
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
        ],
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
            base.quality_warnings, options.quality_warnings, errors
        ),
        cache_status=options.cache_status
        if options.cache_status != "live"
        else base.cache_status,
        cache_age_seconds=options.cache_age_seconds or base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "options",
            "partial" if options.is_partial else "live",
            cache_status=options.cache_status,
            fetched_at=options.fetched_at or _utc_now(),
            summary="主要ETFのオプション分析を更新しました。",
            warnings=options.quality_warnings
            + ([options.error_message] if options.error_message else []),
        ),
    )
    if context.market_data:
        _save_context_cache(context, "full")
    return context


def build_market_context(market_type: str = "US") -> MarketContext:
    """Build the full context for legacy callers and tests."""

    summary = build_market_summary_context(market_type)
    with_options = build_market_options_context(market_type, summary)
    return build_market_details_context(market_type, with_options)


def build_market_monitor_context(option_data: list[dict[str, Any]] | None) -> dict:
    """Build Distribution Day, climax, and yield-spread monitoring context."""

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


def format_market_context_for_ai(context: MarketContext) -> str:
    """Create a compact prompt section from already computed monitoring context."""

    parts = ["[Advanced Technical / Market Monitoring]"]
    if context.data_status:
        status_parts = []
        for item in context.data_status[:6]:
            status = "partial" if item.is_partial else "ok"
            if item.is_stale:
                status = "stale"
            error = f", error={item.error}" if item.error else ""
            cache = (
                f", cache={item.cache_status}"
                if item.cache_status and item.cache_status != "live"
                else ""
            )
            status_parts.append(
                f"{item.name}: {status} from {item.source or 'unknown'}{cache}{error}"
            )
        parts.append("- Data status: " + "; ".join(status_parts))
    if context.quality_warnings:
        parts.append("- Data quality: " + "; ".join(context.quality_warnings[:6]))
    if context.provenance:
        parts.append("[Data provenance]")
        for item in context.provenance[:12]:
            details = [
                f"kind={item.kind.value}",
                f"source={item.source or 'unknown'}",
            ]
            if item.as_of:
                details.append(f"as_of={item.as_of}")
            if item.method:
                details.append(f"method={item.method}")
            if item.limitation:
                details.append(f"limitation={item.limitation}")
            details.append(f"risk={item.risk_level}")
            parts.append(f"- {item.label}: " + ", ".join(details))
    if context.detail_stages:
        stage_parts = []
        for key in DETAIL_STAGE_ORDER:
            item = context.detail_stages.get(key) or {}
            if item:
                stage_parts.append(
                    f"{item.get('label', key)}={item.get('status_label', item.get('status', 'unknown'))}"
                )
        if stage_parts:
            parts.append("- Detail stages: " + "; ".join(stage_parts))
    if context.options.quality_warnings:
        parts.append(
            "- Options data quality: " + "; ".join(context.options.quality_warnings[:6])
        )
    if context.volatility_regime:
        volatility = context.volatility_regime
        parts.append("[Market volatility regime]")
        parts.append(
            f"- {volatility.get('summary', '')}; "
            f"confidence={volatility.get('confidence', 'low')}"
        )
        outcomes = volatility.get("forward_outcomes", {}).get("20d", {})
        if outcomes:
            parts.append(
                "- Historical analog 20d: "
                f"mean={_display_percent(outcomes.get('mean_return'))}, "
                f"probability_up={_display_percent(outcomes.get('probability_up'))}"
            )
    if context.sentiment:
        parts.append(
            "[Local sentiment composite] "
            f"{context.sentiment.get('summary', '')}; "
            f"coverage={context.sentiment.get('coverage', '')}"
        )
        cnn = context.sentiment.get("cnn_reference") or {}
        if cnn:
            parts.append(
                "- CNN external reference only: "
                f"status={cnn.get('status', 'unavailable')}, "
                f"score={cnn.get('score')}, rating={cnn.get('rating', '')}"
            )
    if context.top_risk_signposts:
        signposts = context.top_risk_signposts
        parts.append(
            "[BofA-inspired top-risk subset, not official BofA] "
            f"{signposts.get('summary', '')}"
        )
        for item in (signposts.get("items") or [])[:7]:
            parts.append(
                f"- {item.get('label', '')}: {item.get('status', 'unknown')} "
                f"({item.get('kind', 'proxy')})"
            )

    evaluation = context.evaluation or {}
    if evaluation:
        parts.append(
            f"- Market environment: {evaluation.get('status', 'unknown')} "
            f"(score={float(evaluation.get('score', 0.0)):.2f})"
        )
        for signal in evaluation.get("signals", [])[:8]:
            parts.append(
                f"  - {signal.get('name', 'signal')}: "
                f"{float(signal.get('score', 0.0)):.2f} "
                f"({signal.get('rationale', '')})"
            )

    ibd = context.ibd_regime or {}
    if ibd:
        parts.append("[IBD-style market regime]")
        parts.append(
            f"- Regime: {ibd.get('label', 'unknown')} "
            f"(score={float(ibd.get('score', 0.0)):.2f}, "
            f"exposure={ibd.get('exposure_level', 'unknown')})"
        )
        if ibd.get("rationale"):
            parts.append(f"- Regime rationale: {ibd['rationale']}")
        playbook = context.regime_playbook or {}
        if playbook:
            parts.append(
                f"- Current stance: {playbook.get('stance', '')} "
                f"Risk budget={playbook.get('risk_budget', '')}"
            )
            think_about = playbook.get("think_about") or []
            if think_about:
                parts.append("- Think about: " + "; ".join(think_about[:4]))

    micro = context.microstructure or {}
    if micro:
        parts.append(
            "- Microstructure: "
            f"VRP={_display_percent(micro.get('vrp'))}, "
            f"CTA={_nested(micro, 'cta_proxy', 'extremity')}, "
            f"liquidity={_nested(micro, 'liquidity', 'status')}, "
            f"unwind={micro.get('unwind_level', 'unknown')}"
        )
        if micro.get("narrative_text"):
            parts.append(str(micro["narrative_text"]))

    monitor = context.monitor or {}
    if monitor:
        dist_spy = monitor.get("distribution_spy", {})
        dist_ndx = monitor.get("distribution_ndx", {})
        climax = monitor.get("climax", {})
        spread = monitor.get("yield_spread", {})
        parts.append(
            "- Distribution days: "
            f"SPY={dist_spy.get('count', 0)} ({dist_spy.get('level', 'unknown')}), "
            f"NDX={dist_ndx.get('count', 0)} ({dist_ndx.get('level', 'unknown')})"
        )
        if climax.get("warnings"):
            parts.append("- Market climax warnings: " + "; ".join(climax["warnings"]))
        yield_10y = spread.get("yield_10y")
        yield_display = (
            f"{float(yield_10y):.2f}%" if yield_10y is not None else "unavailable"
        )
        parts.append(
            "- Yield spread: "
            f"{spread.get('overall_status', 'unknown')} (10Y={yield_display})"
        )

    if context.momentum:
        leaders = []
        for category, themes in context.momentum.items():
            top = themes[0] if themes else {}
            if top:
                leaders.append(
                    f"{category}: {top.get('theme')} {top.get('performance')}%"
                )
        if leaders:
            parts.append("- Momentum leaders: " + "; ".join(leaders[:4]))

    distortions = context.market_distortions or {}
    if distortions:
        parts.append("[Market distortions: fundamentals vs flows]")
        bullish = distortions.get("bullish") or []
        bearish = distortions.get("bearish") or []
        if bullish:
            parts.append(
                "- Bullish distortions: "
                + "; ".join(
                    f"{item.get('theme')} ({_ticker_list_text(item.get('tickers'))}) "
                    f"gap={float(item.get('distortion_score', 0.0)):.2f}"
                    for item in bullish[:5]
                )
            )
        if bearish:
            parts.append(
                "- Bearish distortions: "
                + "; ".join(
                    f"{item.get('theme')} ({_ticker_list_text(item.get('tickers'))}) "
                    f"gap={float(item.get('distortion_score', 0.0)):.2f}"
                    for item in bearish[:5]
                )
            )

    credit = context.credit_stress or {}
    if credit:
        parts.append("[Credit stress velocity]")
        parts.append(
            f"- Status: {credit.get('status_label', credit.get('status', 'unknown'))} "
            f"({credit.get('summary', '')})"
        )
        for item in (credit.get("indicators") or [])[:2]:
            parts.append(
                f"  - {item.get('label')}: "
                f"latest={float(item.get('latest', 0.0)):.2f}, "
                f"3m_delta={float(item.get('delta_3m', 0.0)):.2f}, "
                f"z={float(item.get('z_score', 0.0)):.2f}"
            )

    flow = context.flow_monitor or {}
    if flow:
        parts.append("[Leadership flow-pressure proxy]")
        parts.append(
            f"- Status: {flow.get('status', 'unknown')} ({flow.get('summary', '')})"
        )
        leaders = []
        for item in (flow.get("leaders") or [])[:3]:
            leaders.append(
                f"{item.get('label')} {item.get('ticker')} "
                f"score={float(item.get('leadership_score', 0.0)):.2f}"
            )
        if leaders:
            parts.append("  - Leaders: " + "; ".join(leaders))

    sector_flow = context.sector_flow or {}
    if sector_flow:
        parts.append("[US primary / Japan supplemental sector flow]")
        if sector_flow.get("summary"):
            parts.append(f"- Flow summary: {sector_flow['summary']}")
        for market, payload in (sector_flow.get("markets") or {}).items():
            leaders = payload.get("leaders") or []
            if leaders:
                leader = leaders[0]
                parts.append(
                    f"- {market} leading flow: {leader.get('theme')} "
                    f"(score={float(leader.get('flow_score', 0.0)):.1f}, "
                    f"confidence={leader.get('confidence')}, "
                    f"continuation={leader.get('continuation')}, "
                    f"action={leader.get('action')})"
                )

    flow_alignment = context.flow_alignment or {}
    if flow_alignment:
        parts.append("[ETF proxy / sector-flow role split]")
        parts.append(f"- {flow_alignment.get('summary', '')}")
        parts.append(f"- ETF proxy role: {flow_alignment.get('etf_role', '')}")
        parts.append(f"- Sector/theme role: {flow_alignment.get('sector_role', '')}")

    japan = context.japan_conditions or {}
    if japan:
        parts.append("[Nikkei upside six conditions]")
        parts.append(
            f"- Overall: {japan.get('summary', '')} "
            f"label={japan.get('score_label', 'unknown')}"
        )
        for item in (japan.get("items") or [])[:6]:
            parts.append(
                f"  - C{item.get('condition_no')}: {item.get('status_label')} "
                f"value={item.get('value')} evidence={item.get('evidence')}"
            )

    cross = context.cross_market or {}
    if cross:
        parts.append(
            "[Cross-market stance] "
            f"{cross.get('stance', '')} "
            f"relative_flow={cross.get('relative_flow_score', 0)}"
        )

    return "\n".join(parts)


def _build_option_context(market_type: str) -> OptionContext:
    try:
        result = get_major_indices_option_status(market_type)
        failed_tickers = list(result.get("failed_tickers") or [])
        status = str(result.get("status") or "unavailable")
        return OptionContext(
            items=list(result.get("items") or []),
            error_message=str(result.get("error_message") or ""),
            status=status,
            failed_tickers=failed_tickers,
            source=str(result.get("source") or "yfinance"),
            fetched_at=str(result.get("fetched_at") or ""),
            is_stale=bool(result.get("is_stale", False)),
            is_partial=status == "partial" or bool(failed_tickers),
            quality_warnings=list(result.get("quality_warnings") or []),
            cache_status=str(result.get("cache_status") or "live"),
            cache_age_seconds=_optional_float(result.get("cache_age_seconds")),
        )
    except Exception as exc:
        return OptionContext(
            error_message=f"Option analysis failed: {exc}",
            status="failed",
            source="yfinance",
            is_partial=True,
            quality_warnings=[f"Option analysis failed: {exc}"],
            cache_status="failed",
        )


def _safe_call(callback, fallback, errors: list[str]):
    try:
        return callback()
    except Exception as exc:
        errors.append(str(exc))
        return fallback


def _future_result(future, errors: list[str]):
    try:
        return future.result()
    except Exception as exc:
        errors.append(str(exc))
        return None


def _normalize_microstructure(data: dict | None) -> dict[str, Any]:
    return data or {}


def _extract_spy_pcr(option_data: list[dict[str, Any]] | None) -> float | None:
    if not option_data:
        return None
    first = next(
        (item for item in option_data if item.get("ticker") == "SPY"),
        option_data[0],
    )
    pcr = first.get("pcr", {})
    if isinstance(pcr, dict):
        value = pcr.get("volume_pcr")
        return float(value) if isinstance(value, (int, float)) else None
    if isinstance(pcr, (int, float)):
        return float(pcr)
    return None


def _extract_pe(info: dict[str, Any] | None) -> float | None:
    value = info.get("pe_ratio") if info else None
    return float(value) if isinstance(value, (int, float)) else None


def _nested(source: dict[str, Any], parent: str, child: str) -> str:
    value = source.get(parent) or {}
    return str(value.get(child, "unknown")) if isinstance(value, dict) else "unknown"


def _display_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2%}"
    return "unknown"


def _ticker_list_text(value: Any) -> str:
    if not value:
        return "representative tickers unavailable"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value[:5])
    return str(value)


def _coerce_context(
    value: MarketContext | dict[str, Any] | None,
) -> MarketContext | None:
    if isinstance(value, MarketContext):
        return value
    if isinstance(value, dict) and value:
        return MarketContext.from_mapping(value)
    return None


def _merge_ibd_signal(
    evaluation: dict[str, Any],
    ibd_regime: dict[str, Any],
) -> dict[str, Any]:
    if not ibd_regime:
        return evaluation

    signals = list(evaluation.get("signals") or [])
    signals.append(
        {
            "name": "IBD市場状態",
            "score": float(ibd_regime.get("score", 0.0)),
            "weight": float(ibd_regime.get("weight", 2.0)),
            "rationale": str(ibd_regime.get("rationale") or ""),
        }
    )
    total_weight = sum(float(item.get("weight", 0.0)) for item in signals)
    score = (
        sum(
            float(item.get("score", 0.0)) * float(item.get("weight", 0.0))
            for item in signals
        )
        / total_weight
        if total_weight
        else float(evaluation.get("score", 0.0))
    )
    if score >= 0.3:
        status = "🟢 強気 (Bullish)"
        description = "IBD式市場状態を含む複合評価では、リスクを取りやすい環境である。"
    elif score <= -0.3:
        status = "🔴 弱気 (Bearish)"
        description = (
            "IBD式市場状態を含む複合評価では、資金防衛を優先すべき環境である。"
        )
    else:
        status = "⚪ 中立 (Neutral)"
        description = "IBD式市場状態を含む複合評価では、強弱が混在し選別が必要である。"

    return {
        **evaluation,
        "status": status,
        "score": score,
        "description": description,
        "signals": signals,
    }


def _context_cache_path(market_type: str, kind: str) -> Path:
    return _market_context_cache().path_for_key(_context_cache_key(market_type, kind))


def _save_context_cache(context: MarketContext, kind: str) -> None:
    path = _context_cache_path(context.market_type, kind)
    try:
        _market_context_cache().write_path(
            path,
            _context_cache_key(context.market_type, kind),
            context.to_dict(),
            fetched_at=context.fetched_at or _utc_now(),
        )
    except OSError:
        return


def _load_context_cache(
    market_type: str,
    kind: str,
    *,
    max_age_seconds: int,
    fresh_seconds: int,
) -> MarketContext | None:
    key = _context_cache_key(market_type, kind)
    path = _context_cache_path(market_type, kind)
    read = _market_context_cache().read_path(
        path,
        key,
        fresh_seconds=fresh_seconds,
        stale_seconds=max_age_seconds,
    )
    if not read.is_available:
        return None

    context = MarketContext.from_mapping(read.payload)
    if read.fetched_at and not context.fetched_at:
        context.fetched_at = read.fetched_at
    context.source = f"{context.source or kind}_cache"
    context.is_stale = read.is_stale
    context.cache_status = "stale_cache" if read.is_stale else "persistent_cache"
    context.cache_age_seconds = read.age_seconds
    for item in context.data_status:
        item.cache_status = context.cache_status
        item.cache_age_seconds = read.age_seconds
    if context.is_stale:
        context.quality_warnings = _merge_warnings(
            context.quality_warnings,
            [f"Using cached market summary from {context.fetched_at}."],
        )
        context.provenance = _merge_provenance(
            context.provenance,
            [
                stale_cache_provenance(
                    fetched_at=context.fetched_at,
                    source=context.source,
                )
            ],
        )
    context.detail_stages = _cached_stage_statuses(
        context.detail_stages,
        read.is_stale,
        context.cache_status,
        read.fetched_at,
    )
    return context


def _updated_stage_statuses(
    existing: dict[str, dict[str, Any]] | None,
    key: str,
    status: str,
    *,
    cache_status: str = "",
    fetched_at: str = "",
    summary: str = "",
    warnings: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    stages = _default_stage_statuses()
    for stage_key, payload in (existing or {}).items():
        if isinstance(payload, dict):
            stages[stage_key] = {**stages.get(stage_key, {}), **payload}
    default = DETAIL_STAGE_DEFAULTS.get(key, {})
    stages[key] = {
        **stages.get(key, {}),
        "key": key,
        "label": default.get("label", key),
        "difficulty": default.get("difficulty", ""),
        "status": status,
        "status_label": _stage_status_label(status),
        "cache_status": cache_status,
        "fetched_at": fetched_at,
        "summary": summary or default.get("summary", ""),
        "quality_warnings": _merge_warnings(warnings or []),
    }
    return {stage_key: stages[stage_key] for stage_key in DETAIL_STAGE_ORDER}


def _default_stage_statuses() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": key,
            "label": payload["label"],
            "difficulty": payload["difficulty"],
            "status": "pending",
            "status_label": "未取得",
            "cache_status": "",
            "fetched_at": "",
            "summary": payload["summary"],
            "quality_warnings": [],
        }
        for key, payload in DETAIL_STAGE_DEFAULTS.items()
    }


def _cached_stage_statuses(
    existing: dict[str, dict[str, Any]] | None,
    is_stale: bool,
    cache_status: str,
    fetched_at: str,
) -> dict[str, dict[str, Any]]:
    stages = _default_stage_statuses()
    for key, payload in (existing or {}).items():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "pending")
        if status in {"live", "partial", "cache"}:
            status = "stale_cache" if is_stale else "cache"
        stages[key] = {
            **stages.get(key, {}),
            **payload,
            "status": status,
            "status_label": _stage_status_label(status),
            "cache_status": cache_status,
            "fetched_at": fetched_at or payload.get("fetched_at", ""),
        }
    return {stage_key: stages[stage_key] for stage_key in DETAIL_STAGE_ORDER}


def _stage_status_label(status: str) -> str:
    return {
        "pending": "未取得",
        "loading": "取得中",
        "live": "最新",
        "partial": "一部取得",
        "cache": "キャッシュ",
        "stale_cache": "古いキャッシュ",
        "failed": "取得失敗",
    }.get(status, status)


def _utc_now() -> str:
    return utc_now_iso()


def _merge_warnings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item)
            if text and text not in seen:
                merged.append(text)
                seen.add(text)
    return merged


def _merge_provenance(*groups):
    merged = {}
    for group in groups:
        for item in group or []:
            merged[item.item_id] = item
    return list(merged.values())


def _context_cache_key(market_type: str, kind: str) -> str:
    return f"{market_type.lower()}_{kind}"


def _market_context_cache() -> PersistentJsonCache:
    return repo_state_cache(MARKET_CONTEXT_CACHE_NAMESPACE)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _low_pe_relative_return_6m() -> float | None:
    """Return growth-minus-value six-month performance as the public proxy."""

    growth = get_stock_data("RPG", "1y")
    value = get_stock_data("RPV", "1y")
    if growth is None or value is None or growth.empty or value.empty:
        return None
    joined = pd.concat(
        [growth["Close"].rename("growth"), value["Close"].rename("value")],
        axis=1,
    ).dropna()
    if len(joined) < 126:
        return None
    return float(
        joined["growth"].iloc[-1] / joined["growth"].iloc[-126]
        - joined["value"].iloc[-1] / joined["value"].iloc[-126]
    )
