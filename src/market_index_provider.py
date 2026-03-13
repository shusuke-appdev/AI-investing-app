"""
Market Index Data Provider
主要な市場指数・コモディティ・暗号資産のデータを取得します。
"""

import pandas as pd
import streamlit as st
import yfinance as yf

from src.constants import CACHE_TTL_MEDIUM, MARKET_US
from src.finnhub_client import get_quote as _finnhub_get_quote
from src.finnhub_client import is_configured
from src.log_config import get_logger
from src.market_config import get_market_config
from src.models import MarketIndex

logger = get_logger(__name__)

# --- 日本市場用 Stooq データ取得 ---
JP_STOOQ_TICKERS: dict[str, str] = {
    "日経225": "^NKX",
    "TOPIX": "^TPX",
    "10年国債": "10YJP.B",
}


def _get_stooq_data(ticker: str) -> tuple[float, float] | None:
    """Stooqから日本市場データを取得する"""
    try:
        url = f"https://stooq.com/q/l/?s={ticker}&f=sd2t2ohlcv&h&e=csv"
        df = pd.read_csv(url)
        if df.empty or "Close" not in df.columns:
            return None
        close = float(df["Close"].iloc[0])
        open_price = float(df["Open"].iloc[0])
        change = ((close - open_price) / open_price * 100) if open_price != 0 else 0.0
        return close, round(change, 2)
    except Exception as e:
        logger.info(f"[STOOQ_WARN] Failed to fetch {ticker}: {e}")
        return None


@st.cache_data(ttl=CACHE_TTL_MEDIUM)
def get_market_indices(market_type: str = MARKET_US) -> dict[str, MarketIndex]:
    """Get major market indices data."""
    config = get_market_config(market_type)
    result: dict[str, MarketIndex] = {}

    if market_type == "JP":
        for name, ticker in JP_STOOQ_TICKERS.items():
            data = _get_stooq_data(ticker)
            if data:
                result[name] = {"price": data[0], "change": data[1], "ticker": ticker}
        return result

    finnhub_targets = {
        **config.get("indices", {}),
        **config.get("sectors", {}),
        **config.get("commodities", {}),
        **config.get("crypto", {}),
    }

    yf_targets = {**config.get("treasuries", {}), **config.get("forex", {})}

    if not is_configured():
        yf_targets.update(finnhub_targets)
        finnhub_targets = {}

    for name, ticker in finnhub_targets.items():
        try:
            q = _finnhub_get_quote(ticker)
            if isinstance(q, dict) and q.get("c") not in (0, None):
                result[name] = {
                    "price": q.get("c"),
                    "change": q.get("dp", 0),
                    "ticker": ticker,
                }
            else:
                yf_targets[name] = ticker
        except Exception:
            yf_targets[name] = ticker

    if yf_targets:
        try:
            tickers_list = list(yf_targets.values())
            if tickers_list:
                batch_data = yf.download(
                    tickers_list,
                    period="5d",
                    progress=False,
                )

                for name, ticker in yf_targets.items():
                    try:
                        hist = batch_data
                        if len(tickers_list) > 1 and isinstance(
                            batch_data.columns, pd.MultiIndex
                        ):
                            hist = batch_data.xs(ticker, level=1, axis=1)

                        if isinstance(hist, pd.DataFrame) and isinstance(
                            hist.columns, pd.MultiIndex
                        ):
                            try:
                                hist = hist.xs(ticker, level=1, axis=1)
                            except Exception:
                                pass
                        try:
                            single_hist = yf.Ticker(
                                ticker
                            ).history(period="5d")
                            if not single_hist.empty:
                                hist = single_hist
                        except Exception as e:
                            logger.warning(f"Fallback fetch failed for {ticker}: {e}")

                        if not hist.empty and len(hist) >= 1:
                            current = hist["Close"].iloc[-1]
                            prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                            change = ((current - prev) / prev) * 100 if prev != 0 else 0
                            result[name] = {
                                "price": float(current),
                                "change": float(change),
                                "ticker": ticker,
                            }
                        else:
                            result[name] = {
                                "price": 0.0,
                                "change": 0.0,
                                "ticker": ticker,
                            }
                    except Exception:
                        pass
        except Exception:
            pass

    return result
