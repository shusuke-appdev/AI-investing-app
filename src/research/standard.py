"""Small shared-input path. Never invokes the legacy market/model workflows."""

from __future__ import annotations

import hashlib
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import median
from time import perf_counter

import pandas as pd

from src.persistent_cache import repo_state_cache, utc_now_iso
from src.research.bundle import plain
from src.research.comparison import history_points
from src.research.connections import connect
from src.research.public_sources import official_inputs
from src.services.price_integrity import usable_history
from src.theme_measurement import get_theme_measurement_baskets

PERIODS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
INDICES = {
    "US": [("^GSPC", "S&P 500"), ("^NDX", "Nasdaq 100")],
    "JP": [("^N225", "日経平均"), ("1306.T", "TOPIX連動ETF・代理")],
}


def current_history(frame: pd.DataFrame) -> bool:
    return bool(
        not frame.empty
        and not frame.attrs.get("fetch_metadata", {}).get("is_stale")
        and (
            datetime.now(timezone.utc).date() - pd.Timestamp(frame.index[-1]).date()
        ).days
        <= 7
        and pd.Timestamp(frame.index[-1]).date() <= datetime.now(timezone.utc).date()
    )


def fetch_prices(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Deduplicate across markets/themes/drivers; explicitly adjusted OHLCV."""
    import yfinance as yf

    symbols = sorted(set(tickers))
    cache = repo_state_cache("standard_prices")
    key = hashlib.sha256("|".join(symbols).encode()).hexdigest()
    saved = cache.read(key, fresh_seconds=900, stale_seconds=86400)
    payload = saved.payload
    status, error, fetched = "persistent_cache", "", saved.fetched_at
    if saved.status != "fresh":
        try:
            raw = yf.download(
                symbols,
                period="2y",
                auto_adjust=True,
                group_by="ticker",
                threads=8,
                progress=False,
                timeout=12,
            )
            frames = {
                symbol: raw[symbol]
                if isinstance(raw.columns, pd.MultiIndex)
                and symbol in raw.columns.get_level_values(0)
                else pd.DataFrame(columns=["Close"])
                if isinstance(raw.columns, pd.MultiIndex)
                else raw
                for symbol in symbols
            }
            payload = {
                symbol: [
                    {
                        "date": pd.Timestamp(i).date().isoformat(),
                        **{
                            c: float(v)
                            if pd.notna(v) and math.isfinite(float(v))
                            else None
                            for c, v in row.items()
                            if c in {"Close", "Open", "High", "Low", "Volume"}
                        },
                    }
                    for i, row in frame.dropna(subset=["Close"]).iterrows()
                ]
                for symbol, frame in frames.items()
            }
            if not any(payload.values()):
                raise ValueError("No usable prices")
            fetched, status = utc_now_iso(), "live"
            # Keep individual failed series separately, not silently replace with fresh old rows.
            cache.write(key, payload, fetched_at=fetched)
        except Exception as exc:
            payload = saved.payload if saved.is_available else {}
            status, error = (
                "stale_cache" if saved.is_available else "failed",
                f"価格更新失敗 ({type(exc).__name__})",
            )
    result = {}
    for symbol in symbols:
        # Today's still-open daily bar is not a closed observation.
        rows = [
            row
            for row in payload.get(symbol, [])
            if row["date"] < datetime.now(timezone.utc).date().isoformat()
        ]
        frame = pd.DataFrame(rows)
        if rows:
            frame.index = pd.to_datetime(frame.pop("date"))
        frame.attrs["fetch_metadata"] = {
            "source": f"https://finance.yahoo.com/quote/{symbol}/history/",
            "fetched_at": fetched,
            "cache_status": status,
            "is_stale": status == "stale_cache",
            "error": error,
            "price_basis": "adjusted OHLCV; auto_adjust=True; current UTC-day bar excluded",
        }
        result[symbol] = usable_history(frame)
    return result


def returns(
    frame: pd.DataFrame, benchmark: pd.DataFrame, days: int
) -> tuple[float | None, float | None, list[str]]:
    if frame.empty:
        return None, None, []
    if benchmark.empty:
        if len(frame) <= days:
            return None, None, []
        absolute = float(
            (frame["Close"].iloc[-1] / frame["Close"].iloc[-days - 1] - 1) * 100
        )
        return (
            absolute,
            None,
            [
                pd.Timestamp(frame.index[-days - 1]).date().isoformat(),
                pd.Timestamp(frame.index[-1]).date().isoformat(),
            ],
        )
    joined = pd.concat(
        [frame["Close"], benchmark["Close"]], axis=1, join="inner"
    ).dropna()
    # Missing trading observations inside the benchmark window are not compressed.
    if (
        len(joined) <= days
        or joined.index[-1] != benchmark.index[-1]
        or not joined.tail(days + 1).index.equals(benchmark.tail(days + 1).index)
    ):
        return None, None, []
    first, last = joined.iloc[-days - 1], joined.iloc[-1]
    absolute = (last.iloc[0] / first.iloc[0] - 1) * 100
    relative = absolute - (last.iloc[1] / first.iloc[1] - 1) * 100
    return (
        float(absolute),
        float(relative),
        [
            pd.Timestamp(joined.index[-days - 1]).date().isoformat(),
            pd.Timestamp(joined.index[-1]).date().isoformat(),
        ],
    )


def rank_themes(market: str, frames: dict, baskets: dict | None = None) -> dict:
    baskets = baskets if baskets is not None else get_theme_measurement_baskets(market)
    benchmark = frames.get("SPY" if market == "US" else "1306.T", pd.DataFrame())
    absolute_calendar = (
        benchmark
        if not benchmark.empty
        else frames.get(INDICES[market][0][0], pd.DataFrame())
    )
    items = []
    for name, basket in baskets.items():
        measured = basket["all_tickers"]
        registered = basket["all_tickers"]
        stocks = []
        for ticker in registered:
            frame = frames.get(ticker, pd.DataFrame())
            row = {
                "ticker": ticker,
                "periods": {},
                "source": frame.attrs.get("fetch_metadata", {}).get("source"),
                "quality": frame.attrs.get("price_integrity", {}),
            }
            for period, days in PERIODS.items():
                absolute, relative, dates = returns(frame, benchmark, days)
                if benchmark.empty:
                    absolute, _, dates = returns(frame, absolute_calendar, days)
                    relative = None
                row["periods"][period] = {
                    "return": absolute,
                    "relative_return": relative,
                    "observation_dates": dates,
                }
            stocks.append(row)
        item = {
            "theme": name,
            "representative_tickers": registered,
            "stocks": stocks,
            "measurement_tickers": measured,
            "measurement_method": "all_registered_standard",
            "period_status": {},
            "observation_dates": [],
        }
        for period in PERIODS:
            absolute_eligible = [
                s["periods"][period]
                for s in stocks
                if s["ticker"] in measured
                and s["periods"][period]["return"] is not None
                and current_history(frames[s["ticker"]])
                and current_history(absolute_calendar)
            ]
            absolute_valid = (
                bool(measured)
                and len(absolute_eligible) >= min(3, len(measured))
                and len(absolute_eligible) / len(measured) >= 0.6
            )
            eligible = [
                s["periods"][period]
                for s in stocks
                if s["ticker"] in measured
                and s["periods"][period]["relative_return"] is not None
                and current_history(frames[s["ticker"]])
                and current_history(benchmark)
            ]
            coverage = len(eligible) / len(measured) * 100 if measured else 0
            valid = (
                coverage >= 60
                and len(eligible) >= min(3, len(measured))
                and bool(measured)
            )
            item["coverage_" + period] = coverage
            item["count_" + period] = len(eligible)
            item["performance_" + period] = (
                median(r["return"] for r in absolute_eligible)
                if absolute_valid
                else None
            )
            item["absolute_count_" + period] = len(absolute_eligible)
            item["relative_" + period] = (
                median(r["relative_return"] for r in eligible) if valid else None
            )
            item["period_status"][period] = {
                "status": "available"
                if valid
                else "partial"
                if absolute_valid
                else "pending",
                "reason": "取得率60%以上・必要銘柄数を確認"
                if valid
                else "騰落率のみ。市場相対値は基準系列・同期間データの不足により未確認。"
                if absolute_valid
                else f"取得 {len(eligible)}/{len(measured)}。60%以上・min(3,登録数)が必要。",
                "observation_dates": absolute_eligible[0]["observation_dates"]
                if absolute_eligible
                else [],
            }
        item["observation_dates"] = item["period_status"]["6m"]["observation_dates"]
        items.append(item)
    items.sort(key=lambda r: (r["relative_6m"] is None, -(r["relative_6m"] or 0)))
    rank = 0
    for row in items:
        if row["relative_6m"] is not None:
            rank += 1
            row["rank"] = rank
        else:
            row["rank"] = None
    for period in PERIODS:
        eligible_rows = sorted(
            (r for r in items if r["relative_" + period] is not None),
            key=lambda r: -r["relative_" + period],
        )
        for row in items:
            row["rank_" + period] = None
        for n, row in enumerate(eligible_rows, 1):
            row["rank_" + period] = n
    return {
        "items": items,
        "profile": "standard",
        "method": "constituent-median-market-relative-v1",
        "default_period": "6m",
        "rank_label": "6か月・構成銘柄中央値の市場相対騰落順",
        "benchmark": "SPY" if market == "US" else "1306.T（TOPIX連動ETF代理）",
        "quality_warnings": [
            "登録された限定母集団の測定。全市場の広がり・実資金流入ではありません。"
        ],
        "calculated_at": utc_now_iso(),
        "fetched_at": min(
            (
                f.attrs.get("fetch_metadata", {}).get("fetched_at")
                for f in frames.values()
                if f.attrs.get("fetch_metadata", {}).get("fetched_at")
            ),
            default="",
        ),
    }


def observation(
    identifier: str,
    label: str,
    value: float | None,
    market: str,
    unit: str,
    window: str,
    frame: pd.DataFrame,
    parents: list[str],
    *,
    observed_on: str | None = None,
    basis: str | None = None,
) -> dict:
    metadata = frame.attrs.get("fetch_metadata", {})
    invalid_reason = ""
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        value, invalid_reason = None, "型違い・非有限値のため、この観測を使用しません。"
    observed = observed_on or (
        pd.Timestamp(frame.index[-1]).date().isoformat() if not frame.empty else None
    )
    old_observation = bool(
        observed
        and (datetime.now(timezone.utc).date() - pd.Timestamp(observed).date()).days > 7
    )
    count = re.fullmatch(r"(\d+)sessions?", window)
    days = int(count[1]) if count else 1
    offset = (
        days
        if ":ma" in identifier or identifier.endswith((":high20", ":low20"))
        else days + 1
        if days > 1
        else 1
    )
    start = (
        pd.Timestamp(frame.index[-offset]).date().isoformat()
        if len(frame) >= offset
        else None
    )
    return {
        "id": identifier,
        "label": label,
        "value": value,
        "market": market,
        "series_id": parents[0] if parents else identifier,
        "unit": unit,
        "window": window,
        "price_basis": basis or metadata.get("price_basis"),
        "observed_on": observed,
        "period_start": start,
        "period_end": observed,
        "source": metadata.get("source", ""),
        "history_source": metadata.get("history_source"),
        "history_fetched_at": metadata.get("history_fetched_at"),
        "fetched_at": metadata.get("fetched_at"),
        "cache_status": metadata.get("cache_status", "unknown"),
        "quality": "unavailable"
        if value is None
        else "stale"
        if metadata.get("is_stale") or old_observation
        else "available",
        "reason": invalid_reason
        or metadata.get("error")
        or frame.attrs.get("price_integrity", {}).get("reason", ""),
        "parents": parents,
    }


def price_observations(market: str, frames: dict) -> list[dict]:
    result = []
    primary = INDICES[market][0][0]
    for ticker, label in [
        *INDICES[market],
        ("JPY=X", "USD/JPY"),
        ("CL=F", "WTI先物"),
        *(([("RSP", "等加重ETF"), ("IWM", "小型株ETF")]) if market == "US" else []),
    ]:
        frame = frames.get(ticker, pd.DataFrame())
        close = frame.get("Close", pd.Series(dtype=float))
        prefix = "index" if ticker == primary else ticker
        for days in (20, 50, 200):
            value = (
                float((close.iloc[-1] / close.tail(days).mean() - 1) * 100)
                if len(close) >= days
                else None
            )
            result.append(
                observation(
                    f"{prefix}:ma{days}_gap",
                    f"{label} / {days}日線乖離",
                    value,
                    market,
                    "%",
                    f"{days}sessions",
                    frame,
                    [ticker],
                )
            )
        for period, days in PERIODS.items():
            value, _, _ = returns(frame, frame, days)
            result.append(
                observation(
                    f"{prefix}:return_{period}",
                    f"{label} / {period}騰落",
                    value,
                    market,
                    "%",
                    f"{days}sessions",
                    frame,
                    [ticker],
                )
            )
        for key, value in [
            ("close", float(close.iloc[-1]) if len(close) else None),
            (
                "high20",
                float(frame["High"].tail(20).max())
                if "High" in frame and len(frame) >= 20
                else None,
            ),
            (
                "low20",
                float(frame["Low"].tail(20).min())
                if "Low" in frame and len(frame) >= 20
                else None,
            ),
            (
                "volume",
                float(frame["Volume"].iloc[-1])
                if "Volume" in frame and len(frame)
                else None,
            ),
        ]:
            result.append(
                observation(
                    f"{prefix}:{key}",
                    f"{label} / {key}",
                    value,
                    market,
                    "volume"
                    if key == "volume"
                    else "index"
                    if ticker.startswith("^")
                    else "JPY"
                    if ticker == "1306.T"
                    else "price",
                    "1session" if key in {"close", "volume"} else "20sessions",
                    frame,
                    [ticker],
                )
            )
    if market == "US":
        for ticker, identifier in [("RSP", "rsp"), ("IWM", "iwm")]:
            frame, benchmark = (
                frames.get(ticker, pd.DataFrame()),
                frames.get("SPY", pd.DataFrame()),
            )
            absolute, relative, _ = returns(frame, benchmark, 126)
            ratio_change = (
                (((1 + absolute / 100) / (1 + (absolute - relative) / 100) - 1) * 100)
                if absolute is not None and relative is not None
                else None
            )
            result.append(
                observation(
                    "participation:" + identifier,
                    f"{ticker}/SPY / 6か月比率変化",
                    ratio_change,
                    "US",
                    "%",
                    "126sessions",
                    frame,
                    [ticker, "SPY"],
                    basis="adjusted close ratio; change(last/first -1)×100",
                )
            )
    members = list(
        {
            t
            for b in get_theme_measurement_baskets(market).values()
            for t in b["all_tickers"]
        }
    )
    eligible = [
        frames[t]
        for t in members
        if t in frames
        and len(frames[t]) >= 200
        and current_history(frames[t])
        and not frames.get(primary, pd.DataFrame()).empty
        and frames[t].index[-1] == frames[primary].index[-1]
    ]
    count = sum(
        float(f["Close"].iloc[-1]) > float(f["Close"].tail(200).mean())
        for f in eligible
    )
    row = observation(
        "participation:sample",
        "限定母集団 / 200日線上",
        count / len(eligible) * 100 if eligible else None,
        market,
        "%",
        "200sessions",
        frames.get(primary, pd.DataFrame()),
        members,
    )
    row.update(
        sample_count=len(eligible),
        registered_count=len(members),
        scope="registered measurement basket; not entire market",
    )
    result.append(row)
    return result


def macro_observations(market: str, fred, official: dict) -> list[dict]:
    result = []
    for series, label in [
        ("DGS10", "米10年金利"),
        ("DGS2", "米2年金利"),
        ("DFII10", "米実質10年"),
        ("BAMLH0A0HYM2", "米HY OAS"),
    ]:
        frame = fred.data[[series]].dropna() if series in fred.data else pd.DataFrame()
        frame.attrs["fetch_metadata"] = {
            "source": f"https://fred.stlouisfed.org/series/{series}",
            "fetched_at": fred.fetched_at,
            "cache_status": fred.cache_status,
            "is_stale": fred.is_stale,
            "error": "FRED取得不足・前回値" if fred.error else "",
        }
        values = frame.iloc[:, 0] if not frame.empty else pd.Series(dtype=float)
        root = "credit" if series == "BAMLH0A0HYM2" else series
        result.append(
            observation(
                root + ":level",
                label,
                float(values.iloc[-1]) if len(values) else None,
                "US",
                "%",
                "1session",
                frame,
                [series],
                basis="official percent",
            )
        )
        result.append(
            observation(
                root + ":change_1m",
                label + " / 21観測変化",
                float((values.iloc[-1] - values.iloc[-22]) * 100)
                if len(values) >= 22
                else None,
                "US",
                "bp",
                "21sessions",
                frame,
                [series],
                basis="percent difference ×100",
            )
        )
    mof = official["mof"]
    frame = pd.DataFrame(mof.get("points", []))
    if not frame.empty:
        frame.index = pd.to_datetime(frame.pop("date"))
    frame.attrs["fetch_metadata"] = mof
    result.append(
        observation(
            "JP10:level",
            "日本10年金利",
            float(frame["value"].iloc[-1]) if not frame.empty else None,
            "JP",
            "%",
            "1session",
            frame,
            ["MOF10"],
            basis="MOF official percent",
        )
    )
    result.append(
        observation(
            "JP10:change_1m",
            "日本10年金利 / 21観測変化",
            float((frame["value"].iloc[-1] - frame["value"].iloc[-22]) * 100)
            if len(frame) >= 22
            else None,
            "JP",
            "bp",
            "21sessions",
            frame,
            ["MOF10"],
            basis="percent difference ×100",
        )
    )
    # U.S. macro rows retain US scope even in the Japanese view.
    return result


def build_packets(
    market: str, frames: dict, fred, official: dict
) -> tuple[dict, dict, dict]:
    ranking = rank_themes(market, frames)
    from src.research.topdown import build_topdown

    topdown = build_topdown(market, frames, ranking)
    observations = price_observations(market, frames) + macro_observations(
        market, fred, official
    )
    vix = frames.get("^VIX", pd.DataFrame())
    for period, days in [("level", 0), ("change_1m", 21)]:
        values = vix.get("Close", pd.Series(dtype=float))
        value = (
            float(values.iloc[-1])
            if days == 0 and len(values)
            else float(values.iloc[-1] - values.iloc[-days - 1])
            if len(values) > days
            else None
        )
        observations.append(
            observation(
                "vix:" + period,
                "VIX / " + period,
                value,
                "US",
                "volatility points",
                "1session" if days == 0 else "21sessions",
                vix,
                ["^VIX"],
            )
        )
    # Compare on actual common observations, not price-today vs published-credit-yesterday.
    credit_frame = (
        fred.data[["BAMLH0A0HYM2"]].dropna()
        if "BAMLH0A0HYM2" in fred.data
        else pd.DataFrame()
    )
    credit_metadata = {
        "source": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "fetched_at": fred.fetched_at,
        "cache_status": fred.cache_status,
        "is_stale": fred.is_stale,
    }
    for ticker, root, label, is_return in [
        (INDICES[market][0][0], "index", "指数・信用", True),
        ("^VIX", "vix", "VIX・信用", False),
    ]:
        price = frames.get(ticker, pd.DataFrame())
        if price.empty or credit_frame.empty:
            continue
        common = price.index.intersection(credit_frame.index)
        if len(common) < 22:
            continue
        window = common[-22:]
        selected_price, selected_credit = (
            price.loc[window].copy(),
            credit_frame.loc[window].copy(),
        )
        selected_credit.attrs["fetch_metadata"] = credit_metadata
        value = (
            float(
                (selected_price.Close.iloc[-1] / selected_price.Close.iloc[0] - 1) * 100
            )
            if is_return
            else float(selected_price.Close.iloc[-1] - selected_price.Close.iloc[0])
        )
        a = observation(
            root + ":credit_aligned_1m",
            label + " / 共通21観測・価格",
            value,
            market if is_return else "US",
            "%" if is_return else "volatility points",
            "21sessions",
            selected_price,
            [ticker],
        )
        b = observation(
            "credit:" + root + "_aligned_1m",
            label + " / 共通21観測・信用",
            float((selected_credit.iloc[-1, 0] - selected_credit.iloc[0, 0]) * 100),
            "US",
            "bp",
            "21sessions",
            selected_credit,
            ["BAMLH0A0HYM2"],
            basis="percent difference ×100",
        )
        for row in (a, b):
            row["window"] = "21common_observations"
            row["period_start"] = pd.Timestamp(window[0]).date().isoformat()
            row["period_end"] = pd.Timestamp(window[-1]).date().isoformat()
            row["alignment"] = (
                "actual common dates; main observations keep their separate latest dates"
            )
        observations.extend([a, b])
    connected = connect(observations, ranking["items"])
    connected.update(
        profile="standard",
        events=official["events"],
        event_sources=official["event_sources"],
        jpx=official["jpx"],
    )
    data_status = [
        {
            "name": r["label"],
            "source": r["source"],
            "fetched_at": r["fetched_at"],
            "observed_on": r["observed_on"],
            "status": r["quality"],
            "cache_status": r["cache_status"],
            "is_stale": r["quality"] == "stale",
            "is_partial": r["quality"] == "unavailable",
            "error": r["reason"] if r["quality"] != "available" else None,
            "note": r["reason"] if r["quality"] == "available" else None,
        }
        for r in observations
    ]
    analysis = {
        "topdown": topdown,
        "market_type": market,
        "connected": connected,
        "trend_ranking": ranking,
        "data_status": data_status,
        "profile": "standard",
        "calculated_at": utc_now_iso(),
        "fetched_at": min(
            (r["fetched_at"] for r in observations if r["fetched_at"]), default=""
        ),
    }
    theme = {
        "ranking": ranking,
        "profile": "standard",
        "leaders": {
            "data": {
                "fundamental_pending": [
                    {
                        "ticker": t,
                        "reason": "代表銘柄は登録順。個別財務・主条件の更新は別途銘柄指定。",
                    }
                    for r in ranking["items"][:5]
                    for t in r["representative_tickers"][:3]
                ]
            }
        },
    }
    series = []
    for ticker, label in INDICES[market]:
        frame = frames.get(ticker, pd.DataFrame())
        points = history_points(frame)
        series.append(
            {
                "ticker": ticker,
                "label": label,
                "points": points,
                "observed_at": points[-1]["date"] if points else None,
                "status": "available" if points else "unavailable",
                "source_type": "etf_proxy" if ticker == "1306.T" else "direct_index",
                **frame.attrs.get("fetch_metadata", {}),
                "url": frame.attrs.get("fetch_metadata", {}).get("source"),
            }
        )
    return (
        {
            "analysis": analysis,
            "profile": "standard",
            "options_request": "not_requested",
        },
        theme,
        {"series": series},
    )


def standard_sections(
    markets: tuple[str, ...],
    *,
    progress=lambda _: None,
    market_inputs: dict | None = None,
) -> dict:
    from src.economic_data_provider import fetch_fred_series

    if not markets or any(m not in {"US", "JP"} for m in markets):
        raise ValueError("Unsupported markets")
    from src.research.topdown import sector_tickers

    tickers = {"SPY", "QQQ", "RSP", "IWM", "JPY=X", "CL=F", "^VIX"}
    for market in markets:
        tickers.update(sector_tickers(market).values())
        for basket in get_theme_measurement_baskets(market).values():
            tickers.update(basket["all_tickers"])
        tickers.update(t for t, _ in INDICES[market])
    started = perf_counter()
    progress("標準：共通の価格・金利・公式予定を取得中（予測モデルなし）")
    with ThreadPoolExecutor(max_workers=3) as pool:
        price_job = pool.submit(fetch_prices, list(tickers))
        fred_job = pool.submit(
            fetch_fred_series,
            ("DGS10", "DGS2", "DFII10", "BAMLH0A0HYM2"),
            start="2024-01-01",
            csv_timeout=10,
            use_pandas_datareader_fallback=False,
        )
        official_job = pool.submit(official_inputs)
        frames, fred, official = (
            price_job.result(),
            fred_job.result(),
            official_job.result(),
        )
    if market_inputs is not None:
        from src.research.public_sources import validate_market_inputs

        official["jpx"] = validate_market_inputs(market_inputs)["jpx"]
    sections = {"markets": {}, "themes": {}, "comparisons": {}, "policies": {}}
    for market in markets:
        progress(f"{market}：5つの問い・期間別テーマを計算中")
        packet, theme, comparison = build_packets(market, frames, fred, official)
        (
            sections["markets"][market],
            sections["themes"][market],
            sections["comparisons"][market],
        ) = packet, theme, comparison
        sections["policies"][market] = {
            "status": "research_only",
            "market": market,
            "connected": packet["analysis"]["connected"],
            "input_scope": "same connected market observations; no stock refresh",
        }
    sections["diagnostics"] = {
        "profile": "standard",
        "elapsed_seconds": round(perf_counter() - started, 3),
        "unique_price_series": len(tickers),
        "price_cache_status": {
            t: f.attrs.get("fetch_metadata", {}).get("cache_status")
            for t, f in frames.items()
        },
        "excluded": [
            "legacy four stages",
            "ML",
            "options",
            "FOMO",
            "corporate filings",
        ],
        "network_requested": True,
    }
    return plain(sections)
