"""
Market Index Data Provider
主要な市場指数・コモディティ・暗号資産のデータを取得します。
"""

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from src.cache import ttl_cache
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
    """Stooqから日本市場データを取得する（タイムアウト付き）"""
    try:
        url = f"https://stooq.com/q/l/?s={ticker}&f=sd2t2ohlcv&h&e=csv"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        if df.empty or "Close" not in df.columns:
            return None
        close = float(df["Close"].iloc[0])
        open_price = float(df["Open"].iloc[0])
        if math.isnan(close) or math.isnan(open_price):
            return None
        change = ((close - open_price) / open_price * 100) if open_price != 0 else 0.0
        return close, round(change, 2)
    except Exception as e:
        logger.info(f"[STOOQ_WARN] Failed to fetch {ticker}: {e}")
        return None


@ttl_cache(ttl=CACHE_TTL_MEDIUM)
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

    # 生指数ティッカー（^始まり）はFinnhubで取得不可 → yfinanceに回す
    raw_index_tickers = {k: v for k, v in finnhub_targets.items() if v.startswith("^")}
    yf_targets.update(raw_index_tickers)
    finnhub_targets = {k: v for k, v in finnhub_targets.items() if not v.startswith("^")}

    if not is_configured():
        yf_targets.update(finnhub_targets)
        finnhub_targets = {}


    def _fetch_finnhub(n: str, t: str) -> tuple[str, str, dict | None]:
        try:
            return n, t, _finnhub_get_quote(t)
        except Exception:
            return n, t, None

    if finnhub_targets:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_fetch_finnhub, n, t) for n, t in finnhub_targets.items()]
            for future in as_completed(futures):
                n, t, q = future.result()
                if isinstance(q, dict) and q.get("c") not in (0, None):
                    result[n] = {
                        "price": float(q.get("c", 0.0)),  # type: ignore
                        "change": float(q.get("dp", 0.0)),  # type: ignore
                        "ticker": t,
                    }
                else:
                    yf_targets[n] = t

    def _fetch_yf(n: str, t: str) -> tuple[str, str, dict]:
        try:
            hist = yf.Ticker(t).history(period="5d")
            if "Close" in hist.columns:
                hist.dropna(subset=["Close"], inplace=True)
            else:
                hist.dropna(inplace=True)

            if not hist.empty and len(hist) >= 1:
                if "Close" in hist.columns:
                    current = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                else:
                    current = hist.iloc[-1, 0]
                    prev = hist.iloc[-2, 0] if len(hist) >= 2 else current

                # NaN ガード
                if math.isnan(current) or math.isnan(prev):
                    return n, t, {"price": 0.0, "change": 0.0, "ticker": t}

                change = ((current - prev) / prev) * 100 if prev != 0 else 0
                return n, t, {
                    "price": float(current),
                    "change": float(change),
                    "ticker": t,
                }
            else:
                return n, t, {"price": 0.0, "change": 0.0, "ticker": t}
        except Exception as e:
            logger.warning(f"[MarketIndexProvider] Failed to fetch {t}: {e}")
            return n, t, {"price": 0.0, "change": 0.0, "ticker": t}

    if yf_targets:
        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(_fetch_yf, n, t) for n, t in yf_targets.items()]
                for future in as_completed(futures):
                    n, t, data = future.result()
                    result[n] = data
        except Exception as e:
            logger.error(f"[MarketIndexProvider] Batch download execution failed: {e}")

    return result
