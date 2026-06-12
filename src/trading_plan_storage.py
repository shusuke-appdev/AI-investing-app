"""Local-first and Supabase storage for manual trading plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.app_mode import require_writes_enabled
from src.log_config import get_logger
from src.services.trading_plan_service import TradePlanRecord
from src.settings_storage import get_storage_type
from src.storage.atomic_json import read_json, update_json, write_json
from src.supabase_client import get_supabase_client

logger = get_logger(__name__)
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "trading_plans.json"


def save_trade_plan(plan: TradePlanRecord) -> bool:
    require_writes_enabled()
    storage_type = get_storage_type()
    if storage_type == "supabase":
        return _save_supabase(plan)
    return _save_local(plan)


def load_trade_plans() -> list[TradePlanRecord]:
    storage_type = get_storage_type()
    raw = _load_supabase() if storage_type == "supabase" else _load_local()
    plans = [
        TradePlanRecord.from_mapping(item) for item in raw if isinstance(item, dict)
    ]
    return sorted(plans, key=lambda item: item.updated_at, reverse=True)


def get_trade_plan(plan_id: str) -> TradePlanRecord | None:
    return next((plan for plan in load_trade_plans() if plan.plan_id == plan_id), None)


def delete_trade_plan(plan_id: str) -> bool:
    require_writes_enabled()
    if get_storage_type() == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        client.table("trade_plans").delete().eq("id", plan_id).execute()
        return True
    deleted = False

    def remove(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal deleted
        updated = [plan for plan in plans if plan.get("plan_id") != plan_id]
        deleted = len(updated) < len(plans)
        return updated

    update_json(DATA_PATH, [], remove)
    return deleted


def _save_local(plan: TradePlanRecord) -> bool:
    payload = plan.to_dict()

    def upsert(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        index = next(
            (
                idx
                for idx, item in enumerate(plans)
                if item.get("plan_id") == plan.plan_id
            ),
            None,
        )
        if index is None:
            plans.append(payload)
        else:
            plans[index] = payload
        return plans

    update_json(DATA_PATH, [], upsert)
    return True


def _load_local() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        value = read_json(DATA_PATH, [])
        return value if isinstance(value, list) else []
    except (OSError, ValueError) as exc:
        logger.error("Trading plan local load failed: %s", exc)
        return []


def _write_local(plans: list[dict[str, Any]]) -> None:
    write_json(DATA_PATH, plans)


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
