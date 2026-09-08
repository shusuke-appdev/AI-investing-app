"""Cache-only market reference; it never changes individual-stock assessments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.services.market_context_cache import (
    context_from_cache_payload,
    market_context_cache,
    read_context_cache,
)

MARKET_CONTEXT_CACHE_NAMESPACE = "market_context_cache"
RISK_RANK = {"unknown": -1, "none": -1, "low": 0, "medium": 1, "high": 2, "extreme": 3}


def build_cached_market_risk_guardrail(
    ticker: str,
    stock_info: dict[str, Any] | None = None,
    sector_theme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read market risk for reference display without provider calls."""

    normalized = ticker.upper()
    if normalized.endswith(".T"):
        return _inactive(
            "not_applicable", "日本株は米国短期予測ガードレールの対象外です。"
        )
    cache = market_context_cache(MARKET_CONTEXT_CACHE_NAMESPACE)
    read = read_context_cache(
        cache,
        "US",
        "full",
        fresh_seconds=36 * 3600,
        stale_seconds=3 * 86400,
    )
    if not read.is_available:
        return _inactive("unavailable", "Market Watchの詳細更新後に利用できます。")
    context = context_from_cache_payload(read.payload)
    if read.is_stale or context.is_stale:
        return _inactive(
            "stale", "市場予測キャッシュが古いため評価へ反映しません。", is_stale=True
        )
    forecast = context.short_horizon_forecast or {}
    composite = context.composite_sentiment or {}
    as_of = str(
        forecast.get("as_of") or composite.get("as_of") or context.fetched_at or ""
    )
    if not _is_recent_business_as_of(as_of):
        return _inactive(
            "stale", "市場予測が直近米国営業日より古いため反映しません。", is_stale=True
        )

    targets = ["SPY"]
    if _is_technology_stock(stock_info or {}, sector_theme or {}):
        targets.append("QQQ")
    assessments = [
        _target_assessment(target, forecast, composite) for target in targets
    ]
    available = [item for item in assessments if item["available"]]
    if not available:
        return _inactive(
            "inactive",
            "検証済み予測または確認済み複合警戒がないため反映しません。",
        )
    worst = max(available, key=lambda item: RISK_RANK.get(item["risk_level"], -1))
    risk_level = worst["risk_level"]
    action_cap = (
        "protect"
        if risk_level == "extreme"
        else "watch"
        if risk_level == "high" or worst["downside_bias"]
        else "none"
    )
    return {
        "status": "active" if action_cap != "none" else "monitoring",
        "risk_level": risk_level,
        "action_cap": "none",
        "reference_targets": targets,
        "binding_target": worst["target"],
        "downside_bias": worst["downside_bias"],
        "summary": _summary(action_cap, worst),
        "reasons": worst["reasons"],
        "as_of": as_of,
        "source": "cached MarketContext.short_horizon_forecast+composite_sentiment",
        "is_stale": False,
        "probability_changed": False,
        "can_upgrade": False,
    }


def _target_assessment(
    target: str,
    forecast: dict[str, Any],
    composite: dict[str, Any],
) -> dict[str, Any]:
    risks: list[str] = []
    reasons: list[str] = []
    downside_bias = False
    target_forecast = (forecast.get("targets") or {}).get(target) or {}
    if not forecast.get("is_stale"):
        for horizon in ("1d", "5d", "20d"):
            item = (target_forecast.get("horizons") or {}).get(horizon) or {}
            if item.get("status") != "validated" or item.get("is_stale"):
                continue
            risk = str(item.get("risk_level") or "unknown")
            risks.append(risk)
            if horizon in {"5d", "20d"} and item.get("direction") == "downside_bias":
                downside_bias = True
            reasons.append(
                f"{target} {horizon}: {item.get('direction_label', '')} / risk={risk}"
            )
    target_composite = (composite.get("targets") or {}).get(target) or {}
    if (
        composite.get("integration_enabled")
        and target_composite.get("status") == "confirmed"
    ):
        risk = str(target_composite.get("risk_floor") or "none")
        risks.append(risk)
        reasons.append(
            f"{target} 複合判定: {target_composite.get('state_label', '')} / floor={risk}"
        )
    risk_level = (
        max(risks, key=lambda item: RISK_RANK.get(item, -1)) if risks else "unknown"
    )
    return {
        "target": target,
        "available": bool(risks),
        "risk_level": risk_level,
        "downside_bias": downside_bias,
        "reasons": reasons,
    }


def _is_technology_stock(
    stock_info: dict[str, Any], sector_theme: dict[str, Any]
) -> bool:
    values = [
        stock_info.get("sector"),
        sector_theme.get("parent_sector"),
        sector_theme.get("best_theme"),
        *(sector_theme.get("themes") or []),
    ]
    text = " ".join(str(value or "").lower() for value in values)
    return any(
        keyword in text
        for keyword in (
            "technology",
            "semiconductor",
            "software",
            "半導体",
            "テクノロジー",
        )
    )


def _is_recent_business_as_of(value: str) -> bool:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return False
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    previous_business_day = today - pd.offsets.BDay(1)
    return parsed.tz_convert(None).normalize() >= previous_business_day.normalize()


def _summary(action_cap: str, assessment: dict[str, Any]) -> str:
    if action_cap == "protect":
        return f"市場参考: {assessment['target']}で極端なリスクを検出。個別銘柄の条件判定は変更しません。"
    if action_cap == "watch":
        return f"市場参考: {assessment['target']}で警戒情報を検出。個別銘柄の条件判定は変更しません。"
    return "市場予測は監視中ですが、現在のStock評価は変更しません。"


def _inactive(status: str, summary: str, *, is_stale: bool = False) -> dict[str, Any]:
    return {
        "status": status,
        "risk_level": "unknown",
        "action_cap": "none",
        "reference_targets": [],
        "binding_target": "",
        "downside_bias": False,
        "summary": summary,
        "reasons": [],
        "as_of": "",
        "source": "cached MarketContext",
        "is_stale": is_stale,
        "probability_changed": False,
        "can_upgrade": False,
    }
