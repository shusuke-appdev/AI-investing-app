from frontend.state import portfolio_state
from src import portfolio_storage


def test_portfolio_state_reads_shared_storage_setting(monkeypatch):
    monkeypatch.setattr("src.settings_storage.get_storage_type", lambda: "supabase")

    assert portfolio_state.get_active_storage_type() == "supabase"
    assert portfolio_state.storage_type_label("supabase") == "Supabase"


def test_portfolio_storage_default_uses_shared_setting(monkeypatch):
    seen = []

    class FakeStorage:
        def list_all(self):
            return ["Research"]

    monkeypatch.setattr(portfolio_storage, "get_storage_type", lambda: "supabase")
    monkeypatch.setattr(
        portfolio_storage.PortfolioStorageFactory,
        "get_storage",
        lambda storage_type: seen.append(storage_type) or FakeStorage(),
    )

    assert portfolio_storage.list_portfolios() == ["Research"]
    assert seen == ["supabase"]
