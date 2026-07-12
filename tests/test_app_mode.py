import pytest

from src.app_mode import (
    ai_generation_enabled,
    app_capability_summary,
    external_content_fetch_enabled,
    get_app_mode,
    personal_data_enabled,
    require_ai_generation_enabled,
    require_external_content_fetch_enabled,
    require_personal_data_enabled,
    require_writes_enabled,
    writes_enabled,
)


def test_app_mode_defaults_to_public_readonly(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)

    assert get_app_mode() == "public_readonly"
    assert not writes_enabled()
    assert not personal_data_enabled()
    assert not ai_generation_enabled()
    assert not external_content_fetch_enabled()
    assert app_capability_summary() == {
        "mode": "public_readonly",
        "explicitly_configured": False,
        "personal_data": False,
        "ai_generation": False,
        "external_content_fetch": False,
    }


def test_private_mode_requires_explicit_configuration(monkeypatch):
    monkeypatch.setenv("APP_MODE", "private")

    assert writes_enabled()
    assert personal_data_enabled()
    assert ai_generation_enabled()
    assert external_content_fetch_enabled()
    assert app_capability_summary()["explicitly_configured"] is True


def test_public_readonly_blocks_writes(monkeypatch):
    monkeypatch.setenv("APP_MODE", "public_readonly")

    with pytest.raises(PermissionError, match="読み取り専用"):
        require_writes_enabled()
    with pytest.raises(PermissionError, match="個人データ"):
        require_personal_data_enabled()
    with pytest.raises(PermissionError, match="AI生成"):
        require_ai_generation_enabled()
    with pytest.raises(PermissionError, match="URL・YouTube"):
        require_external_content_fetch_enabled()


def test_public_readonly_does_not_return_cached_gemini_client(monkeypatch):
    from src import gemini_client

    monkeypatch.setenv("APP_MODE", "public_readonly")
    monkeypatch.setattr(gemini_client, "_client", object())

    assert gemini_client.get_gemini_client() is None
    assert not gemini_client.configure_gemini("secret")


def test_invalid_app_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_MODE", "publci")

    with pytest.raises(ValueError, match="APP_MODE"):
        writes_enabled()


def test_public_readonly_route_load_guards_disable_personal_loads(monkeypatch):
    from frontend.state import knowledge_state, portfolio_state

    monkeypatch.setenv("APP_MODE", "public_readonly")

    assert not portfolio_state._personal_data_route_enabled()
    assert not knowledge_state._personal_data_route_enabled()
