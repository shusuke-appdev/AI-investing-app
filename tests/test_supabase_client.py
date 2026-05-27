from types import SimpleNamespace

from src import supabase_client

ORIGINAL_GET_SUPABASE_CLIENT = supabase_client.get_supabase_client


def test_get_supabase_client_prefers_secret_key(monkeypatch):
    calls = []
    monkeypatch.setattr(supabase_client, "_supabase_client", None)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda url, key: calls.append((url, key)) or SimpleNamespace(key=key),
    )

    client = ORIGINAL_GET_SUPABASE_CLIENT()

    assert client.key == "secret-key"
    assert calls == [("https://example.supabase.co", "secret-key")]


def test_get_supabase_client_falls_back_to_service_role_key(monkeypatch):
    calls = []
    monkeypatch.setattr(supabase_client, "_supabase_client", None)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda url, key: calls.append((url, key)) or SimpleNamespace(key=key),
    )

    client = ORIGINAL_GET_SUPABASE_CLIENT()

    assert client.key == "service-role-key"
    assert calls == [("https://example.supabase.co", "service-role-key")]


def test_get_supabase_client_falls_back_to_legacy_key(monkeypatch):
    calls = []
    monkeypatch.setattr(supabase_client, "_supabase_client", None)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda url, key: calls.append((url, key)) or SimpleNamespace(key=key),
    )

    client = ORIGINAL_GET_SUPABASE_CLIENT()

    assert client.key == "legacy-key"
    assert calls == [("https://example.supabase.co", "legacy-key")]
