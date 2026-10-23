"""Source-labelled index histories and calendar-aligned offline comparisons."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from io import StringIO

import pandas as pd
import requests

PERIODS = {"1mo": 1, "3mo": 3, "6mo": 6, "1y": 12, "2y": 24}


def history_points(frame: pd.DataFrame) -> list[dict]:
    if "Close" not in frame.columns:
        return []
    points = {}
    for timestamp, value in frame["Close"].items():
        try:
            number = float(value)
            observed = pd.Timestamp(timestamp).date().isoformat()
        except (TypeError, ValueError):
            continue
        if (
            math.isfinite(number)
            and number > 0
            and observed <= date.today().isoformat()
        ):
            points[observed] = {"date": observed, "price": number}
    return [points[key] for key in sorted(points)]


def _yahoo(ticker: str, label: str, *, proxy: bool = False) -> dict:
    from src.stock_data_provider import get_historical_data_with_status

    result = get_historical_data_with_status(ticker, "2y")
    points = history_points(result.data)
    return {
        "ticker": ticker,
        "label": label,
        "source": "Yahoo Finance / yfinance",
        "url": f"https://finance.yahoo.com/quote/{ticker}/history/",
        "source_type": "etf_proxy" if proxy else "direct_index",
        "price_basis": "provider adjusted daily close"
        if proxy
        else "daily index close",
        "fetched_at": result.fetched_at,
        "observed_at": points[-1]["date"] if points else None,
        "is_stale": result.is_stale,
        "status": "available" if points else "unavailable",
        "warnings": list(result.warnings),
        "points": points,
    }


def _topix() -> dict:
    """Prefer the native index; never stitch ETF and index histories."""
    try:
        response = requests.get(
            "https://stooq.com/q/d/l/",
            params={"s": "^tpx", "i": "d"},
            timeout=8,
        )
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text), index_col="Date", parse_dates=True)
        frame = frame.loc[
            frame.index >= pd.Timestamp(date.today()) - pd.DateOffset(years=2)
        ]
        points = history_points(frame)
        if len(points) >= 2:
            return {
                "ticker": "^TPX",
                "label": "TOPIX",
                "source": "Stooq",
                "url": "https://stooq.com/q/?s=^tpx",
                "source_type": "direct_index",
                "price_basis": "daily index close",
                "points": points,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": points[-1]["date"],
                "is_stale": False,
                "status": "available",
                "warnings": [],
            }
    except (requests.RequestException, ValueError, KeyError, pd.errors.ParserError):
        pass
    result = _yahoo("1306.T", "TOPIX連動ETF・代理", proxy=True)
    result["warnings"].append(
        "TOPIX指数の日次履歴が取得できないため1306.Tを使用。ETF価格と指数値は別物です。"
    )
    return result


def fetch_comparisons(markets: tuple[str, ...] = ("US", "JP")) -> dict:
    if not markets or any(key not in {"US", "JP"} for key in markets):
        raise ValueError("Unsupported comparison market")
    jobs_by_market = {
        "US": [
            lambda: _yahoo("^GSPC", "S&P 500"),
            lambda: _yahoo("^NDX", "Nasdaq 100"),
        ],
        "JP": [lambda: _yahoo("^N225", "日経平均"), _topix],
    }
    jobs = [job for market in markets for job in jobs_by_market[market]]

    def isolated(job):
        try:
            return job()
        except Exception as exc:
            return {
                "status": "unavailable",
                "error_type": type(exc).__name__,
                "points": [],
            }

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(isolated, jobs))
    return {
        market: {"series": values[i * 2 : i * 2 + 2]}
        for i, market in enumerate(markets)
    }


def compare(series: list[dict], period: str) -> dict:
    """Use exact shared observation dates: no forward-fill or guessed year."""
    if period not in PERIODS:
        raise ValueError("Unsupported comparison period")
    maps = [{p["date"]: p["price"] for p in item.get("points", [])} for item in series]
    if len(maps) != 2 or any(not item for item in maps):
        return {"status": "unavailable", "series": series, "points": []}
    shared = sorted(set(maps[0]) & set(maps[1]))
    if len(shared) < 2:
        return {"status": "insufficient_data", "series": series, "points": []}
    cutoff = (
        (pd.Timestamp(shared[-1]) - pd.DateOffset(months=PERIODS[period]))
        .date()
        .isoformat()
    )
    dates = [key for key in shared if key >= cutoff]
    if len(dates) < 2:
        return {"status": "insufficient_data", "series": series, "points": []}
    bases = [item[dates[0]] for item in maps]
    partial = (
        shared[0] > (pd.Timestamp(cutoff) + pd.Timedelta(days=7)).date().isoformat()
    )
    return {
        "status": "partial" if partial else "available",
        "period": period,
        "start": dates[0],
        "end": dates[-1],
        "definition": "共通観測日の期間初日=100。終値のみ、休日と欠測は補完しません。",
        "series": [
            {
                **{key: val for key, val in item.items() if key != "points"},
                "latest": maps[i][dates[-1]],
                "return_pct": (maps[i][dates[-1]] / bases[i] - 1) * 100,
            }
            for i, item in enumerate(series)
        ],
        "points": [
            {
                "date": day,
                "values": [item[day] / bases[i] * 100 for i, item in enumerate(maps)],
            }
            for day in dates
        ],
    }


def comparison_views(raw: dict) -> dict:
    return {
        market: {
            period: compare(raw.get(market, {}).get("series", []), period)
            for period in PERIODS
        }
        for market in ("US", "JP")
    }
