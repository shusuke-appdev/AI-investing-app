from types import SimpleNamespace

from src.portfolio_storage import SupabasePortfolioStorage


class _Query:
    def __init__(self):
        self.on_conflict = ""

    def upsert(self, payload, on_conflict=""):
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self):
        self.query = _Query()

    def table(self, name):
        assert name == "portfolios"
        return self.query


def test_supabase_portfolio_upsert_uses_unique_name(monkeypatch):
    client = _Client()
    monkeypatch.setattr("src.portfolio_storage.get_supabase_client", lambda: client)

    assert SupabasePortfolioStorage().save("Research", [{"ticker": "AAPL"}])
    assert client.query.on_conflict == "name"
