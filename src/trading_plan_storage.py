"""Local-first and Supabase storage for manual trading plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.app_mode import require_personal_data_enabled, require_writes_enabled
from src.log_config import get_logger
from src.services.trading_plan_service import TradePlanRecord
from src.settings_storage import get_storage_type
from src.storage.atomic_json import read_json, update_json, write_json
from src.storage.result import StorageResult, available, unavailable
from src.storage.supabase_paging import fetch_all_rows
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
    return load_trade_plans_result().data


def load_trade_plans_result() -> StorageResult[list[TradePlanRecord]]:
    require_personal_data_enabled()
    storage_type = get_storage_type()
    result = (
        _load_supabase_result() if storage_type == "supabase" else _load_local_result()
    )
    plans = [
        TradePlanRecord.from_mapping(item)
        for item in result.data
        if isinstance(item, dict)
    ]
    return StorageResult(
        data=sorted(plans, key=lambda item: item.updated_at, reverse=True),
        backend=result.backend,
        status=result.status,
        warnings=result.warnings,
        error_code=result.error_code,
    )


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
    return _load_local_result().data


def _load_local_result() -> StorageResult[list[dict[str, Any]]]:
    if not DATA_PATH.exists():
        return available([], "local")
    try:
        value = read_json(DATA_PATH, [])
        if not isinstance(value, list):
            raise ValueError("Trading plan storage root must be a list.")
        return available(value, "local")
    except (OSError, ValueError) as exc:
        logger.error("Trading plan local load failed: %s", exc)
        return unavailable(
            [],
            "local",
            warning="取引計画ファイルを読み込めません。",
            error_code="local_read_failed",
        )


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
    return _load_supabase_result().data


def _load_supabase_result() -> StorageResult[list[dict[str, Any]]]:
    client = get_supabase_client()
    if not client:
        return unavailable(
            [],
            "supabase",
            warning="Supabaseへ接続できません。保存済みデータは削除されていません。",
            error_code="backend_unconfigured",
        )
    try:
        rows = fetch_all_rows(client, "trade_plans", "*", order_column="id")
        return available(
            [
                dict(item.get("payload") or {})
                for item in rows
                if isinstance(item, dict)
            ],
            "supabase",
        )
    except Exception as exc:
        logger.error("Trading plan Supabase load failed: %s", exc)
        return unavailable(
            [],
            "supabase",
            warning="Supabaseの取引計画を取得できません。",
            error_code="backend_read_failed",
        )
