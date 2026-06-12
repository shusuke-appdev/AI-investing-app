"""MarketData.app option-chain retrieval and normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.log_config import get_logger
from src.marketdata_client import MarketDataClient, MarketDataError
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso

logger = get_logger(__name__)

MARKETDATA_OPTION_CACHE_NAMESPACE = "marketdata_option_chain_cache"
MARKETDATA_OPTION_CACHE_TTL = 900
MARKETDATA_OPTION_STALE_TTL = 86400
DEFAULT_DTE = 0
DEFAULT_STRIKE_LIMIT = 100
OPTION_COLUMNS = (
    "optionSymbol,underlying,expiration,side,strike,dte,volume,openInterest,"
    "underlyingPrice,iv,delta,gamma,theta,vega,updated"
)


@dataclass
class MarketDataOptionResult:
    """Normalized option chain and provider metadata."""

    calls: pd.DataFrame
    puts: pd.DataFrame
    source: str = "marketdata.app"
    fetched_at: str = ""
    data_as_of: str = ""
    data_mode: str = "account_default"
    is_stale: bool = False
    cache_status: str = "live"
    cache_age_seconds: float | None = None
    credits_consumed: int | None = None
    credits_remaining: int | None = None
    credits_reset_at: str = ""
    quality_warnings: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at,
            "data_as_of": self.data_as_of,
            "data_mode": self.data_mode,
            "is_stale": self.is_stale,
            "data_quality": "stale_cache" if self.is_stale else "available",
            "quality_warnings": list(self.quality_warnings),
            "cache_status": self.cache_status,
            "cache_age_seconds": self.cache_age_seconds,
            "credits_consumed": self.credits_consumed,
            "credits_remaining": self.credits_remaining,
            "credits_reset_at": self.credits_reset_at,
        }


def fetch_marketdata_option_chain(
    ticker: str,
    *,
    dte: int = DEFAULT_DTE,
    strike_limit: int = DEFAULT_STRIKE_LIMIT,
    data_mode: str = "account_default",
    allow_stale: bool = True,
    force_refresh: bool = False,
    client: MarketDataClient | None = None,
) -> MarketDataOptionResult | None:
    """Fetch a bounded option chain, with a provider-specific stale cache."""

    ticker = ticker.upper()
    cache_key = _cache_key(ticker, dte, strike_limit, data_mode)
    if not force_refresh:
        cached = _load_cache(
            cache_key,
            max_age_seconds=MARKETDATA_OPTION_CACHE_TTL,
            fresh_seconds=MARKETDATA_OPTION_CACHE_TTL,
        )
        if cached is not None:
            return cached

    stale = (
        _load_cache(
            cache_key,
            max_age_seconds=MARKETDATA_OPTION_STALE_TTL,
            fresh_seconds=MARKETDATA_OPTION_CACHE_TTL,
        )
        if allow_stale
        else None
    )
    try:
        api = client or MarketDataClient()
        params = {
            "dte": dte,
            "strikeLimit": strike_limit,
            "nonstandard": "false",
            "columns": OPTION_COLUMNS,
        }
        if data_mode != "account_default":
            params["mode"] = data_mode
        response = api.get(f"/options/chain/{ticker}/", params=params)
        frame = normalize_option_chain_response(response.data)
        if frame.empty:
            return stale
        calls = (
            frame[frame["side"] == "call"].drop(columns=["side"]).reset_index(drop=True)
        )
        puts = (
            frame[frame["side"] == "put"].drop(columns=["side"]).reset_index(drop=True)
        )
        if calls.empty or puts.empty:
            return stale
        fetched_at = utc_now_iso()
        result = MarketDataOptionResult(
            calls=calls,
            puts=puts,
            fetched_at=fetched_at,
            data_as_of=_latest_timestamp(frame.get("updated")),
            data_mode=data_mode,
            credits_consumed=response.credits_consumed,
            credits_remaining=response.credits_remaining,
            credits_reset_at=response.credits_reset_at,
        )
        _save_cache(cache_key, result)
        return result
    except MarketDataError as exc:
        logger.warning("[MarketDataOptions] %s fetch failed: %s", ticker, exc)
        return stale


def normalize_option_chain_response(data: dict[str, Any]) -> pd.DataFrame:
    """Normalize MarketData.app's columnar response into the app option schema."""

    if data.get("s") == "no_data":
        return pd.DataFrame()
    payload = {
        key: value
        for key, value in data.items()
        if key != "s" and isinstance(value, list)
    }
    if not payload:
        return pd.DataFrame()
    lengths = {len(value) for value in payload.values()}
    if len(lengths) != 1:
        raise MarketDataError("MarketData.app option columns have mismatched lengths.")

    frame = pd.DataFrame(payload).rename(columns={"iv": "impliedVolatility"})
    required = {"side", "strike", "volume", "openInterest", "impliedVolatility"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise MarketDataError(
            "MarketData.app option response is missing: " + ", ".join(missing)
        )
    frame["side"] = frame["side"].astype(str).str.lower()
    frame = frame[frame["side"].isin({"call", "put"})].copy()
    if "expiration" in frame.columns:
        frame["expiration"] = frame["expiration"].map(_expiration_date)
    numeric_columns = (
        "strike",
        "dte",
        "volume",
        "openInterest",
        "underlyingPrice",
        "impliedVolatility",
        "delta",
        "gamma",
        "theta",
        "vega",
        "updated",
    )
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _expiration_date(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    return datetime.fromtimestamp(_epoch_seconds(number), tz=timezone.utc).strftime(
        "%Y-%m-%d"
    )


def _latest_timestamp(values: pd.Series | None) -> str:
    if values is None:
        return ""
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return ""
    return datetime.fromtimestamp(
        _epoch_seconds(float(numeric.max())), tz=timezone.utc
    ).isoformat()


def _epoch_seconds(value: float) -> float:
    return value / 1000.0 if value > 10_000_000_000 else value


def _cache_key(ticker: str, dte: int, strike_limit: int, data_mode: str) -> str:
    return f"{ticker}_dte{dte}_strike{strike_limit}_{data_mode}"


def _save_cache(key: str, result: MarketDataOptionResult) -> None:
    payload = {
        "calls": _frame_payload(result.calls),
        "puts": _frame_payload(result.puts),
        "metadata": result.metadata(),
    }
    try:
        _cache().write(key, payload, fetched_at=result.fetched_at)
    except OSError as exc:
        logger.debug("[MarketDataOptions] Failed to write cache for %s: %s", key, exc)


def _load_cache(
    key: str, *, max_age_seconds: int, fresh_seconds: int
) -> MarketDataOptionResult | None:
    read = _cache().read(
        key, fresh_seconds=fresh_seconds, stale_seconds=max_age_seconds
    )
    if not read.is_available:
        return None
    calls = _frame_from_payload(read.payload.get("calls"))
    puts = _frame_from_payload(read.payload.get("puts"))
    if calls.empty or puts.empty:
        return None
    metadata = read.payload.get("metadata") or {}
    warnings = list(metadata.get("quality_warnings") or [])
    if read.is_stale:
        warnings.append(
            f"Using cached MarketData.app option data from {read.fetched_at}."
        )
    return MarketDataOptionResult(
        calls=calls,
        puts=puts,
        source="marketdata.app_cache",
        fetched_at=read.fetched_at,
        data_as_of=str(metadata.get("data_as_of") or ""),
        data_mode=str(metadata.get("data_mode") or "account_default"),
        is_stale=read.is_stale,
        cache_status="stale_cache" if read.is_stale else "persistent_cache",
        cache_age_seconds=read.age_seconds,
        credits_consumed=_optional_int(metadata.get("credits_consumed")),
        credits_remaining=_optional_int(metadata.get("credits_remaining")),
        credits_reset_at=str(metadata.get("credits_reset_at") or ""),
        quality_warnings=warnings,
    )


def _frame_payload(frame: pd.DataFrame) -> dict[str, Any]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return {"records": clean.to_dict("records")}


def _frame_from_payload(payload: Any) -> pd.DataFrame:
    records = payload.get("records") if isinstance(payload, dict) else []
    return pd.DataFrame(records or [])


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cache() -> PersistentJsonCache:
    return repo_state_cache(MARKETDATA_OPTION_CACHE_NAMESPACE)
