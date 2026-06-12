import pytest

from src import settings_storage


def test_legacy_gas_storage_setting_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings_storage, "get_setting", lambda key, default: "gas")

    assert settings_storage.get_storage_type() == "local"


def test_storage_type_rejects_removed_gas_backend():
    with pytest.raises(ValueError, match="local.*supabase"):
        settings_storage.set_storage_type_setting("gas")
