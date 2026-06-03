"""Sector and theme flow diagnostics for market monitoring."""

from __future__ import annotations

from statistics import mean
from typing import Any

import pandas as pd

from src.log_config import get_logger
from src.market_config import get_market_config
from src.market_data import get_stock_data
from src.persistent_cache import utc_now_iso
from src.themes_config import get_themes

logger = get_logger(__name__)

US_BENCHMARK = "SPY"
JP_BENCHMARK = "^N225"
MAX_GROUPS_PER_MARKET = 12
MAX_TICKERS_PER_GROUP = 8


def build_sector_flow_context() -> dict[str, Any]:
    """Identify likely sector/theme inflows for US and Japan."""

    markets = {
        "US": _build_market_flow("US"),
        "JP": _build_market_flow("JP"),
    }
    warnings = []
    for payload in markets.values():
        warnings.extend(payload.get("quality_warnings", []))

    return {
        "generated_at": utc_now_iso(),
        "primary_market": "US",
        "markets": markets,
        "summary": _summarize_markets(markets),
        "quality_warnings": _dedupe(warnings),
    }


def build_cross_market_context(
    sector_flow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize US-versus-Japan leadership without separating the recap."""

    flow = sector_flow or build_sector_flow_context()
    us = flow.get("markets", {}).get("US", {})
    jp = flow.get("markets", {}).get("JP", {})
    us_top = _first_leader(us)
    jp_top = _first_leader(jp)

    us_score = float(us_top.get("flow_score", 0.0)) if us_top else 0.0
    jp_score = float(jp_top.get("flow_score", 0.0)) if jp_top else 0.0
    relative = jp_score - us_score
    if relative >= 20:
        stance = "Japan relative flow is stronger, but treat it as a US-linked satellite theme."
    elif relative <= -20:
        stance = "US flow leadership remains dominant; Japan is supplemental."
    else:
        stance = "US and Japan flow strength is mixed; use cross-market confirmation."

    return {
        "primary_market": "US",
        "us_leader": us_top,
        "jp_leader": jp_top,
        "relative_flow_score": round(relative, 1),
        "stance": stance,
    }


def _build_market_flow(market_type: str) -> dict[str, Any]:
    benchmark_ticker = JP_BENCHMARK if market_type == "JP" else US_BENCHMARK
    benchmark = _ticker_snapshot(benchmark_ticker)
    groups = _candidate_groups(market_type)
    leaders = []
    warnings = []

    if benchmark.get("available") is False:
        warnings.append(f"{market_type} benchmark data is unavailable.")

    for group_name, tickers in groups.items():
        payload = _score_group(
            market_type=market_type,
            group_name=group_name,
            tickers=tickers[:MAX_TICKERS_PER_GROUP],
            benchmark=benchmark,
        )
        if payload:
            leaders.append(payload)

    leaders.sort(key=lambda item: item["flow_score"], reverse=True)
    visible = leaders[:5]
    if not visible:
        warnings.append(f"{market_type} sector flow could not be calculated.")

    return {
        "market": market_type,
        "benchmark": benchmark,
        "leaders": visible,
        "summary": _summarize_market(market_type, visible),
        "quality_warnings": warnings,
    }


def _candidate_groups(market_type: str) -> dict[str, list[str]]:
    if market_type == "JP":
        themes = get_themes("JP")
        return dict(list(themes.items())[:MAX_GROUPS_PER_MARKET])
    sectors = get_market_config("US").get("sectors", {})
    return {name: [ticker] for name, ticker in sectors.items()}


def _score_group(
    *,
    market_type: str,
    group_name: str,
    tickers: list[str],
    benchmark: dict[str, Any],
) -> dict[str, Any] | None:
    snapshots = [_ticker_snapshot(ticker) for ticker in tickers]
    available = [item for item in snapshots if item.get("available")]
    if not available:
        return None

    one_day = mean([item["change_1d"] for item in available])
    five_day = mean([item["change_5d"] for item in available])
    twenty_day = mean([item["change_20d"] for item in available])
    volume_ratio = mean([item["volume_ratio"] for item in available])
    participation = sum(1 for item in available if item["change_1d"] > 0) / len(
        available
    )
    coverage = len(available) / max(len(tickers), 1)
    benchmark_1d = float(benchmark.get("change_1d", 0.0) or 0.0)
    relative_1d = one_day - benchmark_1d

    raw_score = (
        relative_1d * 12.0
        + max(five_day, 0.0) * 3.0
        + (volume_ratio - 1.0) * 20.0
        + (participation - 0.5) * 30.0
    )
    flow_score = round(_clamp(raw_score, -100.0, 100.0), 1)
    confidence = _confidence_label(flow_score, volume_ratio, participation, coverage)
    continuation = _continuation_label(five_day, twenty_day, participation)

    return {
        "market": market_type,
        "theme": group_name,
        "tickers": [item["ticker"] for item in available],
        "flow_score": flow_score,
        "confidence": confidence,
        "continuation": continuation,
        "action": _action_label(flow_score, confidence, continuation),
        "change_1d": round(one_day, 2),
        "change_5d": round(five_day, 2),
        "change_20d": round(twenty_day, 2),
        "relative_1d": round(relative_1d, 2),
        "volume_ratio": round(volume_ratio, 2),
        "participation": round(participation, 2),
        "coverage": round(coverage, 2),
        "evidence": _evidence_text(relative_1d, volume_ratio, participation, coverage),
    }


def _ticker_snapshot(ticker: str) -> dict[str, Any]:
    try:
        df = get_stock_data(ticker, "3mo")
    except Exception as exc:
        logger.debug("Sector flow data fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "available": False}

    if df.empty or "Close" not in df.columns:
        return {"ticker": ticker, "available": False}

    normalized = df.copy()
    normalized = normalized.dropna(subset=["Close"])
    if len(normalized) < 2:
        return {"ticker": ticker, "available": False}

    closes = normalized["Close"].astype(float)
    volumes = (
        normalized["Volume"].astype(float)
        if "Volume" in normalized.columns
        else pd.Series([0.0] * len(normalized), index=normalized.index)
    )

    current = float(closes.iloc[-1])
    prev_1 = _prior_value(closes, 1)
    prev_5 = _prior_value(closes, 5)
    prev_20 = _prior_value(closes, 20)
    latest_volume = float(volumes.iloc[-1]) if len(volumes) else 0.0
    avg_volume = float(volumes.tail(20).mean()) if len(volumes) else 0.0
    volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0

    return {
        "ticker": ticker,
        "available": True,
        "change_1d": _pct_change(current, prev_1),
        "change_5d": _pct_change(current, prev_5),
        "change_20d": _pct_change(current, prev_20),
        "volume_ratio": float(_clamp(volume_ratio, 0.0, 5.0)),
    }


def _prior_value(series: pd.Series, periods: int) -> float:
    if len(series) > periods:
        return float(series.iloc[-periods - 1])
    return float(series.iloc[0])


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100.0


def _confidence_label(
    flow_score: float, volume_ratio: float, participation: float, coverage: float
) -> str:
    if coverage < 0.4:
        return "低"
    if abs(flow_score) >= 45 and volume_ratio >= 1.05 and participation >= 0.6:
        return "高"
    if abs(flow_score) >= 25 and coverage >= 0.6:
        return "中"
    return "低"


def _continuation_label(
    change_5d: float, change_20d: float, participation: float
) -> str:
    if change_5d > 0 and change_20d > 0 and participation >= 0.6:
        return "高"
    if change_5d > 0 and participation >= 0.5:
        return "中"
    return "低"


def _action_label(flow_score: float, confidence: str, continuation: str) -> str:
    if flow_score < 0:
        return "見送り"
    if confidence == "高" and continuation in {"高", "中"}:
        return "乗る候補"
    if confidence in {"高", "中"} and flow_score >= 25:
        return "押し目待ち"
    return "観察"


def _evidence_text(
    relative_1d: float, volume_ratio: float, participation: float, coverage: float
) -> str:
    return (
        f"relative_1d={relative_1d:+.2f}pt, "
        f"volume={volume_ratio:.2f}x, "
        f"participation={participation:.0%}, "
        f"coverage={coverage:.0%}"
    )


def _summarize_market(market_type: str, leaders: list[dict[str, Any]]) -> str:
    label = "日本" if market_type == "JP" else "米国"
    if not leaders:
        return f"{label}市場の資金流入セクターは判定不能。"
    top = leaders[0]
    return (
        f"{label}市場は {top['theme']} が首位。"
        f"確信度 {top['confidence']}、継続性 {top['continuation']}、"
        f"判断 {top['action']}。"
    )


def _summarize_markets(markets: dict[str, Any]) -> str:
    us = _first_leader(markets.get("US", {}))
    jp = _first_leader(markets.get("JP", {}))
    if not us and not jp:
        return "日米とも資金流入セクターを判定できない。"
    parts = []
    if us:
        parts.append(f"米国: {us['theme']}({us['flow_score']:+.1f})")
    if jp:
        parts.append(f"日本: {jp['theme']}({jp['flow_score']:+.1f})")
    return " / ".join(parts)


def _first_leader(payload: dict[str, Any]) -> dict[str, Any]:
    leaders = payload.get("leaders") or []
    return leaders[0] if leaders else {}


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
