"""Auditable price-only market, sector and screening observations.

History uses the current registered universe, never a point-in-time backtest.
All functions consume the shared price batch; none acquire data or call a model.
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar
from statistics import median

import pandas as pd

from src.advisor.minervini_analyzer import analyze_stage, detect_vcp
from src.theme_measurement import get_theme_measurement_baskets
from src.theme_taxonomy import SECTOR_ETF_PROFILES, get_theme_profile
from src.themes_config import get_ticker_name

PERIODS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
JP_SECTORS = dict(
    zip(
        [
            "食品",
            "エネルギー資源",
            "建設・資材",
            "素材・化学",
            "医薬品",
            "自動車・輸送機",
            "鉄鋼・非鉄",
            "機械",
            "電機・精密",
            "情報通信・サービスその他",
            "電力・ガス",
            "運輸・物流",
            "商社・卸売",
            "小売",
            "銀行",
            "金融（除く銀行）",
            "不動産",
        ],
        [f"{n}.T" for n in range(1617, 1634)],
        strict=True,
    )
)
HISTORY_NOTE = (
    "現在の登録銘柄で再計算。過去当時の構成・判明情報や投資成績の検証ではありません。"
)


_RETURN_CACHE: ContextVar[dict | None] = ContextVar(
    "research_return_cache", default=None
)


def sector_tickers(market: str) -> dict[str, str]:
    return (
        JP_SECTORS
        if market == "JP"
        else {k: v[1] for k, v in SECTOR_ETF_PROFILES.items()}
    )


def num(value):
    import math

    return (
        float(value)
        if not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        else None
    )


def metadata(frame: pd.DataFrame) -> dict:
    return {
        **frame.attrs.get("fetch_metadata", {}),
        "observed_on": frame.index[-1].date().isoformat() if len(frame) else None,
        "integrity": frame.attrs.get("price_integrity", {}),
    }


def valid(frame: pd.DataFrame, benchmark: pd.DataFrame) -> bool:
    from src.research.standard import current_history

    return bool(
        not frame.empty
        and not benchmark.empty
        and current_history(frame)
        and current_history(benchmark)
        and frame.index[-1] == benchmark.index[-1]
    )


def trend(frame: pd.DataFrame) -> dict:
    close = frame.get("Close", pd.Series(dtype=float))
    gaps = {
        str(n): num((close.iloc[-1] / close.tail(n).mean() - 1) * 100)
        if len(close) >= n
        else None
        for n in (20, 50, 200)
    }
    slope = (
        num((close.tail(200).mean() / close.iloc[-220:-20].mean() - 1) * 100)
        if len(close) >= 220
        else None
    )
    gap = gaps["200"]
    label = (
        "判定不能"
        if gap is None or slope is None
        else "境界"
        if gap == 0 or slope == 0
        else "上昇基調"
        if gap > 0 and slope > 0
        else "回復途上"
        if gap > 0
        else "悪化途上"
        if slope > 0
        else "下降基調"
    )
    return {
        "label": label,
        "ma_gaps": gaps,
        "ma200_slope_20d": slope,
        "short_term": "判定不能"
        if gaps["20"] is None
        else "20日線上"
        if gaps["20"] > 0
        else "20日線下"
        if gaps["20"] < 0
        else "20日線上の境界",
        **metadata(frame),
    }


def distribution_days(frame: pd.DataFrame) -> dict:
    """25-session window includes today; recovery cancels the original event."""
    base = {
        "method": "前日比≤−0.2%、出来高増。直近25営業日・発生日から5%回復で失効",
        "source_type": "etf_proxy",
        **metadata(frame),
    }
    if (
        len(frame) < 26
        or "Volume" not in frame
        or frame.Volume.tail(26).isna().any()
        or (frame.Volume.tail(26) <= 0).any()
    ):
        return {
            **base,
            "status": "insufficient_data",
            "count": None,
            "active": [],
            "expired": [],
        }
    active, expired = [], []
    for i in range(1, len(frame)):
        today = frame.iloc[i]
        kept = []
        for event in active:
            reason = (
                "25営業日窓の外"
                if i - event["index"] >= 25
                else "発生日終値から5%回復"
                if today.Close >= event["close"] * 1.05
                else None
            )
            if reason:
                expired.append(
                    {
                        **event,
                        "expired_on": frame.index[i].date().isoformat(),
                        "reason": reason,
                    }
                )
            else:
                kept.append(event)
        active = kept
        previous = frame.iloc[i - 1]
        if (
            previous.Close > 0
            and today.Close / previous.Close - 1 <= -0.002 + 1e-12
            and today.Volume > previous.Volume
        ):
            active.append(
                {
                    "index": i,
                    "date": frame.index[i].date().isoformat(),
                    "close": float(today.Close),
                    "change_pct": float((today.Close / previous.Close - 1) * 100),
                }
            )

    def clean(rows):
        return [{k: v for k, v in r.items() if k != "index"} for r in rows]

    return {
        **base,
        "status": "available",
        "count": len(active),
        "active": clean(active),
        "expired": clean(expired[-25:]),
    }


def volume_signals(frame: pd.DataFrame) -> dict:
    close, volume = (
        frame.get("Close", pd.Series(dtype=float)),
        frame.get("Volume", pd.Series(dtype=float)),
    )
    rvol = (
        num(volume.iloc[-1] / volume.iloc[-51:-1].mean())
        if len(volume) >= 51
        and volume.iloc[-51:].notna().all()
        and (volume.iloc[-51:] > 0).all()
        else None
    )
    pp, dates = None, []
    if (
        len(close) >= 11
        and len(volume) >= 11
        and (volume.iloc[-11:] > 0).all()
        and volume.iloc[-11:].notna().all()
    ):
        # Difference must be calculated BEFORE slicing, so day -10 has its prior close.
        down = volume.iloc[-11:-1][close.diff().iloc[-11:-1] < 0]
        dates = [d.date().isoformat() for d in down.index]
        if len(down):
            pp = bool(
                close.iloc[-1] > close.iloc[-2]
                and close.iloc[-1] > close.tail(10).mean()
                and volume.iloc[-1] > down.max()
            )
    gap = (
        num((close.iloc[-1] / close.tail(50).mean() - 1) * 100)
        if len(close) >= 50
        else None
    )
    return {
        "rvol50": rvol,
        "volume_surge": None if rvol is None else rvol >= 1.5,
        "price_direction": "上昇"
        if len(close) >= 2 and close.iloc[-1] > close.iloc[-2]
        else "下落・同値"
        if len(close) >= 2
        else "未確認",
        "pocket_pivot": pp,
        "comparison_dates": dates,
        "near_ma50": None if gap is None else -1 <= gap <= 6,
        "ma50_gap": gap,
    }


def group_value(
    members: list[str], frames: dict, benchmark: pd.DataFrame, days: int, end=None
) -> tuple:
    bm = benchmark if end is None else benchmark.loc[:end]
    eligible = []
    for ticker in members:
        original = frames.get(ticker, pd.DataFrame())
        if not valid(original, benchmark):
            continue
        cache = _RETURN_CACHE.get()
        if cache is None:
            cache = {}
        key = (id(original), id(benchmark), days)
        if key not in cache:
            prices = pd.Series(
                original["Close"].to_numpy(), index=original.index
            ).reindex(benchmark.index)
            complete = (
                prices.notna().rolling(days + 1, min_periods=days + 1).sum() == days + 1
            )
            absolute = ((prices / prices.shift(days) - 1) * 100).where(complete)
            relative = (
                absolute - (benchmark.Close / benchmark.Close.shift(days) - 1) * 100
            )
            cache[key] = (absolute, relative)
        point = bm.index[-1] if len(bm) else None
        absolute, relative = (num(series.get(point)) for series in cache[key])
        if relative is not None:
            eligible.append((ticker, absolute, relative))
    enough = (
        bool(members)
        and len(eligible) >= min(3, len(members))
        and len(eligible) / len(members) >= 0.6
    )
    return (
        (
            median(v[1] for v in eligible),
            median(v[2] for v in eligible),
            [v[0] for v in eligible],
        )
        if enough
        else (None, None, [v[0] for v in eligible])
    )


def asset_periods(ticker: str, frames: dict, benchmark: pd.DataFrame) -> dict:
    from src.research.standard import current_history, returns

    result = {}
    for period, days in PERIODS.items():
        absolute, relative, _ = group_value([ticker], frames, benchmark, days)
        dates = (
            [
                benchmark.index[-days - 1].date().isoformat(),
                benchmark.index[-1].date().isoformat(),
            ]
            if relative is not None
            else []
        )
        frame = frames.get(ticker, pd.DataFrame())
        if benchmark.empty and current_history(frame):
            absolute, _, dates = returns(frame, frame, days)
        result[period] = {
            "return": absolute,
            "relative_return": relative,
            "dates": dates,
            "calendar": "own sessions; benchmark unavailable"
            if benchmark.empty
            else "benchmark sessions",
        }
    return result


def rotation(members: list[str], frames: dict, benchmark: pd.DataFrame) -> dict:
    if benchmark.empty:
        return {
            "strength": None,
            "acceleration": None,
            "quadrant": "判定不能",
            "trail": [],
        }
    trail = []
    endpoints = list(
        benchmark.groupby(benchmark.index.to_period("W-FRI")).tail(1).index[-12:]
    )
    if benchmark.index[-1] not in endpoints:
        endpoints.append(benchmark.index[-1])
    for day in endpoints:
        bm = benchmark.loc[:day]
        _, strength, a = group_value(members, frames, benchmark, 126, day)
        _, recent, b = group_value(members, frames, benchmark, 21, day)
        prior_day = bm.index[-22] if len(bm) > 21 else None
        _, previous, c = (
            group_value(members, frames, benchmark, 21, prior_day)
            if prior_day is not None
            else (None, None, [])
        )
        acceleration = (
            recent - previous
            if recent is not None and previous is not None and b == c
            else None
        )
        trail.append(
            {
                "date": day.date().isoformat(),
                "strength": strength,
                "acceleration": acceleration,
                "members": a,
                "comparable": b == c,
            }
        )
    last = trail[-1] if trail else {}
    x, y = last.get("strength"), last.get("acceleration")
    quadrant = (
        "判定不能"
        if x is None or y is None
        else "境界"
        if x == 0 or y == 0
        else ("相対優位" if x > 0 else "相対劣後")
        + ("・改善" if y > 0 else "・鈍化" if x > 0 else "・悪化")
    )
    return {
        "strength": x,
        "acceleration": y,
        "quadrant": quadrant,
        "trail": trail,
        "method": "横=126営業日相対値pp、縦=21営業日相対値の21営業日前比pp。公式RRGではありません。",
        "history_note": HISTORY_NOTE,
    }


def breadth(
    members: list[str],
    frames: dict,
    benchmark: pd.DataFrame,
    history_sessions: int = 60,
) -> dict:
    """Align to the benchmark calendar with NaNs, never forward fill gaps."""
    usable = {
        t: f for t in members if valid(f := frames.get(t, pd.DataFrame()), benchmark)
    }
    if benchmark.empty:
        return {
            "history": [],
            "latest": {},
            "registered_count": len(members),
            "history_note": HISTORY_NOTE,
        }
    index = benchmark.index
    close = pd.DataFrame(
        {t: f.Close.reindex(index) for t, f in usable.items()}, index=index
    )
    high = (
        pd.DataFrame(
            {
                t: f.get("High", pd.Series(dtype=float)).reindex(index)
                for t, f in usable.items()
            },
            index=index,
        )
        .rolling(252, min_periods=252)
        .max()
    )
    low = (
        pd.DataFrame(
            {
                t: f.get("Low", pd.Series(dtype=float)).reindex(index)
                for t, f in usable.items()
            },
            index=index,
        )
        .rolling(252, min_periods=252)
        .min()
    )
    averages = {n: close.rolling(n, min_periods=n).mean() for n in (20, 50, 200)}
    changes = close.pct_change(fill_method=None)
    rows = []
    for day in index[-history_sessions:]:
        row = {
            "date": day.date().isoformat(),
            "registered_count": len(members),
            "counts": {},
        }
        price = close.loc[day]
        for name, values, mask in [
            (f"above_{n}", avg.loc[day], price > avg.loc[day])
            for n, avg in averages.items()
        ] + [
            ("near_high", high.loc[day], price >= high.loc[day] * 0.98),
            ("near_low", low.loc[day], price <= low.loc[day] * 1.02),
            ("advancing", changes.loc[day], changes.loc[day] > 0),
            ("declining", changes.loc[day], changes.loc[day] < 0),
        ]:
            eligible = price.notna() & values.notna()
            count, total = int((mask & eligible).sum()), int(eligible.sum())
            enough = (
                bool(members)
                and total >= min(3, len(members))
                and total / len(members) >= 0.6
            )
            row[name] = count / total * 100 if enough else None
            row["counts"][name] = {
                "numerator": count,
                "denominator": total,
                "coverage": total / len(members) * 100 if members else 0,
            }
        rows.append(row)
    return {
        "history": rows,
        "latest": rows[-1] if rows else {},
        "registered_count": len(members),
        "current_count": len(usable),
        "scope": "登録銘柄内・重複除外。全市場の騰落銘柄数ではありません。",
        "history_note": HISTORY_NOTE,
        "universe_version": hashlib.sha256(
            "|".join(sorted(members)).encode()
        ).hexdigest()[:16],
    }


def chart_points(frame: pd.DataFrame, benchmark: pd.DataFrame) -> list:
    if frame.empty:
        return []
    close = frame.Close
    averages = {n: close.rolling(n).mean() for n in (10, 20, 50, 200)}
    ratio = (
        close / benchmark.Close.reindex(frame.index)
        if not benchmark.empty
        else close * float("nan")
    )
    return [
        {
            "name": d.date().isoformat(),
            "price": num(row.Close),
            "volume": num(row.get("Volume")),
            **{f"ma{n}": num(a.loc[d]) for n, a in averages.items()},
            "relative_ratio": num(ratio.loc[d]),
        }
        for d, row in frame.tail(63).iterrows()
    ]


def build_topdown(market: str, frames: dict, ranking: dict) -> dict:
    token = _RETURN_CACHE.set({})
    try:
        return _build_topdown(market, frames, ranking)
    finally:
        _RETURN_CACHE.reset(token)


def _build_topdown(market: str, frames: dict, ranking: dict) -> dict:
    from src.research.standard import INDICES

    baskets = get_theme_measurement_baskets(market)
    members = list(
        dict.fromkeys(t for basket in baskets.values() for t in basket["all_tickers"])
    )
    benchmark = frames.get("SPY" if market == "US" else "1306.T", pd.DataFrame())
    calendar = frames.get(INDICES[market][0][0], pd.DataFrame())
    sector_rows = []
    for name, ticker in sector_tickers(market).items():
        frame = frames.get(ticker, pd.DataFrame())
        periods = asset_periods(ticker, frames, benchmark)
        sector_rows.append(
            {
                "name": name,
                "ticker": ticker,
                "trend": trend(frame),
                "periods": periods,
                "rotation": rotation([ticker], frames, benchmark),
                "volume": volume_signals(frame),
                "source_type": "etf_proxy",
                "status": "available"
                if valid(frame, benchmark)
                else "partial"
                if valid(frame, calendar)
                else "stale"
                if len(frame)
                else "unavailable",
                "reason": "市場相対値の基準系列が不足・不整合"
                if valid(frame, calendar) and not valid(frame, benchmark)
                else "",
            }
        )
    for item in ranking["items"]:
        names = item["measurement_tickers"]
        profile = get_theme_profile(item["theme"], market, tickers=names)
        item["parent_sector"] = profile.parent_sector
        item["rotation"] = rotation(names, frames, benchmark)
        item["breadth"] = breadth(names, frames, calendar, 1)["latest"]
        ratios = [
            v
            for t in names
            if valid(f := frames.get(t, pd.DataFrame()), calendar)
            and (v := volume_signals(f)["rvol50"]) is not None
        ]
        item["rvol50"] = (
            median(ratios)
            if len(ratios) >= min(3, len(names)) and len(ratios) >= len(names) * 0.6
            else None
        )
        # Compare ranks only within an unchanged eligible membership set.
        past = benchmark.index[-6] if len(benchmark) >= 6 else None
        _, old_value, old_members = (
            group_value(names, frames, benchmark, 126, past)
            if past is not None
            else (None, None, [])
        )
        _, _, now_members = group_value(names, frames, benchmark, 126)
        item["prior_relative_6m"] = old_value
        item["rank_comparable"] = bool(old_members) and old_members == now_members
    comparable = [
        r
        for r in ranking["items"]
        if r["rank_comparable"]
        and r.get("relative_6m") is not None
        and r["prior_relative_6m"] is not None
    ]
    old_order = {
        r["theme"]: i + 1
        for i, r in enumerate(sorted(comparable, key=lambda r: -r["prior_relative_6m"]))
    }
    new_order = {
        r["theme"]: i + 1
        for i, r in enumerate(sorted(comparable, key=lambda r: -r["relative_6m"]))
    }
    for item in ranking["items"]:
        item["rank_change_1w"] = (
            old_order[item["theme"]] - new_order[item["theme"]]
            if item["theme"] in old_order
            else None
        )
        item["rank_change_scope"] = "前週と構成・有効銘柄が同じテーマ集合内の順位差"
    sample = breadth(members, frames, calendar)
    sample["calendar_ticker"] = INDICES[market][0][0]
    for day in sample["history"]:
        when = pd.Timestamp(day["date"])
        values = (
            calendar.Close.pct_change(fill_method=None)
            if not calendar.empty
            else pd.Series(dtype=float)
        )
        day["index_return"] = (
            num(values.get(when) * 100) if when in values.index else None
        )
        sector_changes = []
        for name, ticker in sector_tickers(market).items():
            frame = frames.get(ticker, pd.DataFrame())
            if valid(frame, calendar):
                change = frame.Close.pct_change(fill_method=None).get(when)
                if (change := num(change)) is not None:
                    sector_changes.append({"name": name, "change": change * 100})
        day["strong_sectors"] = sorted(sector_changes, key=lambda r: -r["change"])[:3]
    indices = [
        {"ticker": t, "name": name, **trend(frames.get(t, pd.DataFrame()))}
        for t, name in INDICES[market]
    ]
    distributions = [
        {"ticker": t, **distribution_days(frames.get(t, pd.DataFrame()))}
        for t in (["SPY", "QQQ"] if market == "US" else ["1306.T"])
    ]
    screen = []
    etfs = set(sector_tickers(market).values()) | {"SPY", "QQQ", "IWM", "RSP"}
    for ticker in members:
        if ticker in etfs:
            continue
        frame = frames.get(ticker, pd.DataFrame())
        eligible = valid(frame, calendar)
        stage = analyze_stage(frame) if eligible and len(frame) >= 252 else {}
        passed = bool(stage.get("conditions")) and all(
            r.get("status") == "pass" for r in stage["conditions"]
        )
        periods = asset_periods(ticker, frames, benchmark)
        themes = [
            name for name, basket in baskets.items() if ticker in basket["all_tickers"]
        ]
        parents = sorted(
            {get_theme_profile(name, market).parent_sector for name in themes} - {""}
        )
        high = (
            float(frame.High.tail(252).max())
            if eligible and len(frame) >= 252
            else None
        )
        below = (
            float((frame.Close.iloc[-1] / high - 1) * 100)
            if high and high > 0
            else None
        )
        r3, r6 = (periods[p]["relative_return"] for p in ("3m", "6m"))
        signals = volume_signals(frame) if eligible else {}
        vcp = bool(detect_vcp(frame)[0]) if eligible and len(frame) >= 50 else None
        profile = (
            "reit"
            if any("REIT" in name.upper() for name in themes)
            else "financial"
            if any(p in {"金融", "銀行", "保険"} for p in parents)
            else "general"
        )
        screen.append(
            {
                "ticker": ticker,
                "name": get_ticker_name(ticker, market),
                "market": market,
                "themes": themes,
                "sectors": parents,
                "profile": profile,
                "profile_basis": "登録分類による暫定業態。業績取得時の企業分類で再確認",
                "periods": periods,
                "stage2": passed if stage else None,
                "stage_conditions": stage.get("conditions", []),
                "leader": passed
                and r3 is not None
                and r6 is not None
                and r3 > 0
                and r6 > 0,
                "near_high": None if below is None else below >= -5,
                "high_gap": below,
                "vcp": vcp,
                "volume": signals,
                "chart_data": chart_points(frame, benchmark),
                "quote": num(frame.Close.iloc[-1]) if eligible else None,
                "status": "available"
                if eligible
                else "stale"
                if len(frame)
                else "unavailable",
                **metadata(frame),
            }
        )
    screen.sort(
        key=lambda r: (
            r["periods"]["6m"]["relative_return"] is None,
            -(r["periods"]["6m"]["relative_return"] or 0),
        )
    )
    for i, row in enumerate(screen, 1):
        row["relative_rank_6m"] = (
            i if row["periods"]["6m"]["relative_return"] is not None else None
        )
    summary = [
        f"{row['name']}：{row['label']}、{row['short_term']}。" for row in indices
    ]
    latest = sample["latest"]
    if latest.get("above_200") is not None:
        summary.append(
            f"登録銘柄の200日線上は{latest['above_200']:.1f}%。全市場の参加率ではありません。"
        )
    if len({row["label"] for row in indices}) > 1:
        summary.append("主要指数間で中期状態が異なります。")
    return {
        "version": "topdown-v1",
        "market": market,
        "benchmark": "SPY" if market == "US" else "1306.T（TOPIX連動ETF代理）",
        "benchmark_status": "available"
        if valid(benchmark, calendar)
        else "unavailable",
        "benchmark_evidence": metadata(benchmark),
        "indices": indices,
        "sectors": sector_rows,
        "breadth": sample,
        "distributions": distributions,
        "screening": screen,
        "summary": summary,
        "history_note": HISTORY_NOTE,
        "research_only": True,
    }
