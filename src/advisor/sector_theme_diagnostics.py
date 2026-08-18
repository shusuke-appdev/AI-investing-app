"""Sector/theme diagnostics for fundamental-vs-flow imbalance detection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any

import pandas as pd

from src.market_data import get_stock_data, get_stock_info
from src.services.batched_history_provider import fetch_batched_history
from src.services.trend_ranking_service import find_theme_rankings
from src.theme_taxonomy import get_theme_profile
from src.themes_config import get_themes

THEME_TICKER_LIMIT = 5
MIN_METRICS_PER_STOCK = 2
MIN_THEME_TICKERS = 2
MIN_THEME_COVERAGE = 0.40


@dataclass
class ThemeDiagnostic:
    """One theme's fundamental and flow evaluation."""

    theme: str
    tickers: list[str] = field(default_factory=list)
    fundamental_score: float | None = None
    flow_score: float | None = None
    distortion_score: float | None = None
    fundamental_coverage: float = 0.0
    flow_coverage: float = 0.0
    classification: str = "neutral"
    rating: str = "neutral"
    rationale: str = ""
    fundamental_evidence: list[str] = field(default_factory=list)
    flow_evidence: list[str] = field(default_factory=list)
    quality_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_market_distortions(
    market_type: str = "US",
    *,
    max_themes: int = 30,
    top_n: int = 5,
) -> dict[str, Any]:
    """Return bullish and bearish theme distortions.

    Bullish distortions are fundamentally attractive themes whose flow is still
    weak. Bearish distortions are themes where price/flow strength is materially
    ahead of fundamentals.
    """

    diagnostics = evaluate_theme_diagnostics(market_type, max_themes=max_themes)
    bullish = [
        item
        for item in diagnostics
        if item.classification == "bullish_distortion"
        and item.distortion_score is not None
        and item.distortion_score > 0
    ]
    bearish = [
        item
        for item in diagnostics
        if item.classification == "bearish_distortion"
        and item.distortion_score is not None
        and item.distortion_score < 0
    ]
    bullish.sort(key=lambda item: item.distortion_score, reverse=True)
    bearish.sort(key=lambda item: item.distortion_score)

    return {
        "bullish": [item.to_dict() for item in bullish[:top_n]],
        "bearish": [item.to_dict() for item in bearish[:top_n]],
        "all": [item.to_dict() for item in diagnostics],
        "quality_warnings": _unique(
            warning for item in diagnostics for warning in item.quality_warnings
        )[:10],
    }


def evaluate_theme_diagnostics(
    market_type: str = "US",
    *,
    max_themes: int | None = None,
) -> list[ThemeDiagnostic]:
    """Evaluate configured themes with a lightweight fundamental/flow framework."""

    themes = list(get_themes(market_type).items())
    if max_themes is not None:
        themes = themes[:max_themes]

    benchmark = "SPY" if market_type == "US" else "1306.T"
    requested = [
        benchmark,
        *(
            ticker
            for _theme, tickers in themes
            for ticker in tickers[:THEME_TICKER_LIMIT]
        ),
    ]
    batch = fetch_batched_history(requested, period="6mo", timeout=20)
    history_frames = dict(batch.data or {}) if batch.is_available else {}
    benchmark_returns = _return_profile(history_frames.get(benchmark, pd.DataFrame()))
    diagnostics: list[ThemeDiagnostic] = []

    for theme, tickers in themes:
        selected = tickers[:THEME_TICKER_LIMIT]
        fundamentals = []
        flows = []
        warnings = list(batch.warnings)
        for ticker in selected:
            try:
                value = _fundamental_score(
                    get_stock_info(ticker, include_summary=False)
                )
                if value is not None:
                    fundamentals.append(value)
            except Exception as exc:
                warnings.append(f"{ticker} fundamental data failed: {exc}")
            try:
                value = _flow_score(
                    history_frames.get(ticker, pd.DataFrame()), benchmark_returns
                )
                if value is not None:
                    flows.append(value)
            except Exception as exc:
                warnings.append(f"{ticker} flow data failed: {exc}")

        fundamental_score = _theme_average(fundamentals, len(selected))
        flow_score = _theme_average(flows, len(selected))
        distortion_score = _difference(fundamental_score, flow_score)
        classification = _classification(fundamental_score, flow_score)
        if fundamental_score is None:
            warnings.append("ファンダメンタルの有効データが不足しています。")
        if flow_score is None:
            warnings.append("資金フローの有効データが不足しています。")
        diagnostics.append(
            ThemeDiagnostic(
                theme=theme,
                tickers=selected,
                fundamental_score=fundamental_score,
                flow_score=flow_score,
                distortion_score=distortion_score,
                fundamental_coverage=_coverage(fundamentals, selected),
                flow_coverage=_coverage(flows, selected),
                classification=classification,
                rating=_rating(fundamental_score, flow_score),
                rationale=_rationale(classification, fundamental_score, flow_score),
                fundamental_evidence=_fundamental_evidence(fundamental_score),
                flow_evidence=_flow_evidence(flow_score),
                quality_warnings=warnings,
            )
        )

    diagnostics.sort(
        key=lambda item: (
            abs(item.distortion_score) if item.distortion_score is not None else -1
        ),
        reverse=True,
    )
    return diagnostics


def evaluate_stock_sector_theme_context(
    ticker: str,
    stock_info: dict[str, Any],
    *,
    market_type: str = "US",
    stock_price_df: pd.DataFrame | None = None,
    benchmark_price_df: pd.DataFrame | None = None,
    history_provider: Callable[[str, str], pd.DataFrame] | None = None,
    info_provider: Callable[..., dict[str, Any]] | None = None,
    include_market_ranking: bool = False,
    include_theme_options: bool = False,
    theme_options_cache_only: bool = True,
    fundamental_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the sector/theme context used by the individual stock page and AI."""

    normalized = ticker.strip().upper()
    stock_history_provider = history_provider or get_stock_data
    info_provider = info_provider or get_stock_info
    themes = [
        theme
        for theme, tickers in get_themes(market_type).items()
        if normalized in {item.upper() for item in tickers}
    ]
    if not themes:
        themes = [str(stock_info.get("sector") or "Unclassified")]

    theme_diagnostics = {
        item.theme: item
        for item in _evaluate_selected_theme_diagnostics(
            market_type,
            themes,
            history_provider=history_provider,
            info_provider=info_provider,
            benchmark_price_df=benchmark_price_df,
        )
    }
    adaptive_score = (fundamental_profile or {}).get("score")
    stock_fundamental = (
        float(adaptive_score) / 100 if adaptive_score is not None else None
    )
    if fundamental_profile is None:
        stock_fundamental = _fundamental_score(stock_info)
    stock_flow = _flow_score(
        _normalize_history(stock_price_df)
        if stock_price_df is not None
        else _safe_history(normalized, "6mo", stock_history_provider),
        _return_profile(
            _normalize_history(benchmark_price_df)
            if benchmark_price_df is not None
            else _safe_history(
                "1306.T" if market_type == "JP" else "SPY",
                "6mo",
                stock_history_provider,
            )
        ),
    )
    fundamentals_are_strong = (
        stock_fundamental is not None and stock_fundamental >= 0.55
    )
    flows_are_strong = stock_flow is not None and stock_flow >= 0.55
    combined_rating = (
        "high"
        if fundamentals_are_strong and flows_are_strong
        else "conditional"
        if fundamentals_are_strong or flows_are_strong
        else "unavailable"
        if stock_fundamental is None or stock_flow is None
        else "weak"
    )
    profile = _primary_theme_profile(market_type, themes)
    ranking_context = (
        _stock_theme_ranking_context(
            market_type,
            themes,
            include_options=include_theme_options,
            option_cache_only=theme_options_cache_only,
        )
        if include_market_ranking
        else {}
    )
    best_ranking = (
        (ranking_context.get("items") or [{}])[0]
        if isinstance(ranking_context, dict)
        else {}
    )

    return {
        "ticker": normalized,
        "sector": str(stock_info.get("sector") or ""),
        "industry": str(stock_info.get("industry") or ""),
        "themes": themes,
        "parent_sector": profile.parent_sector,
        "proxy_ticker": profile.proxy_ticker,
        "option_proxy_ticker": best_ranking.get("option_proxy_ticker")
        or profile.option_proxy_ticker,
        "representative_tickers": list(profile.representative_tickers),
        "stock_fundamental_score": _round_optional(stock_fundamental),
        "stock_flow_score": _round_optional(stock_flow),
        "stock_fundamental_score_display": _score_display(stock_fundamental),
        "fundamental_profile_status": (fundamental_profile or {}).get(
            "status", "legacy_proxy"
        ),
        "stock_flow_score_display": _score_display(stock_flow),
        "fundamental_advantage": fundamentals_are_strong,
        "flow_advantage": flows_are_strong,
        "combined_rating": combined_rating,
        "theme_diagnostics": [
            theme_diagnostics[theme].to_dict()
            for theme in themes
            if theme in theme_diagnostics
        ],
        "trend_ranking": ranking_context,
        "best_theme_rank": ranking_context.get("best_rank")
        if isinstance(ranking_context, dict)
        else None,
        "best_theme_rank_points": (
            ranking_context.get("best_rank_points")
            if isinstance(ranking_context, dict)
            and ranking_context.get("best_rank") is not None
            else None
        ),
        "ranking_summary": ranking_context.get("summary", "")
        if isinstance(ranking_context, dict)
        else "",
        "theme_option_signal": best_ranking.get("option_asymmetry", "unavailable"),
        "theme_option_score": best_ranking.get("option_score"),
        "theme_option_summary": best_ranking.get("option_summary", ""),
        "theme_option_source": best_ranking.get("option_source", ""),
        "theme_option_data_as_of": best_ranking.get("option_data_as_of", ""),
        "theme_option_data_quality": best_ranking.get("option_data_quality", ""),
        "theme_option_complete_status": best_ranking.get("option_complete_status", ""),
        "theme_option_provider_active": bool(
            best_ranking.get("option_provider_active", False)
        ),
        "theme_option_fallback_reason": best_ranking.get("option_fallback_reason", ""),
        "theme_option_gamma_coverage": best_ranking.get("option_gamma_coverage"),
        "rationale": _stock_context_rationale(
            combined_rating,
            fundamentals_are_strong,
            flows_are_strong,
        ),
    }


def _evaluate_selected_theme_diagnostics(
    market_type: str,
    selected_themes: list[str],
    *,
    history_provider: Callable[[str, str], pd.DataFrame] | None = None,
    info_provider: Callable[..., dict[str, Any]] | None = None,
    benchmark_price_df: pd.DataFrame | None = None,
) -> list[ThemeDiagnostic]:
    info_provider = info_provider or get_stock_info
    theme_map = get_themes(market_type)
    diagnostics = []
    benchmark = "SPY" if market_type == "US" else "1306.T"
    selected_tickers = [
        ticker
        for theme in selected_themes
        for ticker in theme_map.get(theme, [])[:THEME_TICKER_LIMIT]
    ]
    batch = (
        fetch_batched_history([benchmark, *selected_tickers], period="6mo", timeout=20)
        if history_provider is None
        else None
    )
    history_frames = dict(batch.data or {}) if batch and batch.is_available else {}
    benchmark_returns = _return_profile(
        _normalize_history(benchmark_price_df)
        if benchmark_price_df is not None
        else history_frames.get(benchmark, pd.DataFrame())
        if history_provider is None
        else _safe_history(benchmark, "6mo", history_provider)
    )
    for theme in selected_themes:
        tickers = theme_map.get(theme, [])[:THEME_TICKER_LIMIT]
        if not tickers:
            continue
        fundamentals = []
        flows = []
        warnings = list(batch.warnings) if batch else []
        for ticker in tickers:
            try:
                value = _fundamental_score(info_provider(ticker, include_summary=False))
                if value is not None:
                    fundamentals.append(value)
            except Exception as exc:
                warnings.append(f"{ticker} fundamental data failed: {exc}")
            try:
                value = _flow_score(
                    history_frames.get(ticker, pd.DataFrame())
                    if history_provider is None
                    else _safe_history(ticker, "6mo", history_provider),
                    benchmark_returns,
                )
                if value is not None:
                    flows.append(value)
            except Exception as exc:
                warnings.append(f"{ticker} flow data failed: {exc}")
        fundamental_score = _theme_average(fundamentals, len(tickers))
        flow_score = _theme_average(flows, len(tickers))
        classification = _classification(fundamental_score, flow_score)
        diagnostics.append(
            ThemeDiagnostic(
                theme=theme,
                tickers=tickers,
                fundamental_score=fundamental_score,
                flow_score=flow_score,
                distortion_score=_difference(fundamental_score, flow_score),
                fundamental_coverage=_coverage(fundamentals, tickers),
                flow_coverage=_coverage(flows, tickers),
                classification=classification,
                rating=_rating(fundamental_score, flow_score),
                rationale=_rationale(classification, fundamental_score, flow_score),
                fundamental_evidence=_fundamental_evidence(fundamental_score),
                flow_evidence=_flow_evidence(flow_score),
                quality_warnings=warnings,
            )
        )
    return diagnostics


def _primary_theme_profile(market_type: str, themes: list[str]):
    theme = themes[0] if themes else ""
    tickers = get_themes(market_type).get(theme, [])
    return get_theme_profile(theme, market_type, tickers=tickers)


def _stock_theme_ranking_context(
    market_type: str,
    themes: list[str],
    *,
    include_options: bool,
    option_cache_only: bool,
) -> dict[str, Any]:
    try:
        return find_theme_rankings(
            market_type,
            themes,
            include_options=include_options and market_type == "US",
            option_cache_only=option_cache_only,
        )
    except Exception as exc:
        return {
            "items": [],
            "best_rank": None,
            "best_rank_points": None,
            "summary": f"統合トレンドランキングは取得できません: {exc}",
            "quality_warnings": [str(exc)],
        }


def _fundamental_score(info: dict[str, Any]) -> float | None:
    values = [
        _growth_score(info.get("revenueGrowth")),
        _growth_score(info.get("earningsGrowth")),
        _margin_score(info.get("operatingMargins")),
        _margin_score(info.get("returnOnEquity")),
        _valuation_score(
            info.get("forward_pe"), info.get("pe_ratio"), info.get("pegRatio")
        ),
    ]
    usable = [value for value in values if value is not None]
    return float(mean(usable)) if len(usable) >= MIN_METRICS_PER_STOCK else None


def _flow_score(
    frame: pd.DataFrame, benchmark_returns: dict[str, float]
) -> float | None:
    returns = _return_profile(frame)
    if not returns:
        return None
    scores = []
    for key in ("1m", "3m", "6m"):
        if key in returns:
            benchmark = benchmark_returns.get(key)
            if benchmark is not None:
                relative = returns[key] - benchmark
                scores.append(_bounded((relative + 0.15) / 0.30))
    close = (
        frame["Close"].dropna() if "Close" in frame.columns else pd.Series(dtype=float)
    )
    if len(close) >= 50:
        scores.append(
            0.7 if close.iloc[-1] >= close.rolling(50).mean().iloc[-1] else 0.3
        )
    if len(close) >= 200:
        scores.append(
            0.75 if close.iloc[-1] >= close.rolling(200).mean().iloc[-1] else 0.25
        )
    return float(mean(scores)) if len(scores) >= 2 else None


def _safe_history(
    ticker: str,
    period: str,
    history_provider: Callable[[str, str], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    history_provider = history_provider or get_stock_data
    frame = history_provider(ticker, period)
    return _normalize_history(frame)


def _normalize_history(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized.rename(columns={"close": "Close"}, inplace=True)
    return normalized


def _return_profile(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty or "Close" not in frame.columns:
        return {}
    close = frame["Close"].dropna()
    if len(close) < 2:
        return {}
    windows = {"1m": 21, "3m": 63, "6m": 126}
    result = {}
    for key, window in windows.items():
        if len(close) > window and close.iloc[-window] != 0:
            result[key] = float(
                (close.iloc[-1] - close.iloc[-window]) / close.iloc[-window]
            )
    return result


def _growth_score(value: Any) -> float | None:
    number = _as_float(value)
    if number is None:
        return None
    return _bounded((number + 10.0) / 50.0)


def _margin_score(value: Any) -> float | None:
    number = _as_float(value)
    if number is None:
        return None
    return _bounded(number / 40.0)


def _valuation_score(forward_pe: Any, trailing_pe: Any, peg: Any) -> float | None:
    forward = _as_float(forward_pe)
    trailing = _as_float(trailing_pe)
    peg_value = _as_float(peg)
    scores = []
    if forward is not None and forward > 0:
        scores.append(_bounded((60.0 - forward) / 60.0))
    if forward is not None and trailing is not None and forward > 0 and trailing > 0:
        scores.append(0.65 if forward < trailing else 0.4)
    if peg_value is not None and peg_value > 0:
        scores.append(_bounded((3.0 - peg_value) / 3.0))
    return float(mean(scores)) if scores else None


def _classification(fundamental_score: float | None, flow_score: float | None) -> str:
    if fundamental_score is None or flow_score is None:
        return "unavailable"
    gap = fundamental_score - flow_score
    if fundamental_score >= 0.55 and gap >= 0.2:
        return "bullish_distortion"
    if flow_score >= 0.6 and gap <= -0.2:
        return "bearish_distortion"
    if fundamental_score >= 0.55 and flow_score >= 0.55:
        return "fundamental_and_flow_aligned"
    return "neutral"


def _rating(fundamental_score: float | None, flow_score: float | None) -> str:
    if fundamental_score is None or flow_score is None:
        return "unavailable"
    if fundamental_score >= 0.55 and flow_score >= 0.55:
        return "high"
    if fundamental_score >= 0.55 or flow_score >= 0.55:
        return "conditional"
    return "weak"


def _rationale(
    classification: str, fundamental_score: float | None, flow_score: float | None
) -> str:
    if fundamental_score is None or flow_score is None:
        return "有効データが不足しているため、歪み判定は算出不可です。"
    label = {
        "bullish_distortion": "強気歪み",
        "bearish_distortion": "弱気歪み",
        "fundamental_and_flow_aligned": "ファンダメンタルとフローが整合",
        "neutral": "中立",
    }.get(classification, classification)
    return f"{label}: ファンダメンタル={fundamental_score:.2f}, フロー={flow_score:.2f}"


def _fundamental_evidence(score: float | None) -> list[str]:
    if score is None:
        return ["有効なファンダメンタル指標が不足しています。"]
    if score >= 0.7:
        return ["成長・収益性・バリュエーションの複合スコアが強い。"]
    if score >= 0.55:
        return ["ファンダメンタルは平均以上。フロー確認で高評価に昇格。"]
    return ["ファンダメンタル優位は未確認。"]


def _flow_evidence(score: float | None) -> list[str]:
    if score is None:
        return ["有効な価格・ベンチマークデータが不足しています。"]
    if score >= 0.7:
        return ["相対強度と移動平均の位置が強い。"]
    if score >= 0.55:
        return ["資金フローは改善傾向。"]
    return ["資金フローは弱い、または未確認。"]


def _stock_context_rationale(
    rating: str,
    fundamental_advantage: bool,
    flow_advantage: bool,
) -> str:
    if rating == "high":
        return "ファンダメンタル優位とフロー優位が同時に存在するため、銘柄分析の基礎評価は高い。"
    if fundamental_advantage:
        return "ファンダメンタル優位はあるが、フロー確認が不十分。買いは需給改善待ち。"
    if flow_advantage:
        return "フロー優位はあるが、ファンダメンタル裏付けが弱い。過熱やナラティブ先行を疑う。"
    if rating == "unavailable":
        return "有効データが不足しているため、セクター/テーマ評価は算出不可。"
    return "ファンダメンタル優位・フロー優位とも未確認。個別材料だけで強気判断しない。"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _theme_average(values: list[float], total: int) -> float | None:
    if total <= 0 or len(values) < MIN_THEME_TICKERS:
        return None
    if len(values) / total < MIN_THEME_COVERAGE:
        return None
    return round(mean(values), 3)


def _coverage(values: list[float], selected: list[str]) -> float:
    return round(len(values) / len(selected), 2) if selected else 0.0


def _difference(left: float | None, right: float | None) -> float | None:
    return round(left - right, 3) if left is not None and right is not None else None


def _round_optional(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _score_display(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "算出不可"


def _unique(values) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
