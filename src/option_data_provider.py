"""
Option Data Provider
オプションチェーンのデータ取得を担当。
リトライ・タイムアウト・フォールバックキャッシュ機構搭載。
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from src.log_config import get_logger
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
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


def _is_market_likely_closed() -> bool:
    """米国市場が閉場中かどうかの簡易判定（週末チェック）"""
    now = datetime.now(timezone.utc)
    # 土曜=5, 日曜=6
    return now.weekday() in (5, 6)


def _fetch_option_chain_raw(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
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
    # yfinance API負荷を制御: 起動時・更新時とも直近期限だけを取得する
    max_expirations = min(MAX_EXPIRATIONS, len(expirations))
    for i, exp in enumerate(expirations[:max_expirations]):
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
        if i < max_expirations - 1:
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
    ticker: str, timeout: int = FETCH_TIMEOUT
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """タイムアウト付きでオプションデータを取得"""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_fetch_option_chain_raw, ticker)
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


def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
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
    cached_fresh = _load_persistent_cache(ticker, max_age_seconds=OPTION_CACHE_TTL)
    if cached_fresh is not None:
        calls, puts, fetched_at, cache_status, cache_age_seconds = cached_fresh
        _remember_success(ticker, calls, puts)
        _set_metadata(
            ticker,
            source="persistent_cache",
            fetched_at=fetched_at,
            is_stale=False,
            data_quality="available",
            quality_warnings=[],
            cache_status=cache_status,
            cache_age_seconds=cache_age_seconds,
        )
        return calls, puts

    cached_stale = _load_persistent_cache(
        ticker,
        max_age_seconds=OPTION_STALE_TTL,
        fresh_seconds=OPTION_CACHE_TTL,
    )

    # 市場閉場時はフォールバックキャッシュを優先
    if _is_market_likely_closed():
        with _fallback_lock:
            if ticker in _fallback_cache:
                logger.info(
                    f"[OptionProvider] Market closed, using fallback cache for {ticker}"
                )
                _set_metadata(
                    ticker,
                    source="memory_fallback",
                    fetched_at="",
                    is_stale=True,
                    data_quality="stale_cache",
                    quality_warnings=[
                        "Market is likely closed; using in-memory option cache."
                    ],
                    cache_status="memory_cache",
                    cache_age_seconds=None,
                )
                return _fallback_cache[ticker]
        if cached_stale is not None:
            calls, puts, fetched_at, cache_status, cache_age_seconds = cached_stale
            _remember_success(ticker, calls, puts)
            _set_metadata(
                ticker,
                source="persistent_cache",
                fetched_at=fetched_at,
                is_stale=True,
                data_quality="stale_cache",
                quality_warnings=[
                    f"Market is likely closed; using cached option data from {fetched_at}."
                ],
                cache_status=cache_status,
                cache_age_seconds=cache_age_seconds,
            )
            return calls, puts

    # リトライループ
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = _fetch_with_timeout(ticker)
            if result is not None:
                # 成功 → フォールバックキャッシュに保存
                calls, puts = result
                _remember_success(ticker, calls, puts)
                fetched_at = utc_now_iso()
                _save_persistent_cache(ticker, calls, puts, fetched_at)
                _set_metadata(
                    ticker,
                    source="yfinance",
                    fetched_at=fetched_at,
                    is_stale=False,
                    data_quality="available",
                    quality_warnings=[],
                    cache_status="live",
                    cache_age_seconds=None,
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
        if ticker in _fallback_cache:
            logger.info(
                f"[OptionProvider] All retries failed for {ticker}, using fallback cache"
            )
            _set_metadata(
                ticker,
                source="memory_fallback",
                fetched_at="",
                is_stale=True,
                data_quality="stale_cache",
                quality_warnings=[
                    "Option refresh failed; using in-memory option cache."
                ],
                cache_status="memory_cache",
                cache_age_seconds=None,
            )
            return _fallback_cache[ticker]

    if cached_stale is not None:
        calls, puts, fetched_at, cache_status, cache_age_seconds = cached_stale
        _remember_success(ticker, calls, puts)
        _set_metadata(
            ticker,
            source="persistent_cache",
            fetched_at=fetched_at,
            is_stale=True,
            data_quality="stale_cache",
            quality_warnings=[
                f"Option refresh failed; using cached option data from {fetched_at}."
            ],
            cache_status=cache_status,
            cache_age_seconds=cache_age_seconds,
        )
        return calls, puts

    logger.error(
        f"[OptionProvider] All retries exhausted for {ticker}, no fallback available. "
        f"Last error: {last_error}"
    )
    _set_metadata(
        ticker,
        source="yfinance",
        fetched_at="",
        is_stale=False,
        data_quality="failed",
        quality_warnings=["Option data unavailable and no cache exists."],
        cache_status="failed",
        cache_age_seconds=None,
    )
    return None


def get_option_chain_metadata(ticker: str) -> dict[str, Any]:
    """Return metadata for the most recent option-chain lookup."""

    with _metadata_lock:
        return dict(_metadata_cache.get(ticker.upper(), {}))


def _remember_success(ticker: str, calls: pd.DataFrame, puts: pd.DataFrame) -> None:
    with _fallback_lock:
        _fallback_cache[ticker] = (calls, puts)


def _set_metadata(
    ticker: str,
    *,
    source: str,
    fetched_at: str,
    is_stale: bool,
    data_quality: str,
    quality_warnings: list[str],
    cache_status: str,
    cache_age_seconds: float | None,
) -> None:
    with _metadata_lock:
        _metadata_cache[ticker.upper()] = {
            "source": source,
            "fetched_at": fetched_at,
            "is_stale": is_stale,
            "data_quality": data_quality,
            "quality_warnings": quality_warnings,
            "cache_status": cache_status,
            "cache_age_seconds": cache_age_seconds,
        }


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
