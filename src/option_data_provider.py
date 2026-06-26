"""
Option Data Provider
オプションチェーンのデータ取得を担当。
リトライ・タイムアウト・フォールバックキャッシュ機構搭載。
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from src.log_config import get_logger
from src.marketdata_client import is_configured as marketdata_is_configured
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
from src.theme_taxonomy import marketdata_option_universe
from src.yfinance_runtime import configure_yfinance_cache

logger = get_logger(__name__)
configure_yfinance_cache()

# フォールバックキャッシュ: 最終成功データを保持（市場閉場時に前回データを返す）
_fallback_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
_fallback_lock = threading.Lock()
_metadata_cache: dict[str, dict[str, Any]] = {}
_metadata_lock = threading.Lock()

# リトライ設定
MAX_RETRIES = 1
FETCH_TIMEOUT = 10  # 秒
BACKOFF_BASE = 2  # 指数バックオフのベース
MAX_EXPIRATIONS = 1
OPTION_CACHE_TTL = 900
OPTION_STALE_TTL = 86400
OPTION_CACHE_NAMESPACE = "option_chain_cache"
MARKETDATA_OPTION_TICKERS = marketdata_option_universe()
MARKETDATA_OPTIONS_MODES = {"off", "shadow", "preferred"}


def _is_market_likely_closed() -> bool:
    """米国市場が閉場中かどうかの簡易判定（週末チェック）"""
    now = datetime.now(timezone.utc)
    # 土曜=5, 日曜=6
    return now.weekday() in (5, 6)


def _select_yfinance_expirations(
    expirations: list[str],
    *,
    target_dte: int | None,
    min_dte: int,
    max_expirations: int,
) -> list[str]:
    today = datetime.now(timezone.utc).date()
    parsed: list[tuple[str, date]] = []
    for value in expirations:
        try:
            parsed.append((value, datetime.fromisoformat(str(value)).date()))
        except ValueError:
            logger.debug("[OptionProvider] Ignoring unparseable expiration: %s", value)
    if not parsed:
        return []

    minimum_date = today + timedelta(days=max(min_dte, 0))
    candidates = [(raw, exp) for raw, exp in parsed if exp >= minimum_date]
    if not candidates:
        candidates = [(raw, exp) for raw, exp in parsed if exp >= today]
    if not candidates:
        return []

    if target_dte is None:
        selected = sorted(candidates, key=lambda item: item[1])
    else:
        target_date = today + timedelta(days=max(target_dte, 0))
        selected = sorted(
            candidates,
            key=lambda item: (abs((item[1] - target_date).days), item[1]),
        )
    return [raw for raw, _ in selected[: max(1, max_expirations)]]


def _fetch_option_chain_raw(
    ticker: str, *, target_dte: int | None = None, min_dte: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """yfinanceからオプションチェーンを取得する内部関数（タイムアウトなし）"""
    stock = yf.Ticker(ticker)
    try:
        expirations = stock.options
    except Exception as e:
        logger.warning(f"[OptionProvider] Failed to get expirations for {ticker}: {e}")
        return None

    if not expirations:
        logger.warning(
            f"[OptionProvider] yfinance returned no expirations for {ticker}"
        )
        return None

    all_calls = []
    all_puts = []
    selected_expirations = _select_yfinance_expirations(
        list(expirations),
        target_dte=target_dte,
        min_dte=min_dte,
        max_expirations=MAX_EXPIRATIONS,
    )
    if not selected_expirations:
        logger.warning(
            f"[OptionProvider] yfinance returned no valid expirations for {ticker}"
        )
        return None

    for i, exp in enumerate(selected_expirations):
        try:
            opt = stock.option_chain(exp)
            if opt.calls is None or opt.puts is None:
                logger.warning(
                    f"[OptionProvider] yfinance option_chain({exp}) returned incomplete data for {ticker}"
                )
                continue
            calls = opt.calls.copy()
            puts = opt.puts.copy()
            if calls.empty or puts.empty:
                logger.warning(
                    f"[OptionProvider] yfinance option_chain({exp}) returned empty data for {ticker}"
                )
                continue
            calls["expiration"] = exp
            puts["expiration"] = exp
            all_calls.append(calls)
            all_puts.append(puts)
        except Exception as e:
            logger.warning(
                f"[OptionProvider] yfinance option_chain({exp}) failed for {ticker}: {e}"
            )
            continue
        # yfinance Rate Limit対策: 期限間に短い待機
        if i < len(selected_expirations) - 1:
            time.sleep(0.3)

    if not all_calls or not all_puts:
        logger.warning(
            f"[OptionProvider] yfinance returned no option chains for {ticker}"
        )
        return None

    calls_df = pd.concat(all_calls, ignore_index=True)
    puts_df = pd.concat(all_puts, ignore_index=True)

    # カラム名の正規化（yfinanceバージョン差分吸収）
    col_map = {
        "Volume": "volume",
        "Open Interest": "openInterest",
        "Implied Volatility": "impliedVolatility",
        "Strike": "strike",
        "Last Price": "lastPrice",
    }
    calls_df.rename(
        columns={k: v for k, v in col_map.items() if k in calls_df.columns},
        inplace=True,
    )
    puts_df.rename(
        columns={k: v for k, v in col_map.items() if k in puts_df.columns}, inplace=True
    )

    return calls_df, puts_df


def _fetch_with_timeout(
    ticker: str,
    timeout: int = FETCH_TIMEOUT,
    *,
    target_dte: int | None = None,
    min_dte: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """タイムアウト付きでオプションデータを取得"""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        _fetch_option_chain_raw,
        ticker,
        target_dte=target_dte,
        min_dte=min_dte,
    )
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError:
        logger.warning(
            f"[OptionProvider] Timeout ({timeout}s) fetching options for {ticker}"
        )
        return None
    except Exception as e:
        logger.warning(f"[OptionProvider] Error fetching options for {ticker}: {e}")
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def get_option_chain(
    ticker: str,
    *,
    allow_marketdata: bool = False,
    cache_only: bool = False,
    target_dte: int | None = None,
    min_dte: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """
    オプションチェーンデータを取得する。

    リトライ（最大3回・指数バックオフ）、タイムアウト（15秒）、
    フォールバックキャッシュ（最終成功データの再利用）を備えた堅牢な取得関数。

    Args:
        ticker: ティッカーシンボル (例: "SPY")

    Returns:
        (calls_df, puts_df) のタプル。取得不可の場合はNone。
    """
    ticker = ticker.upper()
    cache_key = _option_cache_key(ticker, target_dte)
    requested_mode = _marketdata_options_mode() if allow_marketdata else "off"
    mode = requested_mode
    if not _marketdata_allowed_for_ticker(ticker):
        mode = "off"
        requested_mode = "off"
    marketdata_unconfigured = allow_marketdata and not marketdata_is_configured()
    if marketdata_unconfigured:
        mode = "off"
    if cache_only:
        cached = _load_persistent_cache(cache_key, max_age_seconds=OPTION_STALE_TTL)
        if cached is None:
            return None
        calls, puts, fetched_at, cache_status, cache_age_seconds = cached
        _remember_success(cache_key, calls, puts)
        _set_metadata(
            ticker,
            target_dte=target_dte,
            source="yfinance",
            fetched_at=fetched_at,
            cache_status=cache_status,
            cache_age_seconds=cache_age_seconds,
            is_stale=cache_status == "stale_cache",
            data_quality="stale_cache"
            if cache_status == "stale_cache"
            else "available",
            quality_warnings=[
                "通常の銘柄分析では保存済みオプションデータのみ使用しています。"
            ],
            provider_active=False,
            fallback_reason="通常の銘柄分析では保存済みオプションデータのみ使用しています。",
        )
        return calls, puts

    if mode == "preferred":
        marketdata_result = _call_marketdata_chain(ticker, target_dte, min_dte)
        if marketdata_result is not None:
            calls, puts, metadata = marketdata_result
            metadata = dict(metadata)
            metadata.pop("target_dte", None)
            _set_metadata(ticker, target_dte=target_dte, **metadata)
            return calls, puts

    yfinance_result = _call_yfinance_chain(ticker, target_dte, min_dte)

    if allow_marketdata and (requested_mode == "preferred" or marketdata_unconfigured):
        metadata = get_option_chain_metadata(ticker, target_dte=target_dte)
        warnings = list(metadata.get("quality_warnings") or [])
        fallback_reason = (
            "MarketData.app preferred fetch unavailable; yfinance fallback is active."
            if marketdata_is_configured()
            else "MarketData.app token is not configured; yfinance fallback is active."
        )
        warnings.append(fallback_reason)
        metadata["quality_warnings"] = warnings
        metadata["marketdata_options_mode"] = requested_mode
        metadata["provider_active"] = False
        metadata["fallback_reason"] = fallback_reason
        metadata["target_dte"] = target_dte
        _replace_metadata(ticker, metadata, target_dte=target_dte)

    if requested_mode == "shadow":
        marketdata_result = (
            None
            if marketdata_unconfigured
            else _call_marketdata_chain(ticker, target_dte, min_dte)
        )
        metadata = get_option_chain_metadata(ticker, target_dte=target_dte)
        warnings = list(metadata.get("quality_warnings") or [])
        if marketdata_unconfigured:
            warnings.append(
                "MarketData.app token is not configured; shadow comparison is skipped."
            )
        elif marketdata_result is None:
            warnings.append(
                "MarketData.app shadow comparison unavailable; yfinance result retained."
            )
        else:
            _, _, shadow_metadata = marketdata_result
            warnings.append(
                "MarketData.app shadow comparison succeeded; "
                "yfinance nearest-expiry result retained. "
                f"expiration={shadow_metadata.get('resolved_expiration') or 'unknown'}, "
                f"as_of={shadow_metadata.get('data_as_of') or 'unknown'}, "
                f"mode={shadow_metadata.get('data_mode') or 'unknown'}, "
                f"credits={shadow_metadata.get('credits_consumed')}."
            )
            metadata.update(
                {
                    "shadow_source": shadow_metadata.get("source", "marketdata.app"),
                    "shadow_data_as_of": shadow_metadata.get("data_as_of", ""),
                    "shadow_data_mode": shadow_metadata.get("data_mode", ""),
                    "shadow_credits_consumed": shadow_metadata.get("credits_consumed"),
                    "shadow_credits_remaining": shadow_metadata.get(
                        "credits_remaining"
                    ),
                    "shadow_resolved_expiration": shadow_metadata.get(
                        "resolved_expiration", ""
                    ),
                    "shadow_resolved_dte": shadow_metadata.get("resolved_dte"),
                }
            )
        metadata["quality_warnings"] = warnings
        metadata["marketdata_options_mode"] = requested_mode
        metadata["provider_active"] = False
        metadata["target_dte"] = target_dte
        metadata.setdefault("fallback_reason", "")
        _replace_metadata(ticker, metadata, target_dte=target_dte)

    return yfinance_result


def _call_marketdata_chain(
    ticker: str, target_dte: int | None, min_dte: int
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]] | None:
    if target_dte is None and min_dte == 0:
        return _fetch_marketdata_chain(ticker)
    return _fetch_marketdata_chain(ticker, target_dte=target_dte, min_dte=min_dte)


def _call_yfinance_chain(
    ticker: str, target_dte: int | None, min_dte: int
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    if target_dte is None and min_dte == 0:
        return _get_yfinance_option_chain(ticker)
    return _get_yfinance_option_chain(ticker, target_dte=target_dte, min_dte=min_dte)


def _get_yfinance_option_chain(
    ticker: str,
    *,
    target_dte: int | None = None,
    min_dte: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Return the existing yfinance/cache option path."""

    cache_key = _option_cache_key(ticker, target_dte)
    cached_fresh = _load_persistent_cache(cache_key, max_age_seconds=OPTION_CACHE_TTL)
    if cached_fresh is not None:
        calls, puts, fetched_at, cache_status, cache_age_seconds = cached_fresh
        _remember_success(cache_key, calls, puts)
        _set_metadata(
            ticker,
            target_dte=target_dte,
            source="persistent_cache",
            fetched_at=fetched_at,
            is_stale=False,
            data_quality="available",
            quality_warnings=[],
            cache_status=cache_status,
            cache_age_seconds=cache_age_seconds,
            provider_active=False,
            fallback_reason="",
        )
        return calls, puts

    cached_stale = _load_persistent_cache(
        cache_key,
        max_age_seconds=OPTION_STALE_TTL,
        fresh_seconds=OPTION_CACHE_TTL,
    )

    # 市場閉場時はフォールバックキャッシュを優先
    if _is_market_likely_closed():
        with _fallback_lock:
            if cache_key in _fallback_cache:
                logger.info(
                    f"[OptionProvider] Market closed, using fallback cache for {ticker}"
                )
                _set_metadata(
                    ticker,
                    target_dte=target_dte,
                    source="memory_fallback",
                    fetched_at="",
                    is_stale=True,
                    data_quality="stale_cache",
                    quality_warnings=[
                        "Market is likely closed; using in-memory option cache."
                    ],
                    cache_status="memory_cache",
                    cache_age_seconds=None,
                    provider_active=False,
                    fallback_reason="Market is likely closed; using in-memory option cache.",
                )
                return _fallback_cache[cache_key]
        if cached_stale is not None:
            calls, puts, fetched_at, cache_status, cache_age_seconds = cached_stale
            _remember_success(cache_key, calls, puts)
            _set_metadata(
                ticker,
                target_dte=target_dte,
                source="persistent_cache",
                fetched_at=fetched_at,
                is_stale=True,
                data_quality="stale_cache",
                quality_warnings=[
                    f"Market is likely closed; using cached option data from {fetched_at}."
                ],
                cache_status=cache_status,
                cache_age_seconds=cache_age_seconds,
                provider_active=False,
                fallback_reason=(
                    f"Market is likely closed; using cached option data from {fetched_at}."
                ),
            )
            return calls, puts

    # リトライループ
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = _fetch_with_timeout(
                ticker,
                target_dte=target_dte,
                min_dte=min_dte,
            )
            if result is not None:
                # 成功 → フォールバックキャッシュに保存
                calls, puts = result
                _remember_success(cache_key, calls, puts)
                fetched_at = utc_now_iso()
                _save_persistent_cache(cache_key, calls, puts, fetched_at)
                _set_metadata(
                    ticker,
                    target_dte=target_dte,
                    source="yfinance",
                    fetched_at=fetched_at,
                    is_stale=False,
                    data_quality="available",
                    quality_warnings=[],
                    cache_status="live",
                    cache_age_seconds=None,
                    provider_active=False,
                    fallback_reason="",
                )
                return result
        except Exception as e:
            last_error = e
            logger.warning(
                f"[OptionProvider] Attempt {attempt + 1}/{MAX_RETRIES} failed for {ticker}: {e}"
            )

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_BASE**attempt
            logger.info(f"[OptionProvider] Retrying in {wait}s...")
            time.sleep(wait)

    # 全リトライ失敗 → フォールバックキャッシュ
    with _fallback_lock:
        if cache_key in _fallback_cache:
            logger.info(
                f"[OptionProvider] All retries failed for {ticker}, using fallback cache"
            )
            _set_metadata(
                ticker,
                target_dte=target_dte,
                source="memory_fallback",
                fetched_at="",
                is_stale=True,
                data_quality="stale_cache",
                quality_warnings=[
                    "Option refresh failed; using in-memory option cache."
                ],
                cache_status="memory_cache",
                cache_age_seconds=None,
                provider_active=False,
                fallback_reason="Option refresh failed; using in-memory option cache.",
            )
            return _fallback_cache[cache_key]

    if cached_stale is not None:
        calls, puts, fetched_at, cache_status, cache_age_seconds = cached_stale
        _remember_success(cache_key, calls, puts)
        _set_metadata(
            ticker,
            target_dte=target_dte,
            source="persistent_cache",
            fetched_at=fetched_at,
            is_stale=True,
            data_quality="stale_cache",
            quality_warnings=[
                f"Option refresh failed; using cached option data from {fetched_at}."
            ],
            cache_status=cache_status,
            cache_age_seconds=cache_age_seconds,
            provider_active=False,
            fallback_reason=f"Option refresh failed; using cached option data from {fetched_at}.",
        )
        return calls, puts

    logger.error(
        f"[OptionProvider] All retries exhausted for {ticker}, no fallback available. "
        f"Last error: {last_error}"
    )
    _set_metadata(
        ticker,
        target_dte=target_dte,
        source="yfinance",
        fetched_at="",
        is_stale=False,
        data_quality="failed",
        quality_warnings=["Option data unavailable and no cache exists."],
        cache_status="failed",
        cache_age_seconds=None,
        provider_active=False,
        fallback_reason="Option data unavailable and no cache exists.",
    )
    return None


def _marketdata_options_mode() -> str:
    default_mode = "preferred" if marketdata_is_configured() else "off"
    mode = os.getenv("MARKETDATA_OPTIONS_MODE", default_mode).strip().lower()
    return mode if mode in MARKETDATA_OPTIONS_MODES else "off"


def marketdata_options_status() -> dict[str, Any]:
    """Return non-secret MarketData.app option configuration status."""

    raw_mode = os.getenv("MARKETDATA_OPTIONS_MODE", "").strip().lower()
    configured = marketdata_is_configured()
    effective_mode = _marketdata_options_mode()
    return {
        "token_configured": configured,
        "configured_mode": raw_mode or "<unset>",
        "effective_mode": effective_mode,
        "is_active": configured and effective_mode in {"preferred", "shadow"},
        "allowed_tickers": sorted(MARKETDATA_OPTION_TICKERS),
        "expiration_policy": "auto",
        "smoke_min_dte": 1,
        "horizon_target_dtes": [7, 30],
    }


def _marketdata_allowed_for_ticker(ticker: str) -> bool:
    normalized = ticker.upper()
    if normalized.endswith(".T"):
        return False
    return normalized in MARKETDATA_OPTION_TICKERS


def _fetch_marketdata_chain(
    ticker: str,
    *,
    target_dte: int | None = None,
    min_dte: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]] | None:
    try:
        from src.marketdata_option_provider import fetch_marketdata_option_chain

        result = fetch_marketdata_option_chain(
            ticker, target_dte=target_dte, min_dte=min_dte
        )
    except Exception as exc:
        logger.warning(f"[OptionProvider] MarketData.app failed for {ticker}: {exc}")
        return None
    if result is None:
        return None
    metadata = result.metadata()
    metadata["marketdata_options_mode"] = _marketdata_options_mode()
    metadata["provider_active"] = True
    metadata["fallback_reason"] = ""
    return result.calls, result.puts, metadata


def get_option_chain_metadata(
    ticker: str, *, target_dte: int | None = None
) -> dict[str, Any]:
    """Return metadata for the most recent option-chain lookup."""

    with _metadata_lock:
        return dict(_metadata_cache.get(_metadata_key(ticker, target_dte), {}))


def _remember_success(ticker: str, calls: pd.DataFrame, puts: pd.DataFrame) -> None:
    with _fallback_lock:
        _fallback_cache[ticker] = (calls, puts)


def _set_metadata(
    ticker: str,
    *,
    target_dte: int | None = None,
    source: str,
    fetched_at: str,
    is_stale: bool,
    data_quality: str,
    quality_warnings: list[str],
    cache_status: str,
    cache_age_seconds: float | None,
    **extra: Any,
) -> None:
    payload = {
        "source": source,
        "fetched_at": fetched_at,
        "is_stale": is_stale,
        "data_quality": data_quality,
        "quality_warnings": quality_warnings,
        "cache_status": cache_status,
        "cache_age_seconds": cache_age_seconds,
        "target_dte": target_dte,
        **extra,
    }
    with _metadata_lock:
        _metadata_cache[_metadata_key(ticker, target_dte)] = dict(payload)
        if target_dte is None:
            _metadata_cache[ticker.upper()] = dict(payload)


def _replace_metadata(
    ticker: str, metadata: dict[str, Any], *, target_dte: int | None = None
) -> None:
    payload = {**metadata, "target_dte": target_dte}
    with _metadata_lock:
        _metadata_cache[_metadata_key(ticker, target_dte)] = dict(payload)
        if target_dte is None:
            _metadata_cache[ticker.upper()] = dict(payload)


def _metadata_key(ticker: str, target_dte: int | None = None) -> str:
    return (
        ticker.upper() if target_dte is None else f"{ticker.upper()}::dte{target_dte}"
    )


def _option_cache_key(ticker: str, target_dte: int | None = None) -> str:
    return ticker.upper() if target_dte is None else f"{ticker.upper()}_dte{target_dte}"


def _cache_file(ticker: str) -> Path:
    return _option_cache().path_for_key(ticker)


def _save_persistent_cache(
    ticker: str, calls: pd.DataFrame, puts: pd.DataFrame, fetched_at: str
) -> None:
    path = _cache_file(ticker)
    payload = {
        "ticker": ticker,
        "fetched_at": fetched_at,
        "calls": _frame_payload(calls),
        "puts": _frame_payload(puts),
    }
    try:
        _option_cache().write_path(path, ticker, payload, fetched_at=fetched_at)
    except OSError as exc:
        logger.debug(
            f"[OptionProvider] Failed to write option cache for {ticker}: {exc}"
        )


def _load_persistent_cache(
    ticker: str, *, max_age_seconds: int, fresh_seconds: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, str, str, float | None] | None:
    path = _cache_file(ticker)
    read = _option_cache().read_path(
        path,
        ticker,
        fresh_seconds=fresh_seconds or max_age_seconds,
        stale_seconds=max_age_seconds,
    )
    if not read.is_available:
        return None

    payload = read.payload
    fetched_at = read.fetched_at

    calls = _frame_from_payload(payload.get("calls") or {})
    puts = _frame_from_payload(payload.get("puts") or {})
    if calls.empty or puts.empty:
        return None
    cache_status = "stale_cache" if read.is_stale else "persistent_cache"
    return calls, puts, fetched_at, cache_status, read.age_seconds


def _frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    clean = df.astype(object).where(pd.notna(df), None)
    return {"records": clean.to_dict("records")}


def _frame_from_payload(payload: dict[str, Any]) -> pd.DataFrame:
    records = payload.get("records") if isinstance(payload, dict) else []
    return pd.DataFrame(records or [])


def _option_cache() -> PersistentJsonCache:
    return repo_state_cache(OPTION_CACHE_NAMESPACE)
