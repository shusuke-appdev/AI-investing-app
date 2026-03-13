"""
Option Data Provider
オプションチェーンのデータ取得を担当。
"""

import pandas as pd
import yfinance as yf

from src.finnhub_client import (
    get_option_chain as _finnhub_get_option_chain,
)
from src.finnhub_client import (
    is_configured,
)
from src.log_config import get_logger

logger = get_logger(__name__)


def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Get option chain data. Priority: Finnhub (Greeks included) -> yfinance fallback."""
    if is_configured():
        try:
            result = _finnhub_get_option_chain(ticker)
            if result is not None:
                return result
        except Exception as e:
            logger.error(f"[DataProvider] Finnhub option chain error for {ticker}: {e}")
            logger.info(f"[DataProvider] Falling back to yfinance for {ticker}")

    try:
        stock = yf.Ticker(ticker)
        try:
            expirations = stock.options
        except Exception as e:
            logger.warning(
                f"[DataProvider] yfinance stock.options failed for {ticker}: {e}"
            )
            return None

        if not expirations:
            logger.warning(
                f"[DataProvider] yfinance returned no expirations for {ticker}"
            )
            return None

        all_calls = []
        all_puts = []
        for exp in expirations[:4]:
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
                    f"[DataProvider] yfinance option_chain({exp}) failed for {ticker}: {e}"
                )
                continue

        if not all_calls:
            logger.warning(
                f"[DataProvider] yfinance returned no option chains for {ticker}"
            )
            return None

        return pd.concat(all_calls, ignore_index=True), pd.concat(
            all_puts, ignore_index=True
        )
    except Exception as e:
        logger.error(f"[DataProvider] Option fetch error for {ticker}: {e}")
        return None
