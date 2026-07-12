"""Stock feature-health presentation helpers."""

from typing import Any

import pandas as pd

from src.services.stock_dashboard_service import _display_text


def _feature_health_item(
    feature: str,
    label: str,
    source: str,
    value: Any,
    detail: str,
    status_key: str,
    effect: str,
    required: bool,
) -> dict[str, Any]:
    return {
        "feature": feature,
        "label": label,
        "source": source,
        "value": "算出不可" if value in (None, "") else str(value),
        "detail": detail,
        "status_key": status_key,
        "status_label": _feature_status_label(status_key),
        "effect": effect,
        "required": required,
    }


def _feature_status_label(status_key: str) -> str:
    return {
        "ok": "OK",
        "partial": "一部評価",
        "capped": "上限あり",
        "unavailable": "算出不可",
    }.get(status_key, status_key)


def _score_display(value: float | None) -> str:
    return "算出不可" if value is None else f"{value:.0f}/100"


def _entry_health_status(status: str, score: float | None) -> str:
    if score is None or status == "insufficient_data":
        return "unavailable"
    if status == "blocked":
        return "capped"
    if status and status != "ready":
        return "partial"
    return "ok"


def _entry_health_detail(status: str, trade_setup: dict[str, Any]) -> str:
    if not trade_setup:
        return "Entry Frameworkがありません。"
    blocked = [str(item) for item in trade_setup.get("blocked_reasons", [])]
    warnings = [str(item) for item in trade_setup.get("warnings", [])]
    if blocked:
        return "; ".join(blocked)
    if warnings:
        return "; ".join(warnings[:3])
    return str(trade_setup.get("summary") or status or "OK")


def _fundamental_health_status(status: str, score: float | None) -> str:
    if score is None or status not in {"available", "partial"}:
        return "unavailable"
    return "partial" if status == "partial" else "ok"


def _fundamental_health_detail(status: str, profile: dict[str, Any]) -> str:
    missing = [str(item) for item in profile.get("missing_reasons", [])]
    caps = [str(item) for item in profile.get("cap_reasons", [])]
    if missing:
        return "; ".join(missing[:3])
    if caps:
        return "; ".join(caps[:3])
    return str(profile.get("summary") or status or "OK")


def _cap_effect_detail(
    probabilistic_signal: dict[str, Any],
    fomo_regime: dict[str, Any],
    technical: dict[str, Any],
) -> str:
    parts = []
    action = str(probabilistic_signal.get("suggested_action") or "")
    confidence = str(probabilistic_signal.get("confidence") or "")
    risk = str(fomo_regime.get("risk_level") or "")
    stage_data = technical.get("stage_data")
    stage = stage_data.get("stage") if isinstance(stage_data, dict) else None
    if action:
        parts.append(f"確率={action}")
    if confidence:
        parts.append(f"信頼度={confidence}")
    if risk:
        parts.append(f"FOMO={risk}")
    if stage not in (None, ""):
        parts.append(f"Stage={stage}")
    return " / ".join(parts) if parts else "上限判定の補助入力。"


def _purchase_health_detail(
    status: str, missing_reasons: list[str], cap_reasons: list[str]
) -> str:
    if missing_reasons:
        return "; ".join(missing_reasons)
    if cap_reasons:
        return "上限: " + "; ".join(cap_reasons)
    return "OK" if status == "available" else "根拠一致度を算出できません。"


def _smart_has_unknowns(value: dict[str, Any]) -> bool:
    if not value:
        return True
    return any(
        isinstance(value.get(key), dict)
        and str(value[key].get("status") or "") == "unknown"
        for key in ("S", "M", "A", "R", "T")
    )


def _smart_error_message(value: dict[str, Any]) -> str:
    if not value:
        return "SMART criteria unavailable."
    missing = []
    for key in ("S", "M", "A", "R", "T"):
        item = value.get(key)
        if isinstance(item, dict) and str(item.get("status") or "") == "unknown":
            missing.append(f"{key}: {item.get('value') or '入力データ不足'}")
    return "; ".join(missing)


def _is_limited_profile(info: dict[str, Any]) -> bool:
    if not info:
        return True
    ticker = _display_text(info.get("ticker"))
    name = _display_text(info.get("name"))
    has_named_profile = bool(name and name != ticker and name != "N/A")
    has_business_text = any(
        _display_text(info.get(key)) not in {"", "N/A"}
        for key in ("summary", "sector", "industry")
    )
    return not (has_named_profile or has_business_text)


def _profile_warning_message(info: dict[str, Any]) -> str:
    if _is_limited_profile(info):
        return "企業概要の一部を取得できませんでした。価格・テクニカル分析は取得済みデータで表示しています。"
    return ""


def _dashboard_error_message(
    info: dict[str, Any],
    history_df: pd.DataFrame | None,
) -> str:
    has_history = history_df is not None and not history_df.empty
    if not info and not has_history:
        return "銘柄データを取得できませんでした。ティッカーとデータプロバイダー設定を確認してください。"
    return ""
