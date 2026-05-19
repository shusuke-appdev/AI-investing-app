from pathlib import Path

from src import yfinance_runtime


def test_configure_yfinance_cache_uses_env_override(monkeypatch, tmp_path):
    calls = []
    cache_dir = tmp_path / "yf-cache"

    monkeypatch.setenv("YFINANCE_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(
        yfinance_runtime.yf,
        "set_tz_cache_location",
        lambda path: calls.append(Path(path)),
    )

    configured = yfinance_runtime.configure_yfinance_cache(force=True)

    assert configured == cache_dir
    assert calls == [cache_dir]
    assert (cache_dir).is_dir()


def test_default_yfinance_cache_dir_is_repo_local():
    assert yfinance_runtime.default_yfinance_cache_dir().parts[-2:] == (
        ".states",
        "yfinance_cache",
    )
