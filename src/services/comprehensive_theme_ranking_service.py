"""Comprehensive theme ranking from price, relative strength, and volume evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, TypedDict

import numpy as np
import pandas as pd
import yfinance as yf

from src.advisor.price_action_metrics import normalize_price_frame, period_returns
from src.log_config import get_logger
from src.persistent_cache import PersistentCacheRead, repo_state_cache
from src.provider_result import FetchResult
from src.theme_measurement import (
    ThemeMeasurementBasket,
    get_theme_measurement_baskets,
    measurement_universe,
)
from src.yfinance_runtime import configure_yfinance_cache

logger = get_logger(__name__)
configure_yfinance_cache()

BENCHMARKS = {"US": "SPY", "JP": "1306.T"}
MIN_COVERAGE = 0.60
CACHE_FRESH_SECONDS = 12 * 60 * 60
CACHE_STALE_SECONDS = 3 * 24 * 60 * 60
_CACHE = repo_state_cache("comprehensive_theme_rankings")


class ComprehensiveThemeRankingRow(TypedDict, total=False):
    """One comparable theme-ranking row."""

    rank: int
    theme: str
    market: str
    total_score: float
    momentum_score: float
    relative_strength_score: float
    attention_score: float
    breadth_score: float
    performance_1w: float
    performance_1m: float
    performance_6m: float
    market_relative_20d: float
    market_relative_63d: float
    dollar_volume_ratio: float
    obv_trend: float
    up_volume_pressure: float
    participation_20d: float
    participation_63d: float
    above_50d: float
    rank_1w: int
    rank_1m: int
    rank_6m: int
    rank_acceleration: int
    coverage_1w: float
    coverage_1m: float
    coverage_6m: float
    component_count: int
    total_components: int
    representative_tickers: list[str]
    stocks: list[dict[str, Any]]
    proxy_ticker: str
    proxy_confirmation: str
    parent_sector: str
    option_proxy_ticker: str
    data_quality: str


class ComprehensiveThemeRankingContext(TypedDict, total=False):
    """Serializable comprehensive ranking plus quality state."""

    market: str
    benchmark: str
    status: str
    items: list[ComprehensiveThemeRankingRow]
    excluded_reasons: dict[str, int]
    quality_warnings: list[str]
    fetched_at: str
    source: str
    is_stale: bool
    universe_count: int


def get_comprehensive_theme_ranking_result(
    market_type: str = "US",
) -> FetchResult[ComprehensiveThemeRankingContext]:
    """Return restart-persistent comprehensive rankings for one market."""

    market = market_type.upper()
    if market not in BENCHMARKS:
        return FetchResult(
            data=_empty_context(market, status="unavailable"),
            source="comprehensive_theme_ranking",
            status="unavailable",
            error_code="unsupported_market",
        )

    cached = _CACHE.read(
        market,
        fresh_seconds=CACHE_FRESH_SECONDS,
        stale_seconds=CACHE_STALE_SECONDS,
    )
    if cached.status == "fresh":
        return _result_from_cache(cached, stale=False)

    live = _build_live_ranking(market)
    if live.is_available and live.data.get("items"):
        _CACHE.write(market, {"context": live.data}, fetched_at=live.fetched_at)
        return live
    if cached.status == "stale":
        stale = _result_from_cache(cached, stale=True)
        stale.warnings = list(
            dict.fromkeys(
                [
                    *stale.warnings,
                    *live.warnings,
                    "最新取得に失敗したため前回順位を表示しています。",
                ]
            )
        )
        stale.data["quality_warnings"] = stale.warnings
        return stale
    return live


def _build_live_ranking(
    market_type: str,
) -> FetchResult[ComprehensiveThemeRankingContext]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    baskets = get_theme_measurement_baskets(market_type)
    benchmark = BENCHMARKS[market_type]
    tickers = measurement_universe(market_type)
    request_tickers = [*tickers]
    if benchmark not in request_tickers:
        request_tickers.append(benchmark)
    try:
        raw = yf.download(
            request_tickers,
            period="2y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=20,
        )
    except Exception as exc:
        logger.exception("Comprehensive theme OHLCV batch failed")
        return FetchResult(
            data=_empty_context(
                market_type,
                status="unavailable",
                fetched_at=fetched_at,
                warnings=["テーマ総合順位の日足を取得できませんでした。"],
            ),
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            error_code="provider_error",
            error=str(exc),
            warnings=["テーマ総合順位の日足を取得できませんでした。"],
        )
    if raw is None or raw.empty:
        return FetchResult(
            data=_empty_context(
                market_type,
                status="unavailable",
                fetched_at=fetched_at,
                warnings=["テーマ総合順位の日足応答が空でした。"],
            ),
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            error_code="empty_response",
            warnings=["テーマ総合順位の日足応答が空でした。"],
        )

    frames = {
        ticker: frame
        for ticker in request_tickers
        if not (frame := _extract_ticker_frame(raw, ticker, request_tickers)).empty
    }
    benchmark_frame = frames.pop(benchmark, pd.DataFrame())
    context = build_comprehensive_theme_ranking(
        market_type=market_type,
        price_frames=frames,
        benchmark_frame=benchmark_frame,
        baskets=baskets,
        fetched_at=fetched_at,
    )
    context["source"] = "yfinance_batch"
    status = str(context.get("status") or "unavailable")
    return FetchResult(
        data=context,
        source="yfinance_batch",
        fetched_at=fetched_at,
        status=status if status in {"available", "partial"} else "unavailable",
        is_partial=status == "partial",
        warnings=context.get("quality_warnings", []),
        error_code="" if context.get("items") else "insufficient_coverage",
    )


def build_comprehensive_theme_ranking(
    *,
    market_type: str,
    price_frames: dict[str, pd.DataFrame],
    benchmark_frame: pd.DataFrame,
    baskets: dict[str, ThemeMeasurementBasket] | None = None,
    fetched_at: str = "",
) -> ComprehensiveThemeRankingContext:
    """Build rankings deterministically from supplied OHLCV frames."""

    market = market_type.upper()
    benchmark = normalize_price_frame(benchmark_frame)
    if len(benchmark) < 127:
        return _empty_context(
            market,
            status="unavailable",
            fetched_at=fetched_at,
            warnings=["市場ベンチマークの履歴が不足しています。"],
        )
    benchmark_returns = period_returns(
        benchmark["Close"].astype(float), periods=(20, 63)
    )
    if any(key not in benchmark_returns for key in ("20d", "63d")):
        return _empty_context(
            market,
            status="unavailable",
            fetched_at=fetched_at,
            warnings=["市場相対強度を算出できません。"],
        )

    rows: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    basket_map = baskets or get_theme_measurement_baskets(market)
    from src.theme_taxonomy import get_theme_profile

    for theme, basket in basket_map.items():
        members = basket["measurement_tickers"]
        metrics = []
        stocks = []
        for ticker in members:
            frame = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
            payload = _ticker_metrics(frame)
            if payload is None:
                continue
            metrics.append(payload)
            stocks.append(
                {
                    "ticker": ticker,
                    "performance": round(payload["return_20d"], 2),
                }
            )
        minimum = min(3, len(members))
        coverage = len(metrics) / max(len(members), 1)
        if len(metrics) < minimum or coverage < MIN_COVERAGE:
            exclusions["代表銘柄の取得率不足"] += 1
            continue
        raw = _theme_metrics(metrics, benchmark_returns)
        if raw is None:
            exclusions["必須価格・出来高不足"] += 1
            continue
        profile = get_theme_profile(theme, market, tickers=members)
        proxy_confirmation = _proxy_confirmation(
            price_frames.get(basket["proxy_ticker"], pd.DataFrame()),
            benchmark_returns,
        )
        rows.append(
            {
                "theme": theme,
                "market": market,
                **raw,
                "coverage_1w": coverage,
                "coverage_1m": coverage,
                "coverage_6m": coverage,
                "component_count": len(metrics),
                "total_components": len(members),
                "representative_tickers": list(members),
                "stocks": sorted(
                    stocks, key=lambda item: item["performance"], reverse=True
                ),
                "proxy_ticker": basket["proxy_ticker"],
                "proxy_confirmation": proxy_confirmation,
                "parent_sector": profile.parent_sector,
                "option_proxy_ticker": profile.option_proxy_ticker,
                "data_quality": "available" if coverage == 1 else "partial",
            }
        )

    if not rows:
        return _empty_context(
            market,
            status="unavailable",
            fetched_at=fetched_at,
            exclusions=dict(exclusions),
            warnings=["総合順位の必須分類を満たすテーマがありません。"],
        )

    _assign_period_ranks(rows)
    _assign_scores(rows)
    rows.sort(key=lambda item: (-float(item["total_score"]), str(item["theme"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        row["rank_points"] = (
            10 if rank <= 3 else 6 if rank <= 10 else 3 if rank <= 20 else 0
        )
        row["flow_score"] = round(float(row["attention_score"]) * 8 - 100, 1)
        row["participation"] = row["participation_20d"]
        row["base_score"] = row["total_score"]
        row["current_score"] = row["total_score"]
        row["one_week_score"] = row["momentum_score"]
        row["one_month_score"] = round(
            float(row["momentum_score"]) + float(row["relative_strength_score"]),
            1,
        )

    warnings = []
    if exclusions:
        warnings.append(
            "取得不足で順位対象外: "
            + "、".join(f"{reason} {count}件" for reason, count in exclusions.items())
        )
    partial = any(row["data_quality"] == "partial" for row in rows)
    return {
        "market": market,
        "benchmark": BENCHMARKS.get(market, ""),
        "status": "partial" if partial else "available",
        "items": rows,
        "excluded_reasons": dict(exclusions),
        "quality_warnings": warnings,
        "fetched_at": fetched_at,
        "source": "supplied_frames",
        "is_stale": False,
        "universe_count": len(price_frames),
    }


def _ticker_metrics(frame: pd.DataFrame) -> dict[str, float] | None:
    if len(frame) < 127 or "Volume" not in frame.columns:
        return None
    close = frame["Close"].astype(float)
    volume = frame["Volume"].astype(float)
    if close.tail(127).isna().any() or volume.tail(63).isna().any():
        return None
    returns = period_returns(close, periods=(5, 20, 21, 63, 126))
    required = ("5d", "20d", "21d", "63d", "126d")
    if any(key not in returns for key in required):
        return None
    dollar_volume = close * volume
    current_turnover = float(dollar_volume.tail(20).mean())
    previous_turnover = float(dollar_volume.iloc[-60:-20].mean())
    if previous_turnover <= 0:
        return None
    signed = np.sign(close.diff().fillna(0.0)) * volume
    obv = signed.cumsum()
    avg_volume = float(volume.tail(20).mean())
    if avg_volume <= 0:
        return None
    obv_trend = float((obv.iloc[-1] - obv.iloc[-21]) / (avg_volume * 20))
    changes = close.diff().tail(20)
    recent_volume = volume.tail(20)
    up = float(recent_volume[changes > 0].sum())
    down = float(recent_volume[changes < 0].sum())
    pressure = up / (up + down) if up + down > 0 else None
    ma50 = float(close.tail(50).mean())
    if pressure is None or not np.isfinite(obv_trend):
        return None
    return {
        "return_5d": returns["5d"],
        "return_20d": returns["20d"],
        "return_21d": returns["21d"],
        "return_63d": returns["63d"],
        "return_126d": returns["126d"],
        "dollar_volume_ratio": current_turnover / previous_turnover,
        "obv_trend": obv_trend,
        "up_volume_pressure": pressure,
        "above_50d": 1.0 if float(close.iloc[-1]) > ma50 else 0.0,
    }


def _theme_metrics(
    metrics: list[dict[str, float]], benchmark_returns: dict[str, float]
) -> dict[str, float] | None:
    def median(key: str) -> float:
        return float(pd.Series([item[key] for item in metrics]).median())

    values = {
        "performance_1w": median("return_5d"),
        "performance_1m": median("return_21d"),
        "performance_6m": median("return_126d"),
        "market_relative_20d": median("return_20d") - benchmark_returns["20d"],
        "market_relative_63d": median("return_63d") - benchmark_returns["63d"],
        "dollar_volume_ratio": median("dollar_volume_ratio"),
        "obv_trend": median("obv_trend"),
        "up_volume_pressure": median("up_volume_pressure"),
        "participation_20d": sum(item["return_20d"] > 0 for item in metrics)
        / len(metrics),
        "participation_63d": sum(item["return_63d"] > 0 for item in metrics)
        / len(metrics),
        "above_50d": sum(item["above_50d"] > 0 for item in metrics) / len(metrics),
    }
    return values if all(np.isfinite(value) for value in values.values()) else None


def _assign_period_ranks(rows: list[dict[str, Any]]) -> None:
    fields = {
        "performance_1w": "rank_1w",
        "performance_1m": "rank_1m",
        "performance_6m": "rank_6m",
    }
    for field, rank_field in fields.items():
        ordered = sorted(
            rows, key=lambda item: (-float(item[field]), str(item["theme"]))
        )
        for rank, row in enumerate(ordered, start=1):
            row[rank_field] = rank
    for row in rows:
        row["rank_acceleration"] = int(row["rank_6m"]) - int(row["rank_1w"])


def _assign_scores(rows: list[dict[str, Any]]) -> None:
    weights = {
        "performance_1w": ("momentum_score", 8.0),
        "performance_1m": ("momentum_score", 12.0),
        "performance_6m": ("momentum_score", 10.0),
        "market_relative_20d": ("relative_strength_score", 10.0),
        "market_relative_63d": ("relative_strength_score", 15.0),
        "dollar_volume_ratio": ("attention_score", 10.0),
        "obv_trend": ("attention_score", 8.0),
        "up_volume_pressure": ("attention_score", 7.0),
        "participation_20d": ("breadth_score", 5.0),
        "participation_63d": ("breadth_score", 5.0),
        "above_50d": ("breadth_score", 5.0),
        "rank_acceleration": ("breadth_score", 5.0),
    }
    for row in rows:
        row.update(
            momentum_score=0.0,
            relative_strength_score=0.0,
            attention_score=0.0,
            breadth_score=0.0,
        )
    for field, (bucket, weight) in weights.items():
        values = pd.Series([float(row[field]) for row in rows])
        percentiles = values.rank(method="average", pct=True)
        for row, percentile in zip(rows, percentiles, strict=True):
            row[bucket] += float(percentile) * weight
    for row in rows:
        for bucket in (
            "momentum_score",
            "relative_strength_score",
            "attention_score",
            "breadth_score",
        ):
            row[bucket] = round(float(row[bucket]), 1)
        row["total_score"] = round(
            sum(
                float(row[bucket])
                for bucket in (
                    "momentum_score",
                    "relative_strength_score",
                    "attention_score",
                    "breadth_score",
                )
            ),
            1,
        )


def _proxy_confirmation(
    frame: pd.DataFrame, benchmark_returns: dict[str, float]
) -> str:
    normalized = normalize_price_frame(frame)
    metrics = _ticker_metrics(normalized)
    if metrics is None:
        return "判定不能"
    relative = metrics["return_20d"] - benchmark_returns["20d"]
    if relative > 0 and metrics["dollar_volume_ratio"] >= 1.0:
        return "確認あり"
    return "不一致"


def _extract_ticker_frame(
    raw: pd.DataFrame, ticker: str, request_tickers: list[str]
) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy() if len(request_tickers) == 1 else pd.DataFrame()
    first = raw.columns.get_level_values(0)
    second = raw.columns.get_level_values(1)
    if ticker in first:
        return raw[ticker].dropna(how="all")
    if ticker in second:
        return raw.xs(ticker, axis=1, level=1).dropna(how="all")
    return pd.DataFrame()


def _result_from_cache(
    cached: PersistentCacheRead, *, stale: bool
) -> FetchResult[ComprehensiveThemeRankingContext]:
    context = dict(cached.payload.get("context") or {})
    context["is_stale"] = stale
    if stale:
        context["status"] = "partial"
    return FetchResult(
        data=context,  # type: ignore[arg-type]
        source=str(context.get("source") or "comprehensive_theme_ranking_cache"),
        fetched_at=cached.fetched_at,
        status="partial" if stale else str(context.get("status") or "available"),
        is_stale=stale,
        is_partial=stale or str(context.get("status")) == "partial",
        warnings=list(context.get("quality_warnings") or []),
    )


def _empty_context(
    market_type: str,
    *,
    status: str,
    fetched_at: str = "",
    warnings: list[str] | None = None,
    exclusions: dict[str, int] | None = None,
) -> ComprehensiveThemeRankingContext:
    return {
        "market": market_type,
        "benchmark": BENCHMARKS.get(market_type, ""),
        "status": status,
        "items": [],
        "excluded_reasons": exclusions or {},
        "quality_warnings": warnings or [],
        "fetched_at": fetched_at,
        "source": "comprehensive_theme_ranking",
        "is_stale": status == "stale",
        "universe_count": 0,
    }
