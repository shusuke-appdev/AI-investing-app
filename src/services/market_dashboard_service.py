"""Market monitoring orchestration shared by Reflex state and AI reporting."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

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
from src.momentum_monitor import get_momentum_themes
from src.option_analyst import get_major_indices_option_status
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
from src.sector_flow_monitor import build_sector_flow_monitor
from src.services.analysis_context import DataResult, MarketContext, OptionContext
from src.services.japan_market_conditions import build_japan_conditions_context
from src.services.market_playbook import get_market_playbook
from src.services.sector_flow_service import (
    build_cross_market_context,
    build_sector_flow_context,
)
from src.stock_data_provider import get_valuation_metrics

MARKET_SUMMARY_FRESH_SECONDS = 300
MARKET_SUMMARY_STALE_SECONDS = 86400
MARKET_CONTEXT_CACHE_NAMESPACE = "market_context_cache"


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
        source="live_summary",
        fetched_at=_utc_now(),
        is_partial=bool(errors),
        quality_warnings=list(errors),
        errors=errors,
        cache_status="live",
    )
    if market_data:
        _save_context_cache(context, "summary")
    return context


def build_market_details_context(
    market_type: str = "US",
    market_context: MarketContext | dict[str, Any] | None = None,
) -> MarketContext:
    """Build non-option detailed monitoring data for explicit refresh actions."""

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

    def credit_stress_task() -> dict[str, Any]:
        return build_credit_stress_monitor(market_type)

    def flow_monitor_task() -> dict[str, Any]:
        return build_sector_flow_monitor(market_type)

    def distortions_task() -> dict[str, Any]:
        if market_type != "US":
            return {}
        return detect_market_distortions(market_type, max_themes=30, top_n=5)

    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = {
            "evaluation": executor.submit(evaluation_task),
            "ibd_regime": executor.submit(ibd_task),
            "microstructure": executor.submit(microstructure_task),
            "momentum": executor.submit(momentum_task),
            "monitor": executor.submit(monitor_task),
            "sector_flow": executor.submit(sector_flow_task),
            "credit_stress": executor.submit(credit_stress_task),
            "flow_monitor": executor.submit(flow_monitor_task),
            "market_distortions": executor.submit(distortions_task),
        }
        results = {
            name: _future_result(future, errors) for name, future in futures.items()
        }
    japan_conditions = _safe_call(
        lambda: build_japan_conditions_context(
            base.market_data, results.get("sector_flow") or {}
        ),
        {},
        errors,
    )
    cross_market = _safe_call(
        lambda: build_cross_market_context(results.get("sector_flow") or {}),
        {},
        errors,
    )
    ibd_regime = results.get("ibd_regime") or {}
    regime_playbook = (
        get_market_playbook(str(ibd_regime.get("status_key", ""))) if ibd_regime else {}
    )
    evaluation = _merge_ibd_signal(
        results.get("evaluation") or {},
        ibd_regime,
    )

    context = MarketContext(
        market_type=market_type,
        market_data=base.market_data,
        market_config=base.market_config,
        options=options,
        evaluation=evaluation,
        ibd_regime=ibd_regime,
        regime_playbook=regime_playbook,
        microstructure=results.get("microstructure") or {},
        momentum=results.get("momentum") or {},
        monitor=results.get("monitor") or {},
        market_distortions=results.get("market_distortions") or {},
        japan_conditions=japan_conditions,
        sector_flow=results.get("sector_flow") or {},
        credit_stress=results.get("credit_stress") or {},
        flow_monitor=results.get("flow_monitor") or {},
        cross_market=cross_market,
        data_status=[
            *base.data_status,
            DataResult(
                name="market_details",
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
                name="market_distortions",
                source="sector_theme_diagnostics",
                fetched_at=_utc_now(),
                is_partial=not bool(results.get("market_distortions")),
                error="; ".join(
                    (results.get("market_distortions") or {}).get(
                        "quality_warnings", []
                    )[:3]
                ),
                cache_status="computed",
            ),
            DataResult(
                name="sector_flow",
                source="sector_flow_service",
                fetched_at=_utc_now(),
                is_partial=not bool(results.get("sector_flow")),
                cache_status="live",
            ),
            DataResult(
                name="credit_stress",
                source=(results.get("credit_stress") or {}).get("source", ""),
                fetched_at=(results.get("credit_stress") or {}).get("fetched_at", ""),
                is_partial=bool(
                    (results.get("credit_stress") or {}).get("is_partial", False)
                ),
                error="; ".join(
                    (results.get("credit_stress") or {}).get("warnings", [])
                ),
                cache_status=(results.get("credit_stress") or {}).get(
                    "cache_status", "live"
                ),
                cache_age_seconds=_optional_float(
                    (results.get("credit_stress") or {}).get("cache_age_seconds")
                ),
            ),
            DataResult(
                name="flow_monitor",
                source=(results.get("flow_monitor") or {}).get("source", ""),
                fetched_at=_utc_now(),
                is_partial=bool(
                    (results.get("flow_monitor") or {}).get("is_partial", False)
                ),
                error="; ".join(
                    (results.get("flow_monitor") or {}).get("warnings", [])
                ),
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
        ],
        errors=errors,
        source="live_details",
        fetched_at=_utc_now(),
        is_stale=base.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings,
            options.quality_warnings,
            (results.get("sector_flow") or {}).get("quality_warnings", []),
            (results.get("credit_stress") or {}).get("warnings", []),
            (results.get("flow_monitor") or {}).get("warnings", []),
            ibd_regime.get("quality_warnings", []) if ibd_regime else [],
            (results.get("market_distortions") or {}).get("quality_warnings", []),
            japan_conditions.get("quality_warnings", []) if japan_conditions else [],
            errors,
        ),
        cache_status="live" if not base.is_stale else base.cache_status,
        cache_age_seconds=base.cache_age_seconds,
    )
    if context.market_data:
        _save_context_cache(context, "full")
    return context


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
        cross_market=base.cross_market,
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
    tnx_yield = float(tnx_df["Close"].iloc[-1]) / 10.0 if not tnx_df.empty else 4.0

    spy_pe = _extract_pe(get_valuation_metrics("SPY"), 22.0)
    ndx_pe = _extract_pe(get_valuation_metrics("QQQ"), 30.0)
    spread = evaluate_yield_spread(tnx_yield, {"SPY": spy_pe, "NDX": ndx_pe})

    return {
        "distribution_spy": dist_spy,
        "distribution_ndx": dist_ndx,
        "climax": climax,
        "yield_spread": spread,
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
    if context.options.quality_warnings:
        parts.append(
            "- Options data quality: " + "; ".join(context.options.quality_warnings[:6])
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
        parts.append(
            "- Yield spread: "
            f"{spread.get('overall_status', 'unknown')} "
            f"(10Y={float(spread.get('yield_10y', 0.0)):.2f}%)"
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
                    f"{item.get('theme')} gap={float(item.get('distortion_score', 0.0)):.2f}"
                    for item in bullish[:5]
                )
            )
        if bearish:
            parts.append(
                "- Bearish distortions: "
                + "; ".join(
                    f"{item.get('theme')} gap={float(item.get('distortion_score', 0.0)):.2f}"
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


def _extract_spy_pcr(option_data: list[dict[str, Any]] | None) -> float:
    if not option_data:
        return 0.8
    first = option_data[0]
    pcr = first.get("pcr", {})
    if isinstance(pcr, dict):
        return float(pcr.get("volume_pcr", 0.8))
    if isinstance(pcr, (int, float)):
        return float(pcr)
    return 0.8


def _extract_pe(info: dict[str, Any] | None, fallback: float) -> float:
    value = info.get("pe_ratio") if info else None
    return float(value) if isinstance(value, (int, float)) else fallback


def _nested(source: dict[str, Any], parent: str, child: str) -> str:
    value = source.get(parent) or {}
    return str(value.get(child, "unknown")) if isinstance(value, dict) else "unknown"


def _display_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2%}"
    return "unknown"


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
    return context


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
