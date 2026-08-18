import pytest

from src import settings_storage
from src.storage.readiness import check_supabase_readiness


def test_legacy_gas_storage_setting_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings_storage, "get_setting", lambda key, default: "gas")

    assert settings_storage.get_storage_type() == "local"


def test_storage_type_rejects_removed_gas_backend():
    with pytest.raises(ValueError, match="local.*supabase"):
        settings_storage.set_storage_type_setting("gas")


def test_settings_save_uses_atomic_json_writer(monkeypatch, tmp_path):
    settings_file = tmp_path / "data" / "settings.json"
    calls = []
    real_write_json = settings_storage.write_json

    def recording_write(path, value):
        calls.append((path, value.copy()))
        real_write_json(path, value)

    monkeypatch.setattr(settings_storage, "SETTINGS_DIR", settings_file.parent)
    monkeypatch.setattr(settings_storage, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(settings_storage, "write_json", recording_write)
    monkeypatch.setattr(settings_storage, "get_supabase_client", lambda: None)
    monkeypatch.setattr(settings_storage, "_settings_cache", None)

    assert settings_storage.save_settings({"storage_type": "local"}) is True
    assert calls == [(settings_file, {"storage_type": "local"})]
    assert settings_storage.load_settings(force_reload=True) == {
        "storage_type": "local"
    }
    assert list(settings_file.parent.glob("*.tmp")) == []


class _ReadinessRpc:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return type("Response", (), {"data": self.payload})()


class _ReadinessClient:
    def __init__(self, payload):
        self.payload = payload

    def rpc(self, name, params):
        assert name == "personal_data_schema_readiness"
        assert params == {}
        return _ReadinessRpc(self.payload)


def test_supabase_readiness_requires_version_and_all_four_tables():
    ready = check_supabase_readiness(
        _ReadinessClient(
            {
                "schema_version": 1,
                "tables": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": True,
                    "trade_plans": True,
                },
                "columns": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": True,
                    "trade_plans": True,
                },
                "grants": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": True,
                    "trade_plans": True,
                },
            }
        )
    )
    missing = check_supabase_readiness(
        _ReadinessClient(
            {
                "schema_version": 1,
                "tables": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": False,
                    "trade_plans": True,
                },
                "columns": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": True,
                    "trade_plans": True,
                },
                "grants": {
                    "user_settings": True,
                    "portfolios": True,
                    "knowledge_items": True,
                    "trade_plans": True,
                },
            }
        )
    )

    assert ready.ready is True
    assert missing.ready is False
    assert missing.error_code == "missing_tables"
    assert missing.missing_tables == ["knowledge_items"]


def test_supabase_readiness_rejects_bad_columns_and_grants():
    payload = {
        "schema_version": 1,
        "tables": {
            name: True
            for name in (
                "user_settings",
                "portfolios",
                "knowledge_items",
                "trade_plans",
            )
        },
        "columns": {
            name: True
            for name in (
                "user_settings",
                "portfolios",
                "knowledge_items",
                "trade_plans",
            )
        },
        "grants": {
            name: True
            for name in (
                "user_settings",
                "portfolios",
                "knowledge_items",
                "trade_plans",
            )
        },
    }
    payload["columns"]["portfolios"] = False
    invalid_columns = check_supabase_readiness(_ReadinessClient(payload))
    payload["columns"]["portfolios"] = True
    payload["grants"]["trade_plans"] = False
    invalid_grants = check_supabase_readiness(_ReadinessClient(payload))

    assert invalid_columns.ready is False
    assert invalid_columns.error_code == "invalid_columns"
    assert invalid_columns.invalid_columns == ["portfolios"]
    assert invalid_grants.ready is False
    assert invalid_grants.error_code == "invalid_grants"
    assert invalid_grants.invalid_grants == ["trade_plans"]


def test_storage_backend_switch_does_not_persist_when_schema_is_not_ready(
    monkeypatch,
):
    writes = []
    monkeypatch.delenv("APP_STORAGE_BACKEND", raising=False)
    monkeypatch.setattr(settings_storage, "_supabase_backend_ready", lambda: False)
    monkeypatch.setattr(
        settings_storage, "set_setting", lambda key, value: writes.append((key, value))
    )

    assert settings_storage.set_storage_type_setting("supabase") is False
    assert writes == []
