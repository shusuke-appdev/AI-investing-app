"""
Migrate local JSON data to Supabase tables.

The default mode is a dry run. Remote writes require ``--execute``. Remote table
clearing additionally requires ``--confirm-destroy`` and a successful backup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.supabase_paging import fetch_all_rows
from src.supabase_client import get_supabase_client

TABLES = ("user_settings", "portfolios", "knowledge_items", "trade_plans")
SETUP_SQL_PATH = Path(__file__).parent.parent / "supabase" / "public_tables.sql"
CLEAR_FILTERS = {
    "user_settings": ("key", "__migration_sentinel__"),
    "portfolios": ("name", "__migration_sentinel__"),
    "knowledge_items": ("id", "__migration_sentinel__"),
    "trade_plans": ("id", "__migration_sentinel__"),
}
PRIMARY_KEYS = {
    "user_settings": "key",
    "portfolios": "name",
    "knowledge_items": "id",
    "trade_plans": "id",
}


class LocalPayloadError(ValueError):
    """Local source data is incomplete or invalid; remote writes must stop."""


@dataclass(frozen=True)
class MigrationOptions:
    """Supabase migration execution options."""

    dry_run: bool = True
    confirm_destroy: bool = False
    tables: tuple[str, ...] = TABLES
    backup_dir: Path = Path(".states/supabase_backups")
    allow_empty: tuple[str, ...] = ()
    restore_manifest: Path | None = None
    print_setup_sql: bool = False


def parse_args(argv: list[str] | None = None) -> MigrationOptions:
    """Parse CLI arguments into migration options."""

    parser = argparse.ArgumentParser(description="Migrate local data to Supabase.")
    parser.add_argument(
        "--restore-manifest",
        type=Path,
        help="Restore a verified backup manifest through the transactional stage/RPC path.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write local data to Supabase. Omit for dry-run mode.",
    )
    parser.add_argument(
        "--confirm-destroy",
        action="store_true",
        help="Transactionally replace selected remote tables. Requires --execute.",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=TABLES,
        default=list(TABLES),
        help="Tables to migrate. Defaults to all supported tables.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path(".states/supabase_backups"),
        help="Git-ignored directory for pre-replace Supabase backups.",
    )
    parser.add_argument(
        "--allow-empty",
        nargs="*",
        choices=TABLES,
        default=[],
        help="Explicitly allow selected tables to be replaced with zero rows.",
    )
    parser.add_argument(
        "--print-setup-sql",
        action="store_true",
        help="Print the Supabase table setup SQL with explicit Data API grants.",
    )
    args = parser.parse_args(argv)
    return MigrationOptions(
        dry_run=not args.execute,
        confirm_destroy=bool(args.confirm_destroy),
        tables=tuple(args.tables),
        backup_dir=args.backup_dir,
        allow_empty=tuple(args.allow_empty),
        restore_manifest=args.restore_manifest,
        print_setup_sql=bool(args.print_setup_sql),
    )


def load_json_robust(path: Path) -> Any:
    """Try to load JSON with utf-8, then cp932 for older local files."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="cp932"))


def migrate(options: MigrationOptions | None = None) -> int:
    """Run the migration and return a process-style exit code."""

    options = options or parse_args()
    if options.print_setup_sql:
        print(load_setup_sql())
        return 0

    if options.restore_manifest is not None:
        if options.confirm_destroy:
            print("[ERR] --restore-manifest cannot be combined with --confirm-destroy.")
            return 1
        try:
            restore_payload, restore_tables = load_backup_manifest(
                options.restore_manifest
            )
        except LocalPayloadError as exc:
            print(f"[ERR] Backup validation failed: {exc}")
            return 1
        print("=== Supabase Restore Tool ===")
        print_migration_plan(restore_payload)
        if options.dry_run:
            print("\nRestore dry run only. Re-run with --execute after review.")
            return 0
        client = get_supabase_client()
        if not client:
            print("[ERR] Could not connect to Supabase for restore.")
            return 1
        if backup_remote_tables(client, restore_tables, options.backup_dir) is None:
            print("[ERR] Current remote backup failed. Restore was not started.")
            return 1
        try:
            replace_remote_tables(client, restore_payload, restore_tables)
        except Exception as exc:
            print(f"[ERR] Transactional restore failed: {exc}")
            return 1
        print("\n=== Restore Complete ===")
        return 0

    print("=== Supabase Migration Tool ===")
    print(f"Mode: {'dry-run' if options.dry_run else 'execute'}")
    print("Tables: " + ", ".join(options.tables))

    try:
        local_payload = collect_local_payload(options.tables)
    except LocalPayloadError as exc:
        print(f"[ERR] Local data validation failed: {exc}")
        return 1
    print_migration_plan(local_payload)

    if options.dry_run:
        print("\nDry run only. Re-run with --execute to write to Supabase.")
        return 0

    client = get_supabase_client()
    if not client:
        print(
            "Error: Could not connect to Supabase. Check SUPABASE_URL and "
            "SUPABASE_SECRET_KEY, SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_KEY."
        )
        return 1

    if options.confirm_destroy:
        empty_tables = [
            table
            for table in options.tables
            if not local_payload.get(table) and table not in options.allow_empty
        ]
        if empty_tables:
            print(
                "[ERR] Refusing to replace non-approved empty tables: "
                + ", ".join(empty_tables)
            )
            return 1
        manifest = backup_remote_tables(client, options.tables, options.backup_dir)
        if manifest is None:
            print("[ERR] Remote backup failed. Aborting transactional replace.")
            return 1
        try:
            replace_remote_tables(client, local_payload, options.tables)
        except Exception as exc:
            print(
                "[ERR] Transactional replace or read-back verification failed; "
                f"inspect remote state and restore the manifest: {exc}"
            )
            return 1
    else:
        print(
            "Remote rows will only be upserted. Use --confirm-destroy for a "
            "validated transactional replace."
        )
        upload_payload(client, local_payload)
    print("\n=== Migration Complete ===")
    return 0


def collect_local_payload(tables: tuple[str, ...]) -> dict[str, Any]:
    """Collect local data for the selected tables."""

    payload: dict[str, Any] = {}
    if "user_settings" in tables:
        updated_at = current_utc_iso()
        payload["user_settings"] = [
            {"key": key, "value": str(value), "updated_at": updated_at}
            for key, value in collect_local_settings().items()
        ]
    if "portfolios" in tables:
        payload["portfolios"] = collect_portfolio_payloads()
    if "knowledge_items" in tables:
        payload["knowledge_items"] = collect_knowledge_payloads()
    if "trade_plans" in tables:
        payload["trade_plans"] = collect_trade_plan_payloads()
    return payload


def collect_local_settings() -> dict[str, Any]:
    """Load local settings without merging from remote Supabase."""

    candidates = [
        Path(__file__).parent.parent / "data" / "settings.json",
        Path("data/settings.json").resolve(),
    ]
    for path in candidates:
        if not path.exists():
            continue
        data = load_json_robust(path)
        if not isinstance(data, dict):
            raise LocalPayloadError(f"{path} must contain a JSON object")
        return data
    return {}


def collect_portfolio_payloads() -> list[dict[str, Any]]:
    """Load local portfolio JSON files as Supabase payloads."""

    portfolio_dir = Path(__file__).parent.parent / "data" / "portfolios"
    if not portfolio_dir.exists():
        return []

    payloads = []
    for portfolio_file in portfolio_dir.glob("*.json"):
        try:
            data = load_json_robust(portfolio_file)
            now = current_utc_iso()
            payloads.append(
                {
                    "name": data["name"],
                    "holdings": data["holdings"],
                    "created_at": data.get("created_at") or now,
                    "updated_at": data.get("updated_at") or now,
                }
            )
        except Exception as exc:
            raise LocalPayloadError(
                f"could not read {portfolio_file.name}: {exc}"
            ) from exc
    return payloads


def collect_knowledge_payloads() -> list[dict[str, Any]]:
    """Load local knowledge JSON as Supabase payloads."""

    knowledge_file = (
        Path(__file__).parent.parent / "data" / "knowledge" / "knowledge_items.json"
    )
    if not knowledge_file.exists():
        return []

    try:
        data = load_json_robust(knowledge_file)
    except Exception as exc:
        raise LocalPayloadError(f"could not read knowledge file: {exc}") from exc

    if not isinstance(data, list):
        raise LocalPayloadError("knowledge_items.json must contain a JSON list")

    payloads = []
    for item in data:
        if isinstance(item, dict):
            item.setdefault("metadata", {})
            payloads.append(item)
    return payloads


def collect_trade_plan_payloads() -> list[dict[str, Any]]:
    """Load local manual trading plans as Supabase payloads."""

    path = Path(__file__).parent.parent / "data" / "trading_plans.json"
    if not path.exists():
        return []
    try:
        plans = load_json_robust(path)
    except Exception as exc:
        raise LocalPayloadError(f"could not read trading plans: {exc}") from exc

    if not isinstance(plans, list):
        raise LocalPayloadError("trading_plans.json must contain a JSON list")

    payloads = []
    for plan in plans if isinstance(plans, list) else []:
        if not isinstance(plan, dict) or not plan.get("plan_id"):
            continue
        now = current_utc_iso()
        payloads.append(
            {
                "id": plan["plan_id"],
                "ticker": plan.get("ticker", ""),
                "status": plan.get("status", "draft"),
                "entry_date": plan.get("entry_date"),
                "payload": plan,
                "created_at": plan.get("created_at") or now,
                "updated_at": plan.get("updated_at") or now,
            }
        )
    return payloads


def print_migration_plan(payload: dict[str, Any]) -> None:
    """Print the migration plan without exposing row contents."""

    print("\n--- Planned upload ---")
    for table in TABLES:
        if table in payload:
            print(f"- {table}: {len(payload[table])} rows")


def load_setup_sql() -> str:
    """Load the Supabase setup SQL that creates tables and explicit grants."""

    return SETUP_SQL_PATH.read_text(encoding="utf-8").strip()


def current_utc_iso() -> str:
    """Return an ISO timestamp accepted by Supabase timestamptz columns."""

    return datetime.now(timezone.utc).isoformat()


def backup_remote_tables(
    client: Any, tables: tuple[str, ...], backup_dir: Path
) -> dict[str, Any] | None:
    """Export every remote row with counts and SHA-256 evidence."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at": current_utc_iso(),
        "tables": {},
    }
    for table in tables:
        try:
            rows = fetch_all_rows(client, table, "*", order_column=PRIMARY_KEYS[table])
            path = backup_dir / f"{timestamp}_{table}.json"
            encoded = _canonical_json(rows)
            path.write_text(encoded, encoding="utf-8")
            manifest["tables"][table] = {
                "path": path.name,
                "row_count": len(rows),
                "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            }
            print(f"[OK] Backed up {table} to {path}")
        except Exception as exc:
            print(f"[ERR] Failed to back up {table}: {exc}")
            return None
    manifest_path = backup_dir / f"{timestamp}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[OK] Wrote backup manifest to {manifest_path}")
    return manifest


def load_backup_manifest(
    path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], tuple[str, ...]]:
    """Validate a manifest and return its exact table payloads."""

    try:
        manifest_path = path.resolve(strict=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalPayloadError(f"could not read manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise LocalPayloadError("unsupported backup manifest schema")
    table_entries = manifest.get("tables")
    if not isinstance(table_entries, dict) or not table_entries:
        raise LocalPayloadError("backup manifest has no tables")
    base = manifest_path.parent.resolve()
    payload: dict[str, list[dict[str, Any]]] = {}
    for table, entry in table_entries.items():
        if table not in TABLES or not isinstance(entry, dict):
            raise LocalPayloadError(f"unsupported backup table: {table}")
        backup_path = (base / str(entry.get("path") or "")).resolve()
        if backup_path.parent != base:
            raise LocalPayloadError(f"backup path escapes manifest directory: {table}")
        try:
            encoded = backup_path.read_text(encoding="utf-8")
            rows = json.loads(encoded)
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalPayloadError(f"could not read {table} backup: {exc}") from exc
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if digest != entry.get("sha256"):
            raise LocalPayloadError(f"{table} backup SHA-256 mismatch")
        if not isinstance(rows, list) or len(rows) != entry.get("row_count"):
            raise LocalPayloadError(f"{table} backup row-count mismatch")
        if any(not isinstance(row, dict) for row in rows):
            raise LocalPayloadError(f"{table} backup contains a non-object row")
        payload[table] = rows
    return payload, tuple(payload)


def clear_remote_tables(client: Any, tables: tuple[str, ...]) -> None:
    """Deprecated unsafe operation retained only to fail closed for callers."""

    del client, tables
    raise RuntimeError(
        "Direct remote clearing is disabled; use transactional replace_remote_tables."
    )


def replace_remote_tables(
    client: Any, payload: dict[str, Any], tables: tuple[str, ...]
) -> None:
    """Stage payload rows and atomically apply them through the restricted RPC."""

    batch_id = str(uuid.uuid4())
    expected_counts = {table: len(payload.get(table, [])) for table in tables}
    expected_hashes = {
        table: _payload_hash(payload.get(table, []), PRIMARY_KEYS[table])
        for table in tables
    }
    batch_created = False
    try:
        client.table("personal_data_migration_batches").insert(
            {
                "id": batch_id,
                "requested_tables": list(tables),
                "expected_counts": expected_counts,
                "expected_hashes": expected_hashes,
                "status": "staged",
            }
        ).execute()
        batch_created = True
        stage_rows = []
        for table in tables:
            primary_key = PRIMARY_KEYS[table]
            for row in payload.get(table, []):
                row_key = str(row.get(primary_key) or "")
                if not row_key:
                    raise LocalPayloadError(f"{table} row is missing {primary_key}")
                stage_rows.append(
                    {
                        "batch_id": batch_id,
                        "table_name": table,
                        "row_key": row_key,
                        "payload": row,
                    }
                )
        for start in range(0, len(stage_rows), 100):
            client.table("personal_data_migration_rows").insert(
                stage_rows[start : start + 100]
            ).execute()
        client.rpc("apply_personal_data_migration", {"p_batch_id": batch_id}).execute()
        for table in tables:
            actual = fetch_all_rows(
                client, table, "*", order_column=PRIMARY_KEYS[table]
            )
            if len(actual) != expected_counts[table]:
                raise RuntimeError(f"{table} row-count verification failed")
            if _payload_hash(actual, PRIMARY_KEYS[table]) != expected_hashes[table]:
                raise RuntimeError(f"{table} SHA-256 verification failed")
    finally:
        if batch_created:
            client.table("personal_data_migration_batches").delete().eq(
                "id", batch_id
            ).execute()
    print("[OK] Transactional replace and read-back verification completed.")


def _payload_hash(rows: list[dict[str, Any]], primary_key: str) -> str:
    ordered = sorted(rows, key=lambda row: str(row.get(primary_key) or ""))
    return hashlib.sha256(_canonical_json(ordered).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    )


def upload_payload(client: Any, payload: dict[str, Any]) -> None:
    """Upload selected payload tables to Supabase."""

    if payload.get("user_settings"):
        client.table("user_settings").upsert(payload["user_settings"]).execute()
        print(f"[OK] Uploaded {len(payload['user_settings'])} settings.")

    for portfolio in payload.get("portfolios", []):
        client.table("portfolios").upsert(portfolio, on_conflict="name").execute()
    if "portfolios" in payload:
        print(f"[OK] Uploaded {len(payload['portfolios'])} portfolios.")

    knowledge_items = payload.get("knowledge_items", [])
    for start in range(0, len(knowledge_items), 10):
        batch = knowledge_items[start : start + 10]
        client.table("knowledge_items").upsert(batch).execute()
    if "knowledge_items" in payload:
        print(f"[OK] Uploaded {len(knowledge_items)} knowledge items.")

    for plan in payload.get("trade_plans", []):
        client.table("trade_plans").upsert(plan, on_conflict="id").execute()
    if "trade_plans" in payload:
        print(f"[OK] Uploaded {len(payload['trade_plans'])} trading plans.")


if __name__ == "__main__":
    raise SystemExit(migrate(parse_args()))
