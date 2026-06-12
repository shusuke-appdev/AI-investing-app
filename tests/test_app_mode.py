import pytest

from src.app_mode import get_app_mode, require_writes_enabled, writes_enabled


def test_app_mode_defaults_to_private(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)

    assert get_app_mode() == "private"
    assert writes_enabled()


def test_public_readonly_blocks_writes(monkeypatch):
    monkeypatch.setenv("APP_MODE", "public_readonly")

    with pytest.raises(PermissionError, match="読み取り専用"):
        require_writes_enabled()


def test_invalid_app_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_MODE", "publci")

    with pytest.raises(ValueError, match="APP_MODE"):
        writes_enabled()
