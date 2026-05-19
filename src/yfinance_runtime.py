"""Runtime configuration for yfinance-backed data providers."""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import yfinance as yf

from src.log_config import get_logger

logger = get_logger(__name__)

_cache_lock = threading.Lock()
_configured_cache_dir: Path | None = None


def default_yfinance_cache_dir() -> Path:
    """Return the repo-local cache directory used when no override is set."""

    return Path(__file__).resolve().parents[1] / ".states" / "yfinance_cache"


def configure_yfinance_cache(*, force: bool = False) -> Path:
    """Point yfinance's SQLite cache at a writable app-controlled directory."""

    global _configured_cache_dir

    with _cache_lock:
        if _configured_cache_dir is not None and not force:
            return _configured_cache_dir

        candidates = _candidate_cache_dirs()
        last_error: Exception | None = None
        for cache_dir in candidates:
            try:
                _ensure_writable_dir(cache_dir)
                yf.set_tz_cache_location(str(cache_dir))
                _configured_cache_dir = cache_dir
                return cache_dir
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[YFinanceRuntime] Cache directory unavailable (%s): %s",
                    cache_dir,
                    exc,
                )

    raise RuntimeError("No writable yfinance cache directory found") from last_error


def _candidate_cache_dirs() -> list[Path]:
    env_dir = os.environ.get("YFINANCE_CACHE_DIR")
    candidates = [Path(env_dir).expanduser()] if env_dir else []
    candidates.append(default_yfinance_cache_dir())
    candidates.append(Path(tempfile.gettempdir()) / "ai_investing_yfinance_cache")
    return candidates


def _ensure_writable_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    probe = cache_dir / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
