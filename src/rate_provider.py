"""Source-defined percent yields shared by Reflex and local research."""

import pandas as pd

from src.economic_data_provider import fetch_fred_series

RATE_SERIES = {"^TNX": "DGS10", "^TYX": "DGS30", "^FVX": "DGS5", "^IRX": "DTB3"}


def rate_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    series = RATE_SERIES[ticker]
    result = fetch_fred_series(
        (series,),
        start="2024-01-01",
        csv_timeout=10,
        use_pandas_datareader_fallback=False,
    )
    frame = (
        result.data[[series]].dropna().rename(columns={series: "Close"})
        if series in result.data
        else pd.DataFrame()
    )
    frame.attrs["fetch_metadata"] = {
        "source": f"https://fred.stlouisfed.org/series/{series}",
        "series_id": series,
        "unit": "%",
        "price_basis": "official percent yield; not a stock price",
        "fetched_at": result.fetched_at,
        "cache_status": result.cache_status,
        "is_stale": result.is_stale,
        "is_partial": result.is_partial,
        "error": "金利取得不足・前回値" if result.error else "",
    }
    if not frame.empty:
        frame.attrs["fetch_metadata"]["observed_on"] = (
            pd.Timestamp(frame.index[-1]).date().isoformat()
        )
    periods = {"5d": 5, "1mo": 22, "3mo": 66, "6mo": 132, "1y": 264}
    return frame.tail(periods[period]).copy() if period in periods else frame
