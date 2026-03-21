"""
Option Data Provider
オプションチェーンのデータ取得を担当。
"""

import pandas as pd
import requests
import yfinance as yf

from src.log_config import get_logger

logger = get_logger(__name__)


def _get_yf_session() -> requests.Session:
    """Returns a requests Session with a custom User-Agent to help bypass blocks."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    )
    return session


def get_option_chain(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Get option chain data. Uses strictly yfinance to avoid Finnhub 403 API errors."""
    try:
        session = _get_yf_session()
        stock = yf.Ticker(ticker, session=session)
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
