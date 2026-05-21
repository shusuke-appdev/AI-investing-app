from types import SimpleNamespace

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


def test_parse_args_defaults_to_dry_run():
    options = migrate_to_supabase.parse_args([])

    assert options.dry_run is True
    assert options.confirm_destroy is False
    assert options.tables == migrate_to_supabase.TABLES


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


def test_clear_remote_tables_uses_table_specific_sentinel_filters():
    client = FakeClient()

    migrate_to_supabase.clear_remote_tables(client, ("portfolios",))

    assert ("portfolios", "delete") in client.calls
    assert ("portfolios", "neq", "name", "__migration_sentinel__") in client.calls
