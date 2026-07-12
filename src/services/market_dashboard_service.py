"""Market monitoring orchestration shared by Reflex state and AI reporting."""

# Public compatibility facade: extracted modules import these established dependencies.
# ruff: noqa: F401

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from concurrent.futures import (
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass
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
from src.persistent_cache import PersistentJsonCache, utc_now_iso
from src.sector_flow_monitor import build_sector_flow_monitor
from src.services.analysis_context import DataResult, MarketContext, OptionContext
from src.services.data_fetch_manifest import requirement_failures
from src.services.japan_market_conditions import build_japan_conditions_context
from src.services.market_context_cache import (
    context_cache_key,
    context_cache_path,
    context_from_cache_payload,
    market_context_cache,
    read_context_cache,
    save_context_cache,
)
from src.services.market_playbook import get_market_playbook
from src.services.market_strategy_service import build_market_strategy_context
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
from src.services.trend_ranking_service import (
    build_opportunity_themes,
    build_trend_ranking_context,
)
from src.services.vix_sq_alert_service import build_vix_sq_alert_context
from src.stock_data_provider import get_valuation_metrics

MARKET_SUMMARY_FRESH_SECONDS = 300
MARKET_SUMMARY_STALE_SECONDS = 86400
MARKET_DETAILS_STALE_SECONDS = 3 * 86400
MARKET_CONTEXT_CACHE_NAMESPACE = "market_context_cache"
MARKET_STAGE_TASK_TIMEOUT_SECONDS = 10.0
MARKET_STAGE_TOTAL_TIMEOUT_SECONDS = 20.0
_MARKET_STAGE_EXECUTORS = {
    workers: ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix=f"market-stage-{workers}",
    )
    for workers in (2, 7)
}
DETAIL_STAGE_ORDER = (
    "core",
    "theme_flow",
    "volatility_sentiment",
    "credit_distortion",
    "options",
)
DETAIL_STAGE_DEFAULTS = {
    "core": {
        "label": "Core: 市場概要/キャッシュ",
        "difficulty": "低",
        "target": "主要指数、設定、前回成功キャッシュ",
        "summary": "主要指数と前回成功した監視結果を先に表示します。",
    },
    "theme_flow": {
        "label": "Theme/Flow: 市場状態/資金流入",
        "difficulty": "中",
        "target": "IBD式市場状態、モメンタム、統合トレンド、セクター/テーマ資金流入",
        "summary": "IBD式市場状態、モメンタム、ETF proxy、セクター資金流入を更新します。",
    },
    "volatility_sentiment": {
        "label": "Vol/Sentiment: ボラ/センチメント",
        "difficulty": "中",
        "target": "ボラティリティ・レジーム、独自Fear & Greed、時間軸別方向感",
        "summary": "ボラティリティ・レジームと独自Fear & Greedを更新します。",
    },
    "credit_distortion": {
        "label": "Credit/Risk: 信用/歪み/天井警戒",
        "difficulty": "高",
        "target": "FRED信用ストレス、市場の歪み検知、天井警戒サインポスト",
        "summary": "FRED信用ストレス、市場の歪み検知、天井警戒サインポストを更新します。",
    },
    "options": {
        "label": "高: オプション",
        "difficulty": "高",
        "target": "SPY/QQQ/IWMと上位テーマETF proxyのPCR、IV、Greeks、GEX可否",
        "summary": "主要ETFのオプション分析を更新します。",
    },
}


@dataclass(frozen=True)
class StageTaskResult:
    """Bounded background task result for detailed market stages."""

    value: Any = None
    status: str = "ok"
    error: str = ""
    timed_out: bool = False


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
    data_status = [
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
    ]
    manifest_failures = requirement_failures("market_summary", data_status)
    errors = _merge_warnings(errors, manifest_failures)
    context = MarketContext(
        market_type=market_type,
        market_data=market_data,
        market_config=market_config,
        data_status=data_status,
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
            "core",
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

    theme_flow = build_market_theme_flow_context(market_type, market_context)
    volatility = build_market_volatility_sentiment_context(market_type, theme_flow)
    return build_market_high_context(market_type, volatility)


def build_market_theme_flow_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build market state, momentum, trend ranking, and flow diagnostics."""

    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors: list[str] = []
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
        return _normalize_microstructure(
            analyze_market_structure("SPY", _option_item(options.items, "SPY"))
        )

    def momentum_task() -> dict[str, list[dict[str, Any]]]:
        return get_momentum_themes(market_type)

    def monitor_task() -> dict[str, Any]:
        return build_market_monitor_context(options.items)

    def sector_flow_task() -> dict[str, Any]:
        return build_sector_flow_context(market_type)

    def flow_monitor_task() -> dict[str, Any]:
        return build_sector_flow_monitor(market_type)

    results = _stage_task_values(
        _run_stage_tasks(
            {
                "evaluation": evaluation_task,
                "ibd_regime": ibd_task,
                "microstructure": microstructure_task,
                "momentum": momentum_task,
                "monitor": monitor_task,
                "sector_flow": sector_flow_task,
                "flow_monitor": flow_monitor_task,
            },
            errors,
            stage_name="theme_flow",
            max_workers=7,
        )
    )
    sector_flow = results.get("sector_flow") or base.sector_flow
    flow_monitor = results.get("flow_monitor") or base.flow_monitor
    japan_conditions = (
        _safe_call(
            lambda: build_japan_conditions_context(base.market_data, sector_flow),
            base.japan_conditions,
            errors,
        )
        if market_type == "JP"
        else {}
    )
    cross_market = (
        _safe_call(
            lambda: build_cross_market_context(sector_flow),
            base.cross_market,
            errors,
        )
        if market_type == "JP"
        else {}
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
    volatility_regime = base.volatility_regime
    sentiment = base.sentiment
    trend_ranking = _safe_call(
        lambda: build_trend_ranking_context(
            market_type,
            sector_flow=sector_flow,
            distortions=base.market_distortions,
            include_options=False,
        ),
        base.trend_ranking,
        errors,
    )
    strategy_bundle = _safe_call(
        lambda: build_market_strategy_context(
            market_type,
            options=options.items,
            option_horizons=options.horizons,
            ibd_regime=ibd_regime,
            evaluation=evaluation,
            volatility_regime=volatility_regime,
            credit_stress=base.credit_stress,
            trend_ranking=trend_ranking,
        ),
        {},
        errors,
    )
    data_updates = [
        DataResult(
            name="market_theme_flow",
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
            name="integrated_trend_ranking",
            source="trend_ranking_service",
            fetched_at=_utc_now(),
            is_partial=not bool(trend_ranking.get("items")),
            error="; ".join(trend_ranking.get("quality_warnings", [])),
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
            name="flow_monitor",
            source=flow_monitor.get("source", ""),
            fetched_at=_utc_now(),
            is_partial=bool(flow_monitor.get("is_partial", False)),
            error="; ".join(flow_monitor.get("warnings", [])),
            cache_status="live",
        ),
    ]
    if market_type == "JP":
        data_updates.append(
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
            )
        )

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
        trend_ranking=trend_ranking,
        opportunity_themes=base.opportunity_themes,
        important_levels=strategy_bundle.get("important_levels", {}),
        market_timeframes=strategy_bundle.get("market_timeframes", {}),
        strategy_regime=strategy_bundle.get("strategy_regime", {}),
        market_driver_monitor=strategy_bundle.get("market_driver_monitor", {}),
        japan_conditions=japan_conditions,
        sector_flow=sector_flow,
        credit_stress=base.credit_stress,
        flow_monitor=flow_monitor,
        flow_alignment=flow_alignment,
        cross_market=cross_market,
        volatility_regime=volatility_regime,
        vix_sq_alert=base.vix_sq_alert,
        sentiment=sentiment,
        top_risk_signposts=base.top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=_replace_data_status(base.data_status, *data_updates),
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
        source="live_theme_flow",
        fetched_at=_utc_now(),
        is_stale=base.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            options.quality_warnings,
            sector_flow.get("quality_warnings", []),
            trend_ranking.get("quality_warnings", []),
            strategy_bundle.get("important_levels", {}).get("quality_warnings", []),
            strategy_bundle.get("market_driver_monitor", {}).get(
                "quality_warnings", []
            ),
            flow_monitor.get("warnings", []),
            ibd_regime.get("quality_warnings", []) if ibd_regime else [],
            japan_conditions.get("quality_warnings", []) if japan_conditions else [],
            errors,
        ),
        cache_status="live" if not base.is_stale else base.cache_status,
        cache_age_seconds=base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "theme_flow",
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


def build_market_medium_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Compatibility wrapper for callers that still request the old medium stage."""

    theme_flow = build_market_theme_flow_context(market_type, market_context)
    return build_market_volatility_sentiment_context(market_type, theme_flow)


def build_market_volatility_sentiment_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build volatility regime, local sentiment, and dependent strategy outputs."""

    base = _coerce_context(market_context) or build_market_summary_context(market_type)
    errors: list[str] = []
    volatility_sentiment = _safe_call(
        lambda: _build_volatility_sentiment_context(
            market_type,
            ibd_regime=base.ibd_regime,
            credit_stress=base.credit_stress,
        ),
        {},
        errors,
    )
    volatility_regime = (
        volatility_sentiment.get("volatility_regime") or base.volatility_regime
    )
    sentiment = volatility_sentiment.get("sentiment") or base.sentiment
    vix_sq_alert = volatility_sentiment.get("vix_sq_alert") or base.vix_sq_alert
    strategy_bundle = _safe_call(
        lambda: build_market_strategy_context(
            market_type,
            options=base.options.items,
            option_horizons=base.options.horizons,
            ibd_regime=base.ibd_regime,
            evaluation=base.evaluation,
            volatility_regime=volatility_regime,
            credit_stress=base.credit_stress,
            trend_ranking=base.trend_ranking,
        ),
        {},
        errors,
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
        market_distortions=base.market_distortions,
        trend_ranking=base.trend_ranking,
        opportunity_themes=base.opportunity_themes,
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
        volatility_regime=volatility_regime,
        vix_sq_alert=vix_sq_alert,
        sentiment=sentiment,
        top_risk_signposts=base.top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=_replace_data_status(
            base.data_status,
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
            DataResult(
                name="local_sentiment_composite",
                source=sentiment.get("source", "local_sentiment_composite"),
                fetched_at=_utc_now(),
                is_partial=not bool(sentiment),
                error="; ".join(sentiment.get("quality_warnings", [])),
                cache_status="computed",
            ),
            DataResult(
                name="vix_sq_alert",
                source="vix_sq_alert_service",
                fetched_at=_utc_now(),
                is_partial=vix_sq_alert.get("status")
                in {"unavailable", "insufficient_data"},
                error="; ".join(vix_sq_alert.get("quality_warnings", [])),
                cache_status="computed",
            ),
            DataResult(
                name="market_strategy_regime",
                source="market_strategy_service",
                fetched_at=_utc_now(),
                is_partial=not bool(strategy_bundle.get("strategy_regime")),
                cache_status="computed",
            ),
        ),
        provenance=base.provenance,
        errors=errors,
        source="live_volatility_sentiment",
        fetched_at=_utc_now(),
        is_stale=base.is_stale,
        is_partial=bool(errors) or base.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            volatility_regime.get("warnings", []),
            sentiment.get("quality_warnings", []),
            vix_sq_alert.get("quality_warnings", []),
            strategy_bundle.get("important_levels", {}).get("quality_warnings", []),
            strategy_bundle.get("market_driver_monitor", {}).get(
                "quality_warnings", []
            ),
            errors,
        ),
        cache_status="live" if not base.is_stale else base.cache_status,
        cache_age_seconds=base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "volatility_sentiment",
            "partial" if errors else "live",
            cache_status="live",
            fetched_at=_utc_now(),
            summary="ボラティリティ・レジームと独自Fear & Greedを更新しました。",
            warnings=_merge_warnings(
                volatility_regime.get("warnings", []),
                sentiment.get("quality_warnings", []),
                vix_sq_alert.get("quality_warnings", []),
                errors,
            ),
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
    errors: list[str] = []

    def credit_stress_task() -> dict[str, Any]:
        return build_credit_stress_monitor(market_type)

    def distortions_task() -> dict[str, Any]:
        if market_type != "US":
            return {}
        return detect_market_distortions(market_type, max_themes=30, top_n=5)

    results = _stage_task_values(
        _run_stage_tasks(
            {
                "credit_stress": credit_stress_task,
                "market_distortions": distortions_task,
            },
            errors,
            stage_name="credit_distortion",
            max_workers=2,
        )
    )

    credit_stress = results.get("credit_stress") or base.credit_stress
    market_distortions = results.get("market_distortions") or base.market_distortions
    volatility_regime = base.volatility_regime
    sentiment = base.sentiment
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
    trend_ranking = _safe_call(
        lambda: build_trend_ranking_context(
            market_type,
            sector_flow=base.sector_flow,
            distortions=market_distortions,
            include_options=False,
        ),
        base.trend_ranking,
        errors,
    )
    opportunity_themes = build_opportunity_themes(
        trend_ranking,
        market_distortions=market_distortions,
    )
    strategy_bundle = _safe_call(
        lambda: build_market_strategy_context(
            market_type,
            options=base.options.items,
            option_horizons=base.options.horizons,
            ibd_regime=base.ibd_regime,
            evaluation=base.evaluation,
            volatility_regime=volatility_regime,
            credit_stress=credit_stress,
            trend_ranking=trend_ranking,
        ),
        {},
        errors,
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
        credit_stress=credit_stress,
        flow_monitor=base.flow_monitor,
        flow_alignment=base.flow_alignment,
        cross_market=base.cross_market,
        volatility_regime=volatility_regime,
        vix_sq_alert=base.vix_sq_alert,
        sentiment=sentiment,
        top_risk_signposts=top_risk_signposts,
        fomo_scan=base.fomo_scan,
        data_status=_replace_data_status(
            base.data_status,
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
        ),
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
            trend_ranking.get("quality_warnings", []),
            strategy_bundle.get("important_levels", {}).get("quality_warnings", []),
            strategy_bundle.get("market_driver_monitor", {}).get(
                "quality_warnings", []
            ),
            errors,
        ),
        cache_status=credit_stress.get("cache_status", base.cache_status),
        cache_age_seconds=_optional_float(credit_stress.get("cache_age_seconds"))
        or base.cache_age_seconds,
        detail_stages=_updated_stage_statuses(
            base.detail_stages,
            "credit_distortion",
            "partial"
            if errors or bool(credit_stress.get("is_partial", False))
            else "live",
            cache_status=credit_stress.get("cache_status", "live"),
            fetched_at=credit_stress.get("fetched_at", "") or _utc_now(),
            summary="信用ストレス、市場の歪み検知、天井警戒サインポストを更新しました。",
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


from src.services.market_ai_formatter import (  # noqa: E402, F401
    format_market_context_for_ai,
)
from src.services.market_dashboard_support import (  # noqa: E402, F401
    _build_option_context,
    _build_volatility_sentiment_context,
    _cached_stage_statuses,
    _coerce_context,
    _context_cache_key,
    _context_cache_path,
    _default_stage_statuses,
    _display_percent,
    _extract_pe,
    _extract_spy_pcr,
    _future_result,
    _load_context_cache,
    _low_pe_relative_return_6m,
    _market_context_cache,
    _merge_ibd_signal,
    _merge_provenance,
    _merge_warnings,
    _nested,
    _normalize_microstructure,
    _option_item,
    _optional_float,
    _optional_int,
    _replace_data_status,
    _run_stage_tasks,
    _safe_call,
    _save_context_cache,
    _stage_status_label,
    _stage_task_values,
    _ticker_list_text,
    _updated_stage_statuses,
    _utc_now,
)
from src.services.market_dashboard_workflows import (  # noqa: E402, F401
    build_flow_alignment_context,
    build_fomo_scan_context,
    build_market_context,
    build_market_monitor_context,
    build_market_options_context,
)
