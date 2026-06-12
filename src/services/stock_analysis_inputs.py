"""Shared, memoized inputs for one individual-stock analysis run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.market_data import get_stock_data, get_stock_info, get_stock_news_with_status

PERIOD_SESSIONS = {
    "5d": 5,
    "1mo": 21,
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}


@dataclass
class StockAnalysisInputs:
    """Fetch each stock-analysis input at most once per ticker/period."""

    ticker: str
    history_provider: Callable[[str, str], pd.DataFrame] = get_stock_data
    info_provider: Callable[..., dict[str, Any]] = get_stock_info
    news_provider: Callable[[str, int], dict[str, Any]] = get_stock_news_with_status
    history_cache: dict[tuple[str, str], pd.DataFrame] = field(default_factory=dict)
    info_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    info_with_summary: set[str] = field(default_factory=set)
    news_cache: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ticker = self.ticker.strip().upper()

    @property
    def benchmark(self) -> str:
        return "1306.T" if self.ticker.endswith(".T") else "SPY"

    def history(self, ticker: str, period: str) -> pd.DataFrame:
        key = (ticker.strip().upper(), period)
        if key not in self.history_cache:
            reusable = self._reusable_history(*key)
            self.history_cache[key] = (
                reusable if reusable is not None else self.history_provider(*key)
            )
        return self.history_cache[key]

    def _reusable_history(self, ticker: str, period: str) -> pd.DataFrame | None:
        requested_sessions = PERIOD_SESSIONS.get(period)
        if requested_sessions is None:
            return None
        candidates = [
            (PERIOD_SESSIONS[cached_period], frame)
            for (cached_ticker, cached_period), frame in self.history_cache.items()
            if cached_ticker == ticker
            and cached_period in PERIOD_SESSIONS
            and PERIOD_SESSIONS[cached_period] >= requested_sessions
            and frame is not None
            and not frame.empty
        ]
        if not candidates:
            return None
        _, frame = min(candidates, key=lambda item: item[0])
        return frame.tail(requested_sessions).copy()

    def info(self, ticker: str, *, include_summary: bool = True) -> dict[str, Any]:
        key = ticker.strip().upper()
        if key not in self.info_cache or (
            include_summary and key not in self.info_with_summary
        ):
            kwargs = {"translate_summary": False}
            if not include_summary:
                kwargs["include_summary"] = False
            self.info_cache[key] = self.info_provider(key, **kwargs)
            if include_summary:
                self.info_with_summary.add(key)
        return self.info_cache[key]

    def news(self, ticker: str, max_items: int = 5) -> dict[str, Any]:
        key = (ticker.strip().upper(), max_items)
        if key not in self.news_cache:
            self.news_cache[key] = self.news_provider(*key)
        return self.news_cache[key]
