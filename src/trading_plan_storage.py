"""Local-first and Supabase storage for manual trading plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.log_config import get_logger
from src.services.trading_plan_service import TradePlanRecord
from src.settings_storage import get_storage_type
from src.supabase_client import get_supabase_client

logger = get_logger(__name__)
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "trading_plans.json"


def save_trade_plan(plan: TradePlanRecord) -> bool:
    storage_type = get_storage_type()
    if storage_type == "gas":
        raise ValueError("Trading PlanのGAS保存は初回実装では未対応です。")
    if storage_type == "supabase":
        return _save_supabase(plan)
    return _save_local(plan)


def load_trade_plans() -> list[TradePlanRecord]:
    storage_type = get_storage_type()
    if storage_type == "gas":
        raise ValueError("Trading PlanのGAS保存は初回実装では未対応です。")
    raw = _load_supabase() if storage_type == "supabase" else _load_local()
    plans = [
        TradePlanRecord.from_mapping(item) for item in raw if isinstance(item, dict)
    ]
    return sorted(plans, key=lambda item: item.updated_at, reverse=True)


def get_trade_plan(plan_id: str) -> TradePlanRecord | None:
    return next((plan for plan in load_trade_plans() if plan.plan_id == plan_id), None)


def delete_trade_plan(plan_id: str) -> bool:
    if get_storage_type() == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        client.table("trade_plans").delete().eq("id", plan_id).execute()
        return True
    plans = [plan for plan in _load_local() if plan.get("plan_id") != plan_id]
    _write_local(plans)
    return True


def _save_local(plan: TradePlanRecord) -> bool:
    plans = _load_local()
    payload = plan.to_dict()
    index = next(
        (idx for idx, item in enumerate(plans) if item.get("plan_id") == plan.plan_id),
        None,
    )
    if index is None:
        plans.append(payload)
    else:
        plans[index] = payload
    _write_local(plans)
    return True


def _load_local() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        value = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Trading plan local load failed: %s", exc)
        return []


def _write_local(plans: list[dict[str, Any]]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(plans, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_supabase(plan: TradePlanRecord) -> bool:
    client = get_supabase_client()
    if not client:
        return False
    payload = {
        "id": plan.plan_id,
        "ticker": plan.ticker,
        "status": plan.status,
        "entry_date": plan.entry_date,
        "payload": plan.to_dict(),
        "updated_at": plan.updated_at,
    }
    client.table("trade_plans").upsert(payload, on_conflict="id").execute()
    return True


def _load_supabase() -> list[dict[str, Any]]:
    client = get_supabase_client()
    if not client:
        return []
    response = client.table("trade_plans").select("*").execute()
    return [
        dict(item.get("payload") or {})
        for item in response.data or []
        if isinstance(item, dict)
    ]
