import pytest

from src.app_mode import (
    ai_generation_enabled,
    app_capability_summary,
    get_app_mode,
    require_ai_generation_enabled,
)


def test_local_app_has_one_personal_mode(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("PRIVATE_DEPLOYMENT_ACK", raising=False)
    monkeypatch.setenv("APP_MODE", "public_readonly")  # retired value is ignored

    assert get_app_mode() == "personal"
    assert ai_generation_enabled()
    require_ai_generation_enabled()
    assert app_capability_summary() == {
        "mode": "personal",
        "personal_data": False,
        "ai_generation": True,
        "external_content_fetch": False,
        "hosted_environment": False,
        "private_deployment_acknowledged": False,
    }


def test_hosted_personal_mode_requires_access_control_ack(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "owner/space")
    monkeypatch.delenv("PRIVATE_DEPLOYMENT_ACK", raising=False)

    with pytest.raises(RuntimeError, match="PRIVATE_DEPLOYMENT_ACK=1"):
        get_app_mode()
    monkeypatch.setenv("PRIVATE_DEPLOYMENT_ACK", "1")
    assert get_app_mode() == "personal"
    assert app_capability_summary()["hosted_environment"] is True
    assert app_capability_summary()["private_deployment_acknowledged"] is True


def test_gemini_generation_uses_gemini_3_8_flash_by_default(monkeypatch):
    from unittest.mock import MagicMock

    from src import gemini_client

    monkeypatch.delenv("SPACE_ID", raising=False)
    client = MagicMock()
    client.models.generate_content.return_value.text = "generated"
    monkeypatch.setattr(gemini_client, "_client", client)

    assert gemini_client.generate_content("prompt") == "generated"
    client.models.generate_content.assert_called_once_with(
        model="gemini-3.8-flash",
        contents="prompt",
    )
