"""Market monitoring orchestration shared by Reflex state and AI reporting."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.advisor.market_environment import evaluate_market_environment
from src.advisor.market_monitor import (
    detect_market_climax,
    evaluate_yield_spread,
    track_distribution_days,
)
from src.market_config import get_market_config
from src.market_data import get_market_indices, get_stock_data
from src.market_microstructure import analyze_market_structure
from src.momentum_monitor import get_momentum_themes
from src.option_analyst import get_major_indices_option_status
from src.services.analysis_context import MarketContext, OptionContext
from src.stock_data_provider import get_valuation_metrics

MARKET_SUMMARY_FRESH_SECONDS = 300
MARKET_SUMMARY_STALE_SECONDS = 86400


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
        source="live_summary",
        fetched_at=_utc_now(),
        is_partial=bool(errors),
        quality_warnings=list(errors),
        errors=errors,
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

    def microstructure_task() -> dict[str, Any]:
        return _normalize_microstructure(analyze_market_structure("SPY"))

    def momentum_task() -> dict[str, list[dict[str, Any]]]:
        return get_momentum_themes(market_type)

    def monitor_task() -> dict[str, Any]:
        return build_market_monitor_context(options.items)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            "evaluation": executor.submit(evaluation_task),
            "microstructure": executor.submit(microstructure_task),
            "momentum": executor.submit(momentum_task),
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
        evaluation=results.get("evaluation") or {},
        microstructure=results.get("microstructure") or {},
        momentum=results.get("momentum") or {},
        monitor=results.get("monitor") or {},
        errors=errors,
        source="live_details",
        fetched_at=_utc_now(),
        is_stale=base.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings, options.quality_warnings, errors
        ),
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
        evaluation=results.get("evaluation") or base.evaluation,
        microstructure=base.microstructure,
        momentum=base.momentum,
        monitor=results.get("monitor") or base.monitor,
        errors=errors,
        source="live_options",
        fetched_at=_utc_now(),
        is_stale=base.is_stale or options.is_stale,
        is_partial=bool(errors) or base.is_partial or options.is_partial,
        quality_warnings=_merge_warnings(
            base.quality_warnings, options.quality_warnings, errors
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
        )
    except Exception as exc:
        return OptionContext(
            error_message=f"Option analysis failed: {exc}",
            status="failed",
            source="yfinance",
            is_partial=True,
            quality_warnings=[f"Option analysis failed: {exc}"],
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


def _context_cache_path(market_type: str, kind: str) -> Path:
    root = Path(__file__).resolve().parents[2] / ".states" / "market_context_cache"
    return root / f"{market_type.lower()}_{kind}.json"


def _save_context_cache(context: MarketContext, kind: str) -> None:
    path = _context_cache_path(context.market_type, kind)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(context.to_dict(), ensure_ascii=False, default=str),
            encoding="utf-8",
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
    path = _context_cache_path(market_type, kind)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    context = MarketContext.from_mapping(raw)
    age = _context_age_seconds(context)
    if age is None or age > max_age_seconds:
        return None
    context.source = f"{context.source or kind}_cache"
    context.is_stale = age > fresh_seconds
    if context.is_stale:
        context.quality_warnings = _merge_warnings(
            context.quality_warnings,
            [f"Using cached market summary from {context.fetched_at}."],
        )
    return context


def _context_age_seconds(context: MarketContext) -> float | None:
    if not context.fetched_at:
        return None
    try:
        fetched_at = datetime.fromisoformat(context.fetched_at)
    except ValueError:
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - fetched_at).total_seconds()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
