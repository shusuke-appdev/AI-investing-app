"""Shared, immutable price histories for one market-analysis refresh."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field

import pandas as pd

from src.market_data import get_stock_data

_PERIOD_OFFSETS = {
    "1y": pd.DateOffset(years=1),
    "6mo": pd.DateOffset(months=6),
}
_MARKET_INPUT_EXECUTOR = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="market-input",
)


@dataclass(frozen=True, slots=True)
class MarketAnalysisInputs:
    """Histories fetched once and sliced for all analyses in one refresh."""

    market_type: str
    histories: dict[str, pd.DataFrame | None] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def history(self, ticker: str, period: str) -> pd.DataFrame | None:
        frame = self.histories.get(ticker)
        if frame is None or frame.empty:
            return frame
        if period == "5y":
            return frame.copy()
        if period == "5d":
            return frame.tail(5).copy()
        offset = _PERIOD_OFFSETS.get(period)
        if offset is None:
            return frame.copy()
        last = pd.Timestamp(frame.index.max())
        return frame.loc[frame.index >= last - offset].copy()


def build_market_analysis_inputs(
    market_type: str,
    *,
    include_detail: bool = True,
    fetcher: Callable[[str, str], pd.DataFrame | None] = get_stock_data,
    timeout_seconds: float = 12.0,
) -> MarketAnalysisInputs:
    """Fetch each required ticker once at its longest required period."""

    if market_type != "US":
        return MarketAnalysisInputs(market_type=market_type)

    requests = {
        "SPY": "5y" if include_detail else "1y",
        "^NDX": "1y",
        "^TNX": "5d",
    }
    if include_detail:
        requests["TLT"] = "1y"

    histories: dict[str, pd.DataFrame | None] = {}
    errors: dict[str, str] = {}
    futures = {
        _MARKET_INPUT_EXECUTOR.submit(fetcher, ticker, period): ticker
        for ticker, period in requests.items()
    }
    try:
        for future in as_completed(futures, timeout=timeout_seconds):
            ticker = futures[future]
            try:
                histories[ticker] = future.result()
            except (
                Exception
            ) as exc:  # preserve absence; callers retain their prior result
                histories[ticker] = None
                errors[ticker] = str(exc)
    except FutureTimeoutError:
        for future, ticker in futures.items():
            if future.done():
                continue
            future.cancel()
            histories[ticker] = None
            errors[ticker] = f"history fetch timed out after {timeout_seconds:g}s"

    return MarketAnalysisInputs(
        market_type=market_type, histories=histories, errors=errors
    )


def shared_history(
    inputs: MarketAnalysisInputs | None,
    ticker: str,
    period: str,
    fallback: Callable[[str, str], pd.DataFrame | None],
) -> pd.DataFrame | None:
    """Use shared input when supplied; never refetch a missing shared value."""

    if inputs is not None:
        return inputs.history(ticker, period)
    return fallback(ticker, period)
