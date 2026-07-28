import pytest

from src import settings_storage


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
