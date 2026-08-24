"""Exercise transactional replace and restore against an approved staging project."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.readiness import check_supabase_readiness
from src.storage.supabase_paging import fetch_all_rows
from src.supabase_client import get_supabase_client
from tools.migrate_to_supabase import (
    PRIMARY_KEYS,
    _payload_hash,
    backup_remote_tables,
    load_backup_manifest,
    replace_remote_tables,
)

ACCEPTANCE_TABLE = "knowledge_items"
MINIMUM_ROWS = 1200
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_PROJECT_REF = re.compile(r"[a-z0-9]{8,32}")


class AcceptanceError(RuntimeError):
    """Raised when staging acceptance cannot safely continue."""


@dataclass(frozen=True)
class AcceptanceOptions:
    """Explicit inputs required for a staging-only destructive round trip."""

    project_ref: str
    confirmation: str
    run_id: str
    rows: int = MINIMUM_ROWS
    execute: bool = False
    backup_root: Path = Path(".states/supabase_staging_acceptance")


def parse_args(argv: Sequence[str] | None = None) -> AcceptanceOptions:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument(
        "--confirm-staging",
        required=True,
        help="Must be exactly STAGING:<project-ref>.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--rows", type=int, default=MINIMUM_ROWS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=Path(".states/supabase_staging_acceptance"),
    )
    args = parser.parse_args(argv)
    return AcceptanceOptions(
        project_ref=args.project_ref,
        confirmation=args.confirm_staging,
        run_id=args.run_id,
        rows=args.rows,
        execute=bool(args.execute),
        backup_root=args.backup_root,
    )


def project_ref_from_url(url: str) -> str:
    """Extract a standard Supabase project ref without returning credential data."""

    host = (urlparse(url).hostname or "").lower()
    suffix = ".supabase.co"
    if not host.endswith(suffix):
        raise AcceptanceError("SUPABASE_URL is not a standard Supabase project URL")
    project_ref = host[: -len(suffix)]
    if not _PROJECT_REF.fullmatch(project_ref):
        raise AcceptanceError("SUPABASE_URL does not contain a valid project ref")
    return project_ref


def validate_staging_boundary(
    options: AcceptanceOptions, environment: Mapping[str, str]
) -> None:
    """Fail closed unless URL, declared refs, and human confirmation all agree."""

    if not _PROJECT_REF.fullmatch(options.project_ref):
        raise AcceptanceError("--project-ref is invalid")
    if not _RUN_ID.fullmatch(options.run_id):
        raise AcceptanceError("--run-id must be 1-64 safe identifier characters")
    if options.rows < MINIMUM_ROWS:
        raise AcceptanceError(f"--rows must be at least {MINIMUM_ROWS}")

    url_ref = project_ref_from_url(environment.get("SUPABASE_URL", ""))
    staging_ref = environment.get("SUPABASE_STAGING_PROJECT_REF", "")
    production_ref = environment.get("SUPABASE_PRODUCTION_PROJECT_REF", "")
    if not staging_ref or not production_ref:
        raise AcceptanceError(
            "SUPABASE_STAGING_PROJECT_REF and SUPABASE_PRODUCTION_PROJECT_REF are required"
        )
    if staging_ref == production_ref:
        raise AcceptanceError("Staging and production project refs must be different")
    if options.project_ref != staging_ref or options.project_ref != url_ref:
        raise AcceptanceError(
            "Project ref does not match the staging URL and declaration"
        )
    if options.confirmation != f"STAGING:{options.project_ref}":
        raise AcceptanceError(
            "Explicit staging confirmation does not match project ref"
        )
    if options.execute and not environment.get("SUPABASE_SECRET_KEY"):
        raise AcceptanceError("SUPABASE_SECRET_KEY is required for staging execution")


def synthetic_rows(run_id: str, count: int) -> list[dict[str, Any]]:
    """Build deterministic synthetic data that cannot contain personal content."""

    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": f"staging-acceptance-{run_id}-{index:04d}",
            "title": f"Synthetic staging row {index}",
            "source_type": "staging_acceptance_synthetic",
            "original_content": "Synthetic data only; no local or user data.",
            "summary": f"Synthetic acceptance row {index} for run {run_id}.",
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": {"synthetic": True, "run_id": run_id, "index": index},
        }
        for index in range(count)
    ]


def _require_ready(client: Any, phase: str) -> None:
    readiness = check_supabase_readiness(client)
    if not readiness.ready:
        raise AcceptanceError(
            f"Supabase schema readiness failed during {phase}: {readiness.error_code}"
        )


def _manifest_path(directory: Path) -> Path:
    manifests = list(directory.glob("*_manifest.json"))
    if len(manifests) != 1:
        raise AcceptanceError("Expected exactly one original backup manifest")
    return manifests[0]


def _verify_restored(
    client: Any,
    original_rows: list[dict[str, Any]],
    run_id: str,
) -> None:
    rows = fetch_all_rows(
        client,
        ACCEPTANCE_TABLE,
        "*",
        order_column=PRIMARY_KEYS[ACCEPTANCE_TABLE],
    )
    if len(rows) != len(original_rows):
        raise AcceptanceError("Restored row count does not match the original manifest")
    if _payload_hash(rows, PRIMARY_KEYS[ACCEPTANCE_TABLE]) != _payload_hash(
        original_rows, PRIMARY_KEYS[ACCEPTANCE_TABLE]
    ):
        raise AcceptanceError("Restored SHA-256 does not match the original manifest")
    prefix = f"staging-acceptance-{run_id}-"
    if any(str(row.get("id") or "").startswith(prefix) for row in rows):
        raise AcceptanceError("Synthetic staging rows remain after restore")


def run_acceptance(
    options: AcceptanceOptions,
    *,
    environment: Mapping[str, str] | None = None,
    client_factory=get_supabase_client,
) -> int:
    """Run a reversible staging round trip and return a process-style code."""

    environment = os.environ if environment is None else environment
    try:
        validate_staging_boundary(options, environment)
    except AcceptanceError as exc:
        print(f"[ERR] Staging boundary rejected: {exc}")
        return 1

    print("=== Supabase Staging Acceptance ===")
    print(f"Project ref: {options.project_ref}")
    print(f"Run ID: {options.run_id}")
    print(f"Synthetic rows: {options.rows}")
    if not options.execute:
        print("Dry run only. Re-run with --execute after reviewing the staging refs.")
        return 0

    client = client_factory()
    if client is None:
        print("[ERR] Could not create the staging Supabase client.")
        return 1

    run_dir = options.backup_root / options.run_id
    original_dir = run_dir / "original"
    restore_required = False
    original_rows: list[dict[str, Any]] = []
    acceptance_error: Exception | None = None

    try:
        _require_ready(client, "preflight")
        manifest = backup_remote_tables(client, (ACCEPTANCE_TABLE,), original_dir)
        if manifest is None:
            raise AcceptanceError("Original staging backup failed")
        payload, tables = load_backup_manifest(_manifest_path(original_dir))
        original_rows = payload[ACCEPTANCE_TABLE]
        prefix = f"staging-acceptance-{options.run_id}-"
        if any(str(row.get("id") or "").startswith(prefix) for row in original_rows):
            raise AcceptanceError("Run ID collides with an existing staging row")

        generated = synthetic_rows(options.run_id, options.rows)
        restore_required = True
        replace_remote_tables(client, {ACCEPTANCE_TABLE: generated}, tables)
        synthetic_actual = fetch_all_rows(
            client,
            ACCEPTANCE_TABLE,
            "*",
            order_column=PRIMARY_KEYS[ACCEPTANCE_TABLE],
        )
        if len(synthetic_actual) != options.rows:
            raise AcceptanceError("Synthetic read-back row count mismatch")
        if _payload_hash(
            synthetic_actual, PRIMARY_KEYS[ACCEPTANCE_TABLE]
        ) != _payload_hash(generated, PRIMARY_KEYS[ACCEPTANCE_TABLE]):
            raise AcceptanceError("Synthetic read-back SHA-256 mismatch")
        print("[OK] Synthetic transactional replace matched count and SHA-256.")
    except Exception as exc:
        acceptance_error = exc
    finally:
        if restore_required:
            try:
                replace_remote_tables(
                    client,
                    {ACCEPTANCE_TABLE: original_rows},
                    (ACCEPTANCE_TABLE,),
                )
                _verify_restored(client, original_rows, options.run_id)
                _require_ready(client, "post-restore")
                print("[OK] Original manifest restored; no synthetic rows remain.")
            except Exception as exc:
                print(f"[ERR] Mandatory restore verification failed: {exc}")
                return 1

    if acceptance_error is not None:
        print(
            f"[ERR] Acceptance failed and original data was restored: {acceptance_error}"
        )
        return 1
    print("=== Supabase Staging Acceptance Passed ===")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_acceptance(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
