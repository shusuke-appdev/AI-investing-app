"""
Migrate local JSON data to Supabase tables.

The default mode is a dry run. Remote writes require ``--execute``. Remote table
clearing additionally requires ``--confirm-destroy`` and a successful backup.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.supabase_client import get_supabase_client

TABLES = ("user_settings", "portfolios", "knowledge_items", "trade_plans")
SETUP_SQL_PATH = Path(__file__).parent.parent / "supabase" / "public_tables.sql"
CLEAR_FILTERS = {
    "user_settings": ("key", "__migration_sentinel__"),
    "portfolios": ("name", "__migration_sentinel__"),
    "knowledge_items": ("id", "__migration_sentinel__"),
    "trade_plans": ("id", "__migration_sentinel__"),
}


@dataclass(frozen=True)
class MigrationOptions:
    """Supabase migration execution options."""

    dry_run: bool = True
    confirm_destroy: bool = False
    tables: tuple[str, ...] = TABLES
    backup_dir: Path = Path("data/supabase_backups")
    print_setup_sql: bool = False


def parse_args(argv: list[str] | None = None) -> MigrationOptions:
    """Parse CLI arguments into migration options."""

    parser = argparse.ArgumentParser(description="Migrate local data to Supabase.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write local data to Supabase. Omit for dry-run mode.",
    )
    parser.add_argument(
        "--confirm-destroy",
        action="store_true",
        help="Clear selected remote tables before upload. Requires --execute.",
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
        default=Path("data/supabase_backups"),
        help="Directory for pre-destroy Supabase backups.",
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

    print("=== Supabase Migration Tool ===")
    print(f"Mode: {'dry-run' if options.dry_run else 'execute'}")
    print("Tables: " + ", ".join(options.tables))

    local_payload = collect_local_payload(options.tables)
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
        if not backup_remote_tables(client, options.tables, options.backup_dir):
            print("[ERR] Remote backup failed. Aborting destructive clear.")
            return 1
        clear_remote_tables(client, options.tables)
    else:
        print(
            "Remote tables will not be cleared. Use --confirm-destroy to replace all."
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
        return data if isinstance(data, dict) else {}
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
            print(f"[ERR] Error reading {portfolio_file.name}: {exc}")
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
        print(f"[ERR] Error reading knowledge file: {exc}")
        return []

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
        print(f"[ERR] Error reading trading plans: {exc}")
        return []

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
) -> bool:
    """Export selected remote tables before destructive clearing."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        try:
            response = client.table(table).select("*").execute()
            path = backup_dir / f"{timestamp}_{table}.json"
            path.write_text(
                json.dumps(response.data or [], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[OK] Backed up {table} to {path}")
        except Exception as exc:
            print(f"[ERR] Failed to back up {table}: {exc}")
            return False
    return True


def clear_remote_tables(client: Any, tables: tuple[str, ...]) -> None:
    """Clear selected remote tables after backup and explicit confirmation."""

    print("\n--- Clearing selected remote tables ---")
    for table in tables:
        column, sentinel = CLEAR_FILTERS[table]
        client.table(table).delete().neq(column, sentinel).execute()
        print(f"[OK] Cleared {table}")


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
