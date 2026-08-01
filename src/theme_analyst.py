"""
テーマ別分析モジュール
テーマごとの騰落率計算とランキング生成を行います。
"""

from datetime import datetime, timedelta, timezone
from typing import TypedDict

import pandas as pd
import yfinance as yf

from src.cache import ttl_cache
from src.log_config import get_logger
from src.persistent_cache import repo_state_cache
from src.provider_result import FetchResult
from src.themes_config import PERIODS, THEMES, get_themes
from src.yfinance_runtime import configure_yfinance_cache

logger = get_logger(__name__)
configure_yfinance_cache()
MIN_THEME_COMPONENTS = 2
MIN_THEME_COVERAGE = 0.4
THEME_CACHE_FRESH_SECONDS = 12 * 60 * 60
THEME_CACHE_STALE_SECONDS = 3 * 24 * 60 * 60
_THEME_RANKING_CACHE = repo_state_cache("theme_rankings")


class ThemeObservation(TypedDict):
    performance: float
    requested_days: int
    actual_days: int


class ThemeStockPerformance(ThemeObservation):
    ticker: str


class RankedTheme(TypedDict):
    theme: str
    performance: float
    stocks: list[ThemeStockPerformance]
    requested_days: int
    component_count: int
    total_components: int
    coverage: float


def fetch_and_calculate_all_performances(
    days: int, market_type: str = "US"
) -> dict[str, float]:
    """
    全テーマの構成銘柄を一括取得して騰落率を計算します。

    Args:
        days: 期間（日数）
        market_type: "US" または "JP"

    Returns:
        {ticker: performance} の辞書
    """
    observations = _fetch_performance_observations(days, market_type)
    return {ticker: float(item["performance"]) for ticker, item in observations.items()}


def _fetch_performance_observations(
    days: int, market_type: str = "US"
) -> dict[str, ThemeObservation]:
    """Return only performances that cover the full requested calendar window."""

    return _fetch_performance_observations_for_periods((days,), market_type).get(
        days, {}
    )


def _fetch_performance_observations_for_periods(
    days_values: tuple[int, ...],
    market_type: str = "US",
) -> dict[int, dict[str, ThemeObservation]]:
    """Return performance observations for multiple periods from one batch fetch."""

    return _fetch_performance_observations_for_periods_result(
        days_values, market_type
    ).data


def _fetch_performance_observations_for_periods_result(
    days_values: tuple[int, ...],
    market_type: str = "US",
) -> FetchResult[dict[int, dict[str, ThemeObservation]]]:
    """Return status-aware theme observations from one yfinance batch fetch."""

    configure_yfinance_cache()
    themes = get_themes(market_type)
    requested_days = tuple(sorted({int(days) for days in days_values if days > 0}))
    if not requested_days:
        return FetchResult(
            data={},
            source="yfinance_batch",
            status="unavailable",
            error_code="invalid_period",
        )

    # 1. 全銘柄リストの作成
    all_tickers = set()
    for tickers in themes.values():
        all_tickers.update(tickers)

    all_ticker_list = list(all_tickers)
    if not all_ticker_list:
        return FetchResult(
            data={},
            source="theme_taxonomy",
            status="unavailable",
            error_code="empty_universe",
        )

    fetch_period = _fetch_period_for_days(max(requested_days))
    interval = "1d"
    performance_maps: dict[int, dict[str, ThemeObservation]] = {
        days: {} for days in requested_days
    }
    ticker_errors = 0
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        # yfinanceで一括ダウンロード
        df = yf.download(
            all_ticker_list,
            period=fetch_period,
            interval=interval,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=20,
        )

        if df.empty:
            return FetchResult(
                data=performance_maps,
                source="yfinance_batch",
                fetched_at=fetched_at,
                status="unavailable",
                error_code="empty_response",
                warnings=["テーマ構成銘柄の価格履歴を取得できませんでした。"],
            )

        # 1銘柄だけの場合のハンドリング
        if len(all_ticker_list) == 1:
            pass  # 通常はMultiIndexではないが、アクセス方法を統一する必要がある

        for ticker in all_ticker_list:
            try:
                # データ抽出
                if isinstance(df.columns, pd.MultiIndex):
                    if ticker in df.columns.get_level_values(0):
                        stock_df = df[ticker]
                    elif ticker in df.columns.get_level_values(1):
                        stock_df = df.xs(ticker, axis=1, level=1)
                    else:
                        continue
                else:
                    stock_df = df

                if "Close" not in stock_df.columns:
                    continue

                closes = stock_df["Close"].dropna()
                if len(closes) < 2:
                    continue

                # 最新日付と価格
                current_date = closes.index[-1]
                current_price = closes.iloc[-1]

                for days in requested_days:
                    target_date = current_date - timedelta(days=days)
                    past_data = closes[closes.index <= target_date]
                    if past_data.empty:
                        continue
                    start_date = past_data.index[-1]
                    start_price = float(past_data.iloc[-1])
                    if start_price == 0:
                        continue
                    perf = ((float(current_price) - start_price) / start_price) * 100
                    performance_maps[days][ticker] = {
                        "performance": perf,
                        "requested_days": days,
                        "actual_days": max(0, int((current_date - start_date).days)),
                    }

            except Exception:
                ticker_errors += 1
                continue

    except Exception as e:
        logger.exception("Theme batch download failed")
        return FetchResult(
            data=performance_maps,
            source="yfinance_batch",
            fetched_at=fetched_at,
            status="unavailable",
            error_code="provider_error",
            error=str(e),
        )

    warnings = []
    if ticker_errors:
        warnings.append(
            f"{ticker_errors}銘柄は応答形式を確認できず、ランキングから除外しました。"
        )
    return FetchResult(
        data=performance_maps,
        source="yfinance_batch",
        fetched_at=fetched_at,
        status="partial" if ticker_errors else "available",
        is_partial=bool(ticker_errors),
        warnings=warnings,
    )


def _fetch_period_for_days(days: int) -> str:
    if days <= 5:
        return "1mo"
    if days <= 30:
        return "3mo"
    if days <= 90:
        return "6mo"
    if days <= 180:
        return "1y"
    return "2y"


@ttl_cache(ttl=43200)  # 12時間キャッシュ
def get_ranked_themes(period_name: str, market_type: str = "US") -> list[RankedTheme]:
    """
    指定期間での全テーマをパフォーマンス順（降順）で取得します。

    Args:
        period_name: 期間名 ("1日", "1週間", etc.)
        market_type: "US" または "JP"

    Returns:
        全テーマのリスト（パフォーマンス順）
    """
    if period_name not in PERIODS:
        raise ValueError(f"Unknown period: {period_name}")

    days = PERIODS[period_name]
    ticker_performances = _fetch_performance_observations(days, market_type)
    return _rank_themes_from_observations(days, ticker_performances, market_type)


def get_ranked_themes_result(
    period_name: str,
    market_type: str = "US",
) -> FetchResult[list[RankedTheme]]:
    """Return theme rankings with normalized availability and provenance metadata."""

    if period_name not in PERIODS:
        raise ValueError(f"Unknown period: {period_name}")

    cache_key = f"{market_type}:{period_name}"
    cached = _THEME_RANKING_CACHE.read(
        cache_key,
        fresh_seconds=THEME_CACHE_FRESH_SECONDS,
        stale_seconds=THEME_CACHE_STALE_SECONDS,
    )
    if cached.status == "fresh":
        return _theme_result_from_cache(cached.payload, cached, stale=False)

    live = _build_ranked_themes_result(period_name, market_type)
    if live.is_available:
        _THEME_RANKING_CACHE.write(
            cache_key,
            _theme_result_payload(live),
            fetched_at=live.fetched_at or None,
        )
        return live
    if cached.status == "stale" and cached.payload.get("data"):
        stale = _theme_result_from_cache(cached.payload, cached, stale=True)
        stale.warnings = list(
            dict.fromkeys(
                [
                    *stale.warnings,
                    *live.warnings,
                    "最新取得に失敗したため、12時間契約を超えた前回ランキングを表示しています。",
                ]
            )
        )
        stale.error = live.error
        stale.error_code = live.error_code
        return stale
    return live


def _build_ranked_themes_result(
    period_name: str,
    market_type: str,
) -> FetchResult[list[RankedTheme]]:
    days = PERIODS[period_name]
    observations = _fetch_performance_observations_for_periods_result(
        (days,), market_type
    )
    ranking = _rank_themes_from_observations(
        days,
        observations.data.get(days, {}),
        market_type,
    )
    warnings = list(observations.warnings)
    status = observations.status
    error_code = observations.error_code
    if not ranking and status in {"available", "partial"}:
        status = "unavailable"
        error_code = "insufficient_coverage"
        warnings.append("必要な構成銘柄数または取得率を満たすテーマがありません。")

    return FetchResult(
        data=ranking,
        source=observations.source,
        fetched_at=observations.fetched_at,
        is_stale=observations.is_stale,
        is_partial=observations.is_partial,
        cache_status=observations.cache_status,
        cache_age_seconds=observations.cache_age_seconds,
        status=status,
        warnings=warnings,
        error_code=error_code,
        error=observations.error,
    )


def _theme_result_payload(result: FetchResult[list[RankedTheme]]) -> dict:
    return {
        "data": result.data,
        "source": result.source,
        "fetched_at": result.fetched_at,
        "is_partial": result.is_partial,
        "status": result.status,
        "warnings": result.warnings,
        "error_code": result.error_code,
        "error": result.error,
    }


def _theme_result_from_cache(
    payload: dict, cached, *, stale: bool
) -> FetchResult[list[RankedTheme]]:
    data = payload.get("data")
    return FetchResult(
        data=list(data) if isinstance(data, list) else [],
        source=str(payload.get("source") or "theme_rankings"),
        fetched_at=str(payload.get("fetched_at") or cached.fetched_at),
        is_stale=stale,
        is_partial=bool(payload.get("is_partial")) or stale,
        cache_status="stale_cache" if stale else "persistent_cache",
        cache_age_seconds=cached.age_seconds,
        status="partial" if stale else str(payload.get("status") or "available"),
        warnings=list(payload.get("warnings") or []),
        error_code=str(payload.get("error_code") or ""),
        error=str(payload.get("error") or ""),
    )


@ttl_cache(ttl=43200)
def get_ranked_theme_periods(
    period_names: tuple[str, ...],
    market_type: str = "US",
) -> dict[str, list[RankedTheme]]:
    """Return rankings for several periods using one yfinance batch fetch."""

    unknown = [period for period in period_names if period not in PERIODS]
    if unknown:
        raise ValueError(f"Unknown periods: {', '.join(unknown)}")
    days_by_period = {period: PERIODS[period] for period in period_names}
    observations_by_days = _fetch_performance_observations_for_periods(
        tuple(days_by_period.values()), market_type
    )
    return {
        period: _rank_themes_from_observations(
            days,
            observations_by_days.get(days, {}),
            market_type,
        )
        for period, days in days_by_period.items()
    }


def _rank_themes_from_observations(
    days: int,
    ticker_performances: dict[str, ThemeObservation],
    market_type: str,
) -> list[RankedTheme]:

    themes = get_themes(market_type)
    theme_performances: list[RankedTheme] = []

    for theme_name, tickers in themes.items():
        stock_perfs: list[ThemeStockPerformance] = []
        for t in tickers:
            if t in ticker_performances:
                observation = ticker_performances[t]
                stock_perfs.append(
                    {
                        "ticker": t,
                        "performance": observation["performance"],
                        "requested_days": observation["requested_days"],
                        "actual_days": observation["actual_days"],
                    }
                )

        coverage = len(stock_perfs) / len(tickers) if tickers else 0.0
        if len(stock_perfs) >= MIN_THEME_COMPONENTS and coverage >= MIN_THEME_COVERAGE:
            avg_perf = sum(s["performance"] for s in stock_perfs) / len(stock_perfs)
            stock_perfs.sort(key=lambda x: x["performance"], reverse=True)

            theme_performances.append(
                {
                    "theme": theme_name,
                    "performance": avg_perf,
                    "stocks": stock_perfs,
                    "requested_days": days,
                    "component_count": len(stock_perfs),
                    "total_components": len(tickers),
                    "coverage": coverage,
                }
            )

    # パフォーマンス順にソート (降順)
    theme_performances.sort(key=lambda x: x["performance"], reverse=True)

    return theme_performances


def get_top_themes(period_name: str, top_n: int = 10) -> list[RankedTheme]:
    """
    指定期間での上位テーマを取得します（互換性維持）。
    """
    ranked = get_ranked_themes(period_name)
    return ranked[:top_n]


def get_theme_details(theme_name: str, period_name: str = "1ヶ月") -> dict:
    """
    テーマの詳細情報を取得します。
    """
    # 既存互換のため残すが、内部でget_top_themes的なロジックを使うか、
    # 単独ダウンロードする。単独の場合は従来のロジックで良いが、
    # 整合性を取るため再実装してもよい。ここでは簡易的に。
    # 「詳細」機能は現状UIであまり使われていない（Expander内はget_top_themesで返されたデータを使っている）。
    return {}  # 必要なら実装


def get_all_theme_names() -> list[str]:
    """
    定義されている全テーマ名を取得します。

    Returns:
        テーマ名のリスト
    """
    return list(THEMES.keys())
