"""MarketData.app option-chain retrieval and normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from src.log_config import get_logger
from src.marketdata_client import MarketDataClient, MarketDataError
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
from src.provider_result import FetchResult

logger = get_logger(__name__)

MARKETDATA_OPTION_CACHE_NAMESPACE = "marketdata_option_chain_cache"
MARKETDATA_OPTION_CACHE_TTL = 900
MARKETDATA_OPTION_STALE_TTL = 86400
MARKETDATA_EXPIRATION_CACHE_TTL = 300
DEFAULT_DTE = 0
DEFAULT_STRIKE_LIMIT = 100
DEFAULT_EXPIRATION_POLICY = "auto"
SMOKE_EXPIRATION_POLICY = "next_valid"
MARKETDATA_EASTERN_TZ = ZoneInfo("America/New_York")
SAME_DAY_EXPIRATION_CUTOFF_ET = time(15, 45)
OPTION_COLUMNS = (
    "optionSymbol,underlying,expiration,side,strike,dte,volume,openInterest,"
    "underlyingPrice,iv,delta,gamma,theta,vega,updated"
)
_expiration_cache: dict[str, tuple[datetime, list[date]]] = {}


@dataclass(kw_only=True)
class MarketDataOptionResult(FetchResult[None]):
    """Normalized option chain and provider metadata."""

    calls: pd.DataFrame
    puts: pd.DataFrame
    data: None = None
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
    resolved_expiration: str = ""
    resolved_dte: int | None = None
    target_dte: int | None = None
    expiration_policy: str = DEFAULT_EXPIRATION_POLICY
    expiration_fallback_reason: str = ""
    error_code: str = ""
    quality_warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Keep the compatibility alias synchronized with the shared contract."""

        combined = list(dict.fromkeys([*self.warnings, *self.quality_warnings]))
        self.warnings = combined
        self.quality_warnings = combined

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
            "resolved_expiration": self.resolved_expiration,
            "resolved_dte": self.resolved_dte,
            "target_dte": self.target_dte,
            "expiration_policy": self.expiration_policy,
            "expiration_fallback_reason": self.expiration_fallback_reason,
            "error_code": self.error_code,
        }


def fetch_marketdata_option_chain(
    ticker: str,
    *,
    dte: int | None = None,
    target_dte: int | None = None,
    min_dte: int = 0,
    expiration_policy: str = DEFAULT_EXPIRATION_POLICY,
    strike_limit: int = DEFAULT_STRIKE_LIMIT,
    data_mode: str = "account_default",
    allow_stale: bool = True,
    force_refresh: bool = False,
    client: MarketDataClient | None = None,
) -> MarketDataOptionResult | None:
    """Fetch a bounded option chain, with a provider-specific stale cache."""

    ticker = ticker.upper()
    api = client or MarketDataClient()
    expiration = None
    expiration_reason = ""
    resolved_dte = dte
    if dte is None:
        try:
            expiration, resolved_dte, expiration_reason = resolve_option_expiration(
                ticker,
                target_dte=target_dte,
                min_dte=min_dte,
                expiration_policy=expiration_policy,
                client=api,
                use_cache=client is None,
            )
        except MarketDataError as exc:
            logger.warning(
                "[MarketDataOptions] %s expiration resolution failed: %s", ticker, exc
            )
            return _stale_for_resolution_failure(
                ticker,
                strike_limit,
                data_mode,
                allow_stale,
                str(exc),
                getattr(exc, "code", "api_error"),
            )

    cache_key = _cache_key(
        ticker,
        dte=resolved_dte,
        expiration=expiration,
        strike_limit=strike_limit,
        data_mode=data_mode,
    )
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
        params = {
            "strikeLimit": strike_limit,
            "nonstandard": "false",
            "columns": OPTION_COLUMNS,
        }
        if expiration:
            params["expiration"] = expiration
        elif dte is not None:
            params["dte"] = dte
        else:
            params["dte"] = DEFAULT_DTE
        if data_mode != "account_default":
            params["mode"] = data_mode
        response = api.get(f"/options/chain/{ticker}/", params=params)
        frame = normalize_option_chain_response(response.data)
        if frame.empty:
            return _with_warning(
                stale,
                f"MarketData.app returned no option rows for {ticker} "
                f"expiration={expiration or 'dte=' + str(dte)}.",
                error_code="no_data",
            )
        calls = (
            frame[frame["side"] == "call"].drop(columns=["side"]).reset_index(drop=True)
        )
        puts = (
            frame[frame["side"] == "put"].drop(columns=["side"]).reset_index(drop=True)
        )
        if calls.empty or puts.empty:
            return _with_warning(
                stale,
                f"MarketData.app returned incomplete call/put rows for {ticker}.",
                error_code="no_data",
            )
        fetched_at = utc_now_iso()
        resolved_expiration = expiration or _first_expiration(frame)
        resolved_dte = _first_dte(frame, resolved_dte)
        result = MarketDataOptionResult(
            calls=calls,
            puts=puts,
            fetched_at=fetched_at,
            data_as_of=_latest_timestamp(frame.get("updated")),
            data_mode=data_mode,
            credits_consumed=response.credits_consumed,
            credits_remaining=response.credits_remaining,
            credits_reset_at=response.credits_reset_at,
            resolved_expiration=resolved_expiration,
            resolved_dte=resolved_dte,
            target_dte=target_dte,
            expiration_policy=expiration_policy,
            expiration_fallback_reason=expiration_reason,
        )
        _save_cache(cache_key, result)
        return result
    except MarketDataError as exc:
        logger.warning("[MarketDataOptions] %s fetch failed: %s", ticker, exc)
        return _with_warning(
            stale,
            f"MarketData.app fetch failed for {ticker}: {exc}",
            error_code=getattr(exc, "code", "api_error"),
        )


def resolve_option_expiration(
    ticker: str,
    *,
    target_dte: int | None = None,
    min_dte: int = 0,
    expiration_policy: str = DEFAULT_EXPIRATION_POLICY,
    client: MarketDataClient | None = None,
    use_cache: bool | None = None,
    now: datetime | None = None,
) -> tuple[str, int, str]:
    """Return a stable expiration date for MarketData.app option-chain requests."""

    api = client or MarketDataClient()
    expirations = _load_expirations(
        ticker.upper(),
        api,
        use_cache=(client is None if use_cache is None else use_cache),
    )
    if not expirations:
        raise MarketDataError(
            "MarketData.app returned no option expirations.", code="no_data"
        )
    selected, reason = _select_expiration(
        expirations,
        target_dte=target_dte,
        min_dte=min_dte,
        expiration_policy=expiration_policy,
        now=now,
    )
    today = _eastern_now(now).date()
    dte = max(0, (selected - today).days)
    return selected.isoformat(), dte, reason


def _load_expirations(
    ticker: str, api: MarketDataClient, *, use_cache: bool
) -> list[date]:
    if use_cache:
        cached = _expiration_cache.get(ticker)
        now = datetime.now(timezone.utc)
        if cached is not None:
            fetched_at, expirations = cached
            age = (now - fetched_at).total_seconds()
            if age <= MARKETDATA_EXPIRATION_CACHE_TTL:
                return list(expirations)
    response = api.get(f"/options/expirations/{ticker}/")
    expirations = _extract_expiration_dates(response.data)
    if use_cache and expirations:
        _expiration_cache[ticker] = (datetime.now(timezone.utc), list(expirations))
    return expirations


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


def _extract_expiration_dates(data: dict[str, Any]) -> list[date]:
    values: list[Any] = []
    for key, value in data.items():
        if key == "s" or not isinstance(value, list):
            continue
        if key.lower() in {"expirations", "expiration", "date", "dates"}:
            values = value
            break
        if not values:
            values = value
    expirations = sorted(
        {
            parsed
            for parsed in (_parse_expiration_date(value) for value in values)
            if parsed is not None
        }
    )
    return expirations


def _parse_expiration_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        number = float(text)
    except ValueError:
        return None
    return datetime.fromtimestamp(_epoch_seconds(number), tz=timezone.utc).date()


def _select_expiration(
    expirations: list[date],
    *,
    target_dte: int | None,
    min_dte: int,
    expiration_policy: str,
    now: datetime | None,
) -> tuple[date, str]:
    current_et = _eastern_now(now)
    today = current_et.date()
    if target_dte is not None:
        minimum_date = today + timedelta(days=max(min_dte, 0))
        candidates = [
            expiration for expiration in expirations if expiration >= minimum_date
        ]
        if not candidates:
            candidates = [
                expiration for expiration in expirations if expiration >= today
            ]
        if candidates:
            target_date = today + timedelta(days=max(target_dte, 0))
            selected = min(
                candidates,
                key=lambda expiration: (
                    abs((expiration - target_date).days),
                    expiration,
                ),
            )
            return (
                selected,
                f"expiration closest to target_dte={target_dte} selected.",
            )
        raise MarketDataError(
            "MarketData.app expirations are all in the past.", code="expired_option"
        )
    policy = (
        expiration_policy
        if expiration_policy in {"auto", "same_day", "next_valid"}
        else "auto"
    )
    if policy == "same_day" and today in expirations and min_dte <= 0:
        return today, "same-day expiration explicitly requested."
    if (
        policy == "auto"
        and min_dte <= 0
        and today in expirations
        and current_et.time() < SAME_DAY_EXPIRATION_CUTOFF_ET
    ):
        return today, "same-day expiration selected before the 15:45 ET cutoff."

    effective_min_dte = max(min_dte, 1 if policy in {"auto", "next_valid"} else min_dte)
    minimum_date = today + timedelta(days=effective_min_dte)
    for expiration in expirations:
        if expiration >= minimum_date:
            if today in expirations and expiration != today:
                return (
                    expiration,
                    "same-day expiration skipped after cutoff or by min_dte.",
                )
            return expiration, "next valid expiration selected."
    for expiration in expirations:
        if expiration >= today:
            return (
                expiration,
                "no expiration met min_dte; nearest non-expired expiration selected.",
            )
    raise MarketDataError(
        "MarketData.app expirations are all in the past.", code="expired_option"
    )


def _eastern_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MARKETDATA_EASTERN_TZ)


def _first_expiration(frame: pd.DataFrame) -> str:
    if "expiration" not in frame.columns:
        return ""
    values = frame["expiration"].dropna().astype(str)
    return str(values.iloc[0]) if not values.empty else ""


def _first_dte(frame: pd.DataFrame, fallback: int | None) -> int | None:
    if "dte" not in frame.columns:
        return fallback
    values = pd.to_numeric(frame["dte"], errors="coerce").dropna()
    if values.empty:
        return fallback
    return int(values.iloc[0])


def _cache_key(
    ticker: str,
    *,
    dte: int | None,
    expiration: str | None,
    strike_limit: int,
    data_mode: str,
) -> str:
    expiration_key = f"exp{expiration.replace('-', '')}" if expiration else f"dte{dte}"
    return f"{ticker}_{expiration_key}_strike{strike_limit}_{data_mode}"


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
    return _result_from_cache_read(read)


def _result_from_cache_read(read) -> MarketDataOptionResult | None:
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
        resolved_expiration=str(metadata.get("resolved_expiration") or ""),
        resolved_dte=_optional_int(metadata.get("resolved_dte")),
        target_dte=_optional_int(metadata.get("target_dte")),
        expiration_policy=str(
            metadata.get("expiration_policy") or DEFAULT_EXPIRATION_POLICY
        ),
        expiration_fallback_reason=str(
            metadata.get("expiration_fallback_reason") or ""
        ),
        error_code=str(metadata.get("error_code") or ""),
        quality_warnings=warnings,
    )


def _stale_for_resolution_failure(
    ticker: str,
    strike_limit: int,
    data_mode: str,
    allow_stale: bool,
    warning: str,
    error_code: str,
) -> MarketDataOptionResult | None:
    if not allow_stale:
        return None
    prefix = f"{ticker}_"
    cache = _cache()
    suffix = f"_strike{strike_limit}_{data_mode}"
    try:
        paths = sorted(cache.root.glob(f"{prefix}*{suffix}.json"), reverse=True)
    except OSError:
        paths = []
    for path in paths:
        key = path.stem
        read = cache.read_path(
            path,
            key,
            fresh_seconds=MARKETDATA_OPTION_CACHE_TTL,
            stale_seconds=MARKETDATA_OPTION_STALE_TTL,
        )
        if not read.is_available:
            continue
        stale = _result_from_cache_read(read)
        if stale is not None:
            return _with_warning(stale, warning, error_code=error_code)
    return None


def _with_warning(
    result: MarketDataOptionResult | None, warning: str, *, error_code: str
) -> MarketDataOptionResult | None:
    if result is None:
        return None
    result.quality_warnings = [*result.quality_warnings, warning]
    result.error_code = error_code
    return result


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
