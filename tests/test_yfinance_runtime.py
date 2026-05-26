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


def test_yfinance_cache_info_reports_configured_path(monkeypatch, tmp_path):
    cache_dir = tmp_path / "yf-cache"
    monkeypatch.setenv("YFINANCE_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(
        yfinance_runtime.yf,
        "set_tz_cache_location",
        lambda path: None,
    )

    configured = yfinance_runtime.configure_yfinance_cache(force=True)
    info = yfinance_runtime.yfinance_cache_info()

    assert configured.exists()
    assert info["configured"] is True
    assert info["cache_dir"] == str(configured)
    assert info["writable"] is True
