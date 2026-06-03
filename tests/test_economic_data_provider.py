from pathlib import Path

import pandas as pd

from src import economic_data_provider as provider
from src.persistent_cache import PersistentJsonCache


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        return None


def test_fetch_fred_series_uses_csv_and_cache(monkeypatch, tmp_path: Path):
    store = PersistentJsonCache(tmp_path, provider.ECONOMIC_DATA_CACHE_NAMESPACE)
    monkeypatch.setattr(provider, "_economic_cache", lambda: store)
    monkeypatch.setattr(
        provider,
        "_fetch_with_pandas_datareader",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pdr broken")),
    )

    def fake_get(url, params, headers, timeout):
        assert params["id"] == "BAA10Y"
        assert headers["User-Agent"] == "AI-investing-app/1.0"
        return _FakeResponse("observation_date,BAA10Y\n2026-01-01,1.0\n2026-01-02,.\n")

    monkeypatch.setattr(provider.requests, "get", fake_get)

    result = provider.fetch_fred_series(["BAA10Y"], start="2026-01-01")

    assert result.source == "fred_csv"
    assert result.data["BAA10Y"].iloc[0] == 1.0
    assert pd.isna(result.data["BAA10Y"].iloc[1])
    assert result.error == ""

    cached = provider.fetch_fred_series(["BAA10Y"], start="2026-01-01")

    assert cached.cache_status == "persistent_cache"
    assert cached.data["BAA10Y"].iloc[0] == 1.0


def test_pandas_datareader_compat_imports_data_module():
    pdr_data = provider.import_pandas_datareader_data()

    assert hasattr(pdr_data, "DataReader")
