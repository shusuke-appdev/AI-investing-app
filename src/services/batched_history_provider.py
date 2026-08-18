"""Status-aware batched daily-history provider for theme workflows."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import yfinance as yf

from src.persistent_cache import utc_now_iso
from src.provider_result import FetchResult
from src.yfinance_runtime import configure_yfinance_cache

configure_yfinance_cache()


def fetch_batched_history(
    tickers: list[str],
    *,
    period: str = "2y",
    timeout: int = 20,
    downloader: Callable[..., pd.DataFrame] = yf.download,
) -> FetchResult[dict[str, pd.DataFrame]]:
    """Fetch one bounded batch and report missing members explicitly."""

    requested = list(dict.fromkeys(ticker for ticker in tickers if ticker))
    fetched_at = utc_now_iso()
    if not requested:
        return FetchResult(data={}, status="unavailable", error_code="empty_universe")
    try:
        raw = downloader(
            requested,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=timeout,
        )
    except Exception as exc:
        return FetchResult(
            data={},
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            error_code="provider_error",
            error=str(exc),
        )
    if raw is None or raw.empty:
        return FetchResult(
            data={},
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            error_code="empty_response",
        )
    frames = {
        ticker: frame
        for ticker in requested
        if not (frame := _extract_ticker_frame(raw, ticker, requested)).empty
    }
    missing = [ticker for ticker in requested if ticker not in frames]
    return FetchResult(
        data=frames,
        source="yfinance_batch",
        fetched_at=fetched_at,
        status="partial" if missing else "available",
        is_partial=bool(missing),
        warnings=[f"Missing batched history: {', '.join(missing)}"] if missing else [],
        error_code="partial_history" if missing else "",
    )


def _extract_ticker_frame(
    raw: pd.DataFrame, ticker: str, requested: list[str]
) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(0):
            return raw[ticker].dropna(how="all").copy()
        if ticker in raw.columns.get_level_values(-1):
            return raw.xs(ticker, axis=1, level=-1).dropna(how="all").copy()
        return pd.DataFrame()
    return raw.dropna(how="all").copy() if len(requested) == 1 else pd.DataFrame()
