import warnings
from pathlib import Path

import pandas as pd

from src import economic_data_provider as provider
from src import persistent_cache
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
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        pdr_data = provider.import_pandas_datareader_data()

    assert hasattr(pdr_data, "DataReader")
    assert not [
        warning
        for warning in captured
        if "distutils Version classes are deprecated" in str(warning.message)
    ]


def test_fetch_fred_series_returns_stale_cache_immediately_when_preferred(
    monkeypatch, tmp_path: Path
):
    store = PersistentJsonCache(tmp_path, provider.ECONOMIC_DATA_CACHE_NAMESPACE)
    monkeypatch.setattr(provider, "_economic_cache", lambda: store)
    old_fetched_at = "2026-07-12T00:00:00+00:00"
    monkeypatch.setattr(persistent_cache, "age_seconds", lambda fetched_at: 172_800)
    key = provider._cache_key(["BAA10Y"], "2026-01-01", None)
    store.write(
        key,
        {
            "series_ids": ["BAA10Y"],
            "records": [{"date": "2026-01-01", "BAA10Y": 1.25}],
            "source": "fred_csv",
            "warnings": ["cached warning"],
        },
        fetched_at=old_fetched_at,
    )
    monkeypatch.setattr(
        provider,
        "_fetch_with_fred_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("live FRED fetch should not run")
        ),
    )
    monkeypatch.setattr(
        provider,
        "_fetch_with_pandas_datareader",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pandas fallback should not run")
        ),
    )

    result = provider.fetch_fred_series(
        ["BAA10Y"],
        start="2026-01-01",
        fresh_seconds=1,
        stale_seconds=7 * 86400,
        prefer_stale_cache=True,
    )

    assert result.cache_status == "stale_cache"
    assert result.is_partial is True
    assert result.data["BAA10Y"].iloc[0] == 1.25
    assert "保存済みデータ" in result.warnings[-1]


def test_fetch_fred_series_can_skip_pandas_datareader_fallback(monkeypatch, tmp_path):
    store = PersistentJsonCache(tmp_path, provider.ECONOMIC_DATA_CACHE_NAMESPACE)
    monkeypatch.setattr(provider, "_economic_cache", lambda: store)
    monkeypatch.setattr(
        provider,
        "_fetch_with_fred_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("csv timeout")),
    )
    monkeypatch.setattr(
        provider,
        "_fetch_with_pandas_datareader",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pandas fallback should not run")
        ),
    )

    result = provider.fetch_fred_series(
        ["BAA10Y"],
        start="2026-01-01",
        use_pandas_datareader_fallback=False,
    )

    assert result.data.empty
    assert result.is_partial is True
    assert result.cache_status == "failed"
    assert "FRED CSV取得失敗" in result.error
