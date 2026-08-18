"""Supabase personal-data schema readiness contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PERSONAL_DATA_SCHEMA_VERSION = 1
PERSONAL_DATA_TABLES = (
    "user_settings",
    "portfolios",
    "knowledge_items",
    "trade_plans",
)


@dataclass(frozen=True)
class StorageReadiness:
    ready: bool
    schema_version: int | None = None
    missing_tables: list[str] = field(default_factory=list)
    invalid_columns: list[str] = field(default_factory=list)
    invalid_grants: list[str] = field(default_factory=list)
    error_code: str = ""


def check_supabase_readiness(client: Any) -> StorageReadiness:
    """Verify the versioned RPC and every required personal-data table."""

    if client is None:
        return StorageReadiness(False, error_code="backend_unconfigured")
    try:
        response = client.rpc("personal_data_schema_readiness", {}).execute()
        payload = response.data
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict):
            return StorageReadiness(False, error_code="invalid_readiness_payload")
        version = int(payload.get("schema_version") or 0)
        tables = (
            payload.get("tables") if isinstance(payload.get("tables"), dict) else {}
        )
        columns = (
            payload.get("columns") if isinstance(payload.get("columns"), dict) else {}
        )
        grants = (
            payload.get("grants") if isinstance(payload.get("grants"), dict) else {}
        )
        missing = [
            name for name in PERSONAL_DATA_TABLES if tables.get(name) is not True
        ]
        invalid_columns = [
            name for name in PERSONAL_DATA_TABLES if columns.get(name) is not True
        ]
        invalid_grants = [
            name for name in PERSONAL_DATA_TABLES if grants.get(name) is not True
        ]
        return StorageReadiness(
            ready=(
                version == PERSONAL_DATA_SCHEMA_VERSION
                and not missing
                and not invalid_columns
                and not invalid_grants
            ),
            schema_version=version,
            missing_tables=missing,
            invalid_columns=invalid_columns,
            invalid_grants=invalid_grants,
            error_code=(
                "schema_version_mismatch"
                if version != PERSONAL_DATA_SCHEMA_VERSION
                else "missing_tables"
                if missing
                else "invalid_columns"
                if invalid_columns
                else "invalid_grants"
                if invalid_grants
                else ""
            ),
        )
    except Exception:
        return StorageReadiness(False, error_code="readiness_rpc_unavailable")
