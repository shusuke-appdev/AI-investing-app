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

import pandas as pd
import yfinance as yf

from src.log_config import get_logger

logger = get_logger(__name__)

# フォールバックキャッシュ: 最終成功データを保持（市場閉場時に前回データを返す）
_fallback_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
_fallback_lock = threading.Lock()

# リトライ設定
MAX_RETRIES = 3
FETCH_TIMEOUT = 15  # 秒
BACKOFF_BASE = 2  # 指数バックオフのベース


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
    # yfinance API負荷を制御: 最大3期限に制限し、期限間に待機
    max_expirations = min(3, len(expirations))
    for i, exp in enumerate(expirations[:max_expirations]):
        try:
            opt = stock.option_chain(exp)
            calls = opt.calls.copy()
            puts = opt.puts.copy()
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

    if not all_calls:
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
    with ThreadPoolExecutor(max_workers=1) as executor:
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
    # 市場閉場時はフォールバックキャッシュを優先
    if _is_market_likely_closed():
        with _fallback_lock:
            if ticker in _fallback_cache:
                logger.info(
                    f"[OptionProvider] Market closed, using fallback cache for {ticker}"
                )
                return _fallback_cache[ticker]

    # リトライループ
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = _fetch_with_timeout(ticker)
            if result is not None:
                # 成功 → フォールバックキャッシュに保存
                with _fallback_lock:
                    _fallback_cache[ticker] = result
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
            return _fallback_cache[ticker]

    logger.error(
        f"[OptionProvider] All retries exhausted for {ticker}, no fallback available. "
        f"Last error: {last_error}"
    )
    return None
