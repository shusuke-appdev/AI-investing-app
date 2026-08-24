import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import supabase_staging_acceptance
from src.storage.supabase_paging import fetch_all_rows
from tools import migrate_to_supabase


class FakeTable:
    def __init__(self, name: str, calls: list[tuple]):
        self.name = name
        self.calls = calls
        self.data = [{"id": "row"}]

    def select(self, columns: str):
        self.calls.append((self.name, "select", columns))
        return self

    def delete(self):
        self.calls.append((self.name, "delete"))
        return self

    def neq(self, column: str, value: str):
        self.calls.append((self.name, "neq", column, value))
        return self

    def upsert(self, payload, **kwargs):
        self.calls.append((self.name, "upsert", payload, kwargs))
        return self

    def execute(self):
        self.calls.append((self.name, "execute"))
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self):
        self.calls: list[tuple] = []

    def table(self, name: str) -> FakeTable:
        self.calls.append(("table", name))
        return FakeTable(name, self.calls)


def test_supabase_paging_reads_all_1200_rows():
    rows = [{"id": index} for index in range(1200)]

    class PagedQuery:
        def __init__(self):
            self.start = 0
            self.end = 0

        def select(self, columns):
            assert columns == "*"
            return self

        def order(self, column):
            assert column == "id"
            return self

        def range(self, start, end):
            self.start, self.end = start, end
            return self

        def execute(self):
            return SimpleNamespace(data=rows[self.start : self.end + 1])

    class PagedClient:
        def table(self, name):
            assert name == "knowledge_items"
            return PagedQuery()

    fetched = fetch_all_rows(
        PagedClient(), "knowledge_items", "*", order_column="id", page_size=500
    )

    assert fetched == rows


def test_parse_args_defaults_to_dry_run():
    options = migrate_to_supabase.parse_args([])

    assert options.dry_run is True
    assert options.confirm_destroy is False
    assert options.tables == migrate_to_supabase.TABLES
    assert options.print_setup_sql is False


def test_parse_args_can_print_setup_sql():
    options = migrate_to_supabase.parse_args(["--print-setup-sql"])

    assert options.print_setup_sql is True


def test_print_setup_sql_does_not_connect_to_supabase(monkeypatch, capsys):
    def fail_connect():
        raise AssertionError("setup SQL print should not connect")

    def fail_collect(tables):
        raise AssertionError("setup SQL print should not read local payload")

    monkeypatch.setattr(migrate_to_supabase, "get_supabase_client", fail_connect)
    monkeypatch.setattr(migrate_to_supabase, "collect_local_payload", fail_collect)

    result = migrate_to_supabase.migrate(
        migrate_to_supabase.MigrationOptions(print_setup_sql=True)
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "alter table public.portfolios enable row level security;" in output
    assert (
        'drop policy if exists "Enable all access for all users" on public.portfolios;'
        in output
    )
    assert (
        "grant select, insert, update, delete on table public.portfolios to service_role;"
        in output
    )
    assert "alter table public.trade_plans enable row level security;" in output
    assert "alter default privileges for role postgres in schema public" in output


def test_dry_run_does_not_connect_to_supabase(monkeypatch):
    monkeypatch.setattr(
        migrate_to_supabase,
        "collect_local_payload",
        lambda tables: {"user_settings": []},
    )

    def fail_connect():
        raise AssertionError("dry-run should not connect")

    monkeypatch.setattr(migrate_to_supabase, "get_supabase_client", fail_connect)

    result = migrate_to_supabase.migrate(
        migrate_to_supabase.MigrationOptions(
            dry_run=True,
            tables=("user_settings",),
        )
    )

    assert result == 0


def test_execute_without_confirm_destroy_uploads_without_delete(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(migrate_to_supabase, "get_supabase_client", lambda: client)
    monkeypatch.setattr(
        migrate_to_supabase,
        "collect_local_payload",
        lambda tables: {"user_settings": [{"key": "storage_type", "value": "local"}]},
    )

    result = migrate_to_supabase.migrate(
        migrate_to_supabase.MigrationOptions(
            dry_run=False,
            confirm_destroy=False,
            tables=("user_settings",),
        )
    )

    assert result == 0
    assert any(call[1] == "upsert" for call in client.calls if len(call) > 1)
    assert not any(call[1] == "delete" for call in client.calls if len(call) > 1)


def test_clear_remote_tables_is_disabled_fail_closed():
    client = FakeClient()

    with pytest.raises(RuntimeError, match="transactional"):
        migrate_to_supabase.clear_remote_tables(client, ("portfolios",))
    assert not any(call[1] == "delete" for call in client.calls if len(call) > 1)


class MemoryQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.payload = None
        self.start = 0
        self.end = 999
        self.filter = None
        self.operation = "select"

    def select(self, _columns):
        self.operation = "select"
        return self

    def order(self, _column):
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filter = (column, value)
        return self

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        if self.operation == "insert":
            values = self.payload if isinstance(self.payload, list) else [self.payload]
            rows.extend(values)
            return SimpleNamespace(data=values)
        if self.operation == "delete":
            column, value = self.filter
            self.client.tables[self.table] = [
                row for row in rows if row.get(column) != value
            ]
            if self.table == "personal_data_migration_batches" and column == "id":
                staged = self.client.tables.get("personal_data_migration_rows", [])
                self.client.tables["personal_data_migration_rows"] = [
                    row for row in staged if row.get("batch_id") != value
                ]
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=rows[self.start : self.end + 1])


class MemoryRpc:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        assert self.name == "apply_personal_data_migration"
        batch_id = self.params["p_batch_id"]
        batch = next(
            row
            for row in self.client.tables["personal_data_migration_batches"]
            if row["id"] == batch_id
        )
        staged = [
            row
            for row in self.client.tables["personal_data_migration_rows"]
            if row["batch_id"] == batch_id
        ]
        for table in batch["requested_tables"]:
            self.client.tables[table] = [
                row["payload"] for row in staged if row["table_name"] == table
            ]
        return SimpleNamespace(data={"status": "applied"})


class MemoryClient:
    def __init__(self, tables):
        self.tables = {name: list(rows) for name, rows in tables.items()}
        self.tables.setdefault("personal_data_migration_batches", [])
        self.tables.setdefault("personal_data_migration_rows", [])

    def table(self, name):
        return MemoryQuery(self, name)

    def rpc(self, name, params):
        return MemoryRpc(self, name, params)


def test_manifest_restore_round_trips_all_1200_rows(monkeypatch, tmp_path):
    original = [
        {"id": f"item-{index:04d}", "summary": str(index)} for index in range(1200)
    ]
    client = MemoryClient({"knowledge_items": original})
    original_dir = tmp_path / "original"

    manifest = migrate_to_supabase.backup_remote_tables(
        client, ("knowledge_items",), original_dir
    )
    assert manifest is not None
    manifest_path = next(original_dir.glob("*_manifest.json"))
    assert manifest["tables"]["knowledge_items"]["row_count"] == 1200

    client.tables["knowledge_items"] = [{"id": "replacement", "summary": "new"}]
    monkeypatch.setattr(migrate_to_supabase, "get_supabase_client", lambda: client)
    result = migrate_to_supabase.migrate(
        migrate_to_supabase.MigrationOptions(
            dry_run=False,
            restore_manifest=manifest_path,
            backup_dir=tmp_path / "pre_restore",
        )
    )

    assert result == 0
    assert client.tables["knowledge_items"] == original
    assert migrate_to_supabase._payload_hash(
        client.tables["knowledge_items"], "id"
    ) == migrate_to_supabase._payload_hash(original, "id")


def test_failed_stage_validation_removes_migration_batch():
    client = MemoryClient({"knowledge_items": []})

    with pytest.raises(migrate_to_supabase.LocalPayloadError, match="missing id"):
        migrate_to_supabase.replace_remote_tables(
            client,
            {"knowledge_items": [{"summary": "missing primary key"}]},
            ("knowledge_items",),
        )

    assert client.tables["personal_data_migration_batches"] == []
    assert client.tables["personal_data_migration_rows"] == []


def _staging_environment():
    return {
        "SUPABASE_URL": "https://stagingref12345.supabase.co",
        "SUPABASE_SECRET_KEY": "test-only-secret",
        "SUPABASE_STAGING_PROJECT_REF": "stagingref12345",
        "SUPABASE_PRODUCTION_PROJECT_REF": "productionref12",
    }


def _acceptance_options(tmp_path):
    return supabase_staging_acceptance.AcceptanceOptions(
        project_ref="stagingref12345",
        confirmation="STAGING:stagingref12345",
        run_id="run-123",
        execute=True,
        backup_root=tmp_path,
    )


def _ready():
    return SimpleNamespace(ready=True, error_code="")


def test_staging_acceptance_round_trip_uses_synthetic_rows_only(monkeypatch, tmp_path):
    original = [
        {
            "id": "original",
            "title": "existing staging row",
            "source_type": "test",
            "original_content": "staging fixture",
            "summary": "original",
            "created_at": "2026-08-24T00:00:00+00:00",
            "updated_at": "2026-08-24T00:00:00+00:00",
            "metadata": {},
        }
    ]
    client = MemoryClient({"knowledge_items": original})
    monkeypatch.setattr(
        supabase_staging_acceptance,
        "check_supabase_readiness",
        lambda _client: _ready(),
    )

    result = supabase_staging_acceptance.run_acceptance(
        _acceptance_options(tmp_path),
        environment=_staging_environment(),
        client_factory=lambda: client,
    )

    assert result == 0
    assert client.tables["knowledge_items"] == original
    assert client.tables["personal_data_migration_batches"] == []
    assert client.tables["personal_data_migration_rows"] == []


def test_staging_acceptance_restores_original_after_acceptance_failure(
    monkeypatch, tmp_path
):
    original = [{"id": "original", "summary": "staging fixture"}]
    client = MemoryClient({"knowledge_items": original})
    real_replace = migrate_to_supabase.replace_remote_tables
    calls = 0

    def replace_then_fail(client_arg, payload, tables):
        nonlocal calls
        calls += 1
        real_replace(client_arg, payload, tables)
        if calls == 1:
            raise RuntimeError("simulated post-replace acceptance failure")

    monkeypatch.setattr(
        supabase_staging_acceptance,
        "check_supabase_readiness",
        lambda _client: _ready(),
    )
    monkeypatch.setattr(
        supabase_staging_acceptance, "replace_remote_tables", replace_then_fail
    )

    result = supabase_staging_acceptance.run_acceptance(
        _acceptance_options(tmp_path),
        environment=_staging_environment(),
        client_factory=lambda: client,
    )

    assert result == 1
    assert calls == 2
    assert client.tables["knowledge_items"] == original


def test_staging_acceptance_rejects_production_ref_before_client_creation(tmp_path):
    environment = _staging_environment()
    environment["SUPABASE_PRODUCTION_PROJECT_REF"] = "stagingref12345"
    created = False

    def client_factory():
        nonlocal created
        created = True
        return MemoryClient({"knowledge_items": []})

    result = supabase_staging_acceptance.run_acceptance(
        _acceptance_options(tmp_path),
        environment=environment,
        client_factory=client_factory,
    )

    assert result == 1
    assert created is False


def test_manifest_tampering_aborts_before_remote_connection(monkeypatch, tmp_path):
    backup_path = tmp_path / "knowledge.json"
    backup_path.write_text('[{"id":"safe"}]', encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tables": {
                    "knowledge_items": {
                        "path": backup_path.name,
                        "row_count": 1,
                        "sha256": "incorrect",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        migrate_to_supabase,
        "get_supabase_client",
        lambda: pytest.fail("tampered restore must not connect"),
    )

    result = migrate_to_supabase.migrate(
        migrate_to_supabase.MigrationOptions(
            dry_run=False,
            restore_manifest=manifest_path,
        )
    )

    assert result == 1


def test_versioned_migration_matches_canonical_schema():
    migrations = sorted(
        Path("supabase/migrations").glob("*_personal_data_storage_v1.sql")
    )

    assert len(migrations) == 1
    assert migrations[0].read_bytes() == Path("supabase/public_tables.sql").read_bytes()
    sql = migrations[0].read_text(encoding="utf-8")
    assert "personal_data_schema_readiness" in sql
    assert "grant execute" in sql
    assert "to service_role" in sql
