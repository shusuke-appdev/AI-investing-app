"""Stock dashboard use-case orchestration for Reflex state."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pydantic import BaseModel

from src.advisor.fomo_volatility_regime import analyze_fomo_volatility_regime
from src.advisor.probabilistic_signal import (
    generate_probabilistic_stock_signal,
    signal_to_dict,
)
from src.advisor.sector_theme_diagnostics import evaluate_stock_sector_theme_context
from src.advisor.smart_criteria import evaluate_smart_criteria
from src.advisor.technical import analyze_technical
from src.advisor.trade_setup import evaluate_trade_setup, trade_setup_to_dict
from src.advisor.trend_follow_diagnostics import (
    generate_trend_follow_diagnostics,
    trend_follow_to_dict,
)
from src.display_labels import TECHNICAL_LABELS, display_label
from src.market_data import get_stock_data, get_stock_info, get_stock_news_with_status
from src.services.analysis_context import DataResult, ProvenanceItem, StockSignalContext
from src.services.fundamental_profile_service import evaluate_fundamental_profile
from src.services.provenance_service import stock_provenance
from src.services.purchase_evidence_service import evaluate_purchase_evidence
from src.services.stock_analysis_inputs import StockAnalysisInputs
from src.services.volume_profile_service import build_volume_profile


@dataclass
class StockDashboardContext:
    """Prepared individual-stock dashboard payload."""

    info: dict[str, Any] = field(default_factory=dict)
    display_info: dict[str, str] = field(default_factory=dict)
    chart_data: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    news_source_status: str = ""
    news_error_reason: str = ""
    technical_data: dict[str, Any] = field(default_factory=dict)
    smart_criteria: dict[str, Any] = field(default_factory=dict)
    probabilistic_signal: dict[str, Any] = field(default_factory=dict)
    trend_follow_diagnostics: dict[str, Any] = field(default_factory=dict)
    fomo_regime: dict[str, Any] = field(default_factory=dict)
    trade_setup: dict[str, Any] = field(default_factory=dict)
    sector_theme_context: dict[str, Any] = field(default_factory=dict)
    fundamental_profile: dict[str, Any] = field(default_factory=dict)
    volume_profile: dict[str, Any] = field(default_factory=dict)
    purchase_evidence: dict[str, Any] = field(default_factory=dict)
    stock_signal_context: dict[str, Any] = field(default_factory=dict)
    data_status: list[DataResult] = field(default_factory=list)
    provenance: list[ProvenanceItem] = field(default_factory=list)
    profile_warning: str = ""
    quality_warnings: list[str] = field(default_factory=list)
    error_message: str = ""


def build_stock_dashboard_context(
    ticker: str,
    inputs: StockAnalysisInputs | None = None,
) -> StockDashboardContext:
    """Fetch and prepare all non-AI stock dashboard data."""

    normalized_ticker = ticker.strip().upper()
    inputs = inputs or StockAnalysisInputs(
        normalized_ticker,
        history_provider=get_stock_data,
        info_provider=get_stock_info,
        news_provider=get_stock_news_with_status,
    )
    benchmark = inputs.benchmark
    diagnostic_errors: dict[str, str] = {}
    info_data = _safe_analysis(
        "stock_profile",
        lambda: inputs.info(normalized_ticker),
        {},
        diagnostic_errors,
    )
    long_history_df = _safe_analysis(
        "long_price_history",
        lambda: inputs.history(normalized_ticker, "5y"),
        pd.DataFrame(),
        diagnostic_errors,
    )
    history_df = _safe_analysis(
        "price_history",
        lambda: inputs.history(normalized_ticker, "1y"),
        long_history_df,
        diagnostic_errors,
    )
    long_benchmark_df = _safe_analysis(
        "long_benchmark_history",
        lambda: inputs.history(benchmark, "5y"),
        pd.DataFrame(),
        diagnostic_errors,
    )
    benchmark_df = _safe_analysis(
        "benchmark_history",
        lambda: inputs.history(benchmark, "1y"),
        long_benchmark_df,
        diagnostic_errors,
    )
    news_result = _safe_analysis(
        "news",
        lambda: inputs.news(normalized_ticker, 5),
        {"items": [], "source_status": "failed", "error_reason": "News unavailable."},
        diagnostic_errors,
    )
    tech_data = _safe_analysis(
        "technical_analysis",
        lambda: analyze_technical(normalized_ticker, "1y", history_df),
        {},
        diagnostic_errors,
    )

    info_dict = to_plain_value(info_data) if info_data else {}
    technical_dict = _technical_to_dict(tech_data)
    smart_res = _safe_analysis(
        "smart_criteria",
        lambda: evaluate_smart_criteria(
            normalized_ticker,
            dict(info_dict) if info_dict else {},
            "Unknown",
        ),
        {},
        diagnostic_errors,
    )

    probabilistic_dict = _safe_analysis(
        "probabilistic_signal",
        lambda: to_plain_value(
            signal_to_dict(
                generate_probabilistic_stock_signal(
                    normalized_ticker,
                    "5y",
                    benchmark,
                    info_dict,
                    technical_dict,
                    long_history_df,
                    long_benchmark_df,
                )
            )
        ),
        {},
        diagnostic_errors,
    )
    trend_follow_dict = _safe_analysis(
        "trend_follow_diagnostics",
        lambda: to_plain_value(
            trend_follow_to_dict(
                generate_trend_follow_diagnostics(
                    normalized_ticker,
                    "5y",
                    benchmark,
                    long_history_df,
                )
            )
        ),
        {},
        diagnostic_errors,
    )
    fomo_regime = _safe_analysis(
        "fomo_regime",
        lambda: to_plain_value(
            analyze_fomo_volatility_regime(history_df, ticker=normalized_ticker)
        ),
        {},
        diagnostic_errors,
    )
    trade_setup_dict = _safe_analysis(
        "trade_setup",
        lambda: to_plain_value(
            trade_setup_to_dict(
                evaluate_trade_setup(
                    normalized_ticker,
                    info_dict,
                    technical_dict,
                    history_df,
                    benchmark_df,
                    inputs.history,
                )
            )
        ),
        {},
        diagnostic_errors,
    )
    fundamental_profile = _safe_analysis(
        "fundamental_profile",
        lambda: evaluate_fundamental_profile(
            normalized_ticker,
            info_dict,
            market_type="JP" if normalized_ticker.endswith(".T") else "US",
        ),
        {},
        diagnostic_errors,
    )
    if fundamental_profile.get("smart_applicability") != "growth_proxy":
        smart_res = to_plain_value(smart_res)
        smart_res["all_met"] = False
        smart_res["overall_status"] = "unknown"
        for key in ("S", "M", "A", "R", "T"):
            item = smart_res.get(key)
            if not isinstance(item, dict):
                continue
            item["met"] = False
            item["status"] = "unknown"
            item["desc"] = "適用外（SMARTはグロース分類向けproxy）: " + str(
                item.get("desc") or key
            )
    volume_profile = _safe_analysis(
        "volume_profile",
        lambda: build_volume_profile(
            history_df,
            current_price=info_dict.get("current_price"),
        ),
        {},
        diagnostic_errors,
    )
    sector_theme_context = _safe_analysis(
        "sector_theme_context",
        lambda: to_plain_value(
            evaluate_stock_sector_theme_context(
                normalized_ticker,
                info_dict,
                market_type="JP" if normalized_ticker.endswith(".T") else "US",
                stock_price_df=history_df,
                benchmark_price_df=benchmark_df,
                history_provider=inputs.history,
                info_provider=inputs.info,
                include_market_ranking=True,
                include_theme_options=not normalized_ticker.endswith(".T"),
                fundamental_profile=fundamental_profile,
            )
        ),
        {},
        diagnostic_errors,
    )
    purchase_evidence = _safe_analysis(
        "purchase_evidence",
        lambda: evaluate_purchase_evidence(
            technical=technical_dict,
            trade_setup=trade_setup_dict,
            fundamental_profile=fundamental_profile,
            sector_theme=sector_theme_context,
            probabilistic_signal=probabilistic_dict,
            fomo_regime=fomo_regime,
        ),
        {},
        diagnostic_errors,
    )
    news_items = news_result.get("items", []) if isinstance(news_result, dict) else []
    news_source_status = (
        str(news_result.get("source_status", ""))
        if isinstance(news_result, dict)
        else ""
    )
    news_error_reason = (
        str(news_result.get("error_reason", ""))
        if isinstance(news_result, dict)
        else ""
    )

    data_status = _build_data_status(
        info_dict,
        history_df,
        news_source_status,
        news_error_reason,
        bool(technical_dict),
        bool(probabilistic_dict),
        trend_follow_dict,
        trade_setup_dict,
        sector_theme_context,
    )
    _apply_diagnostic_errors(data_status, diagnostic_errors)
    provenance = stock_provenance(
        ticker=normalized_ticker,
        has_profile=bool(info_dict) and not _is_limited_profile(info_dict),
        has_history=history_df is not None and not history_df.empty,
        has_technical=bool(technical_dict),
        probabilistic=probabilistic_dict,
        trend_follow=trend_follow_dict,
        trade_setup=trade_setup_dict,
        sector_theme=sector_theme_context,
        fundamental_profile=fundamental_profile,
        volume_profile=volume_profile,
        purchase_evidence=purchase_evidence,
        news_status=news_source_status,
    )
    stock_signal_context = StockSignalContext(
        ticker=normalized_ticker,
        stock_info=info_dict,
        technical_data=technical_dict,
        smart_criteria=to_plain_value(smart_res),
        probabilistic_signal=probabilistic_dict,
        trend_follow_diagnostics=trend_follow_dict,
        fomo_regime=fomo_regime,
        trade_setup=trade_setup_dict,
        sector_theme_context=sector_theme_context,
        news_headlines=_news_headlines(news_items),
        news_source_status=news_source_status,
        news_error_reason=news_error_reason,
        fundamental_profile=fundamental_profile,
        volume_profile=volume_profile,
        purchase_evidence=purchase_evidence,
        data_status=data_status,
        provenance=provenance,
    ).to_dict()

    chart_data = _history_to_chart_data(history_df)
    return StockDashboardContext(
        info=info_dict,
        display_info=_build_display_info(normalized_ticker, info_dict),
        chart_data=chart_data,
        news=[_normalize_news_item(dict(item)) for item in news_items],
        news_source_status=news_source_status,
        news_error_reason=news_error_reason,
        technical_data=technical_dict,
        smart_criteria=to_plain_value(smart_res),
        probabilistic_signal=probabilistic_dict,
        trend_follow_diagnostics=trend_follow_dict,
        fomo_regime=fomo_regime,
        trade_setup=trade_setup_dict,
        sector_theme_context=sector_theme_context,
        stock_signal_context=stock_signal_context,
        data_status=data_status,
        provenance=provenance,
        fundamental_profile=fundamental_profile,
        volume_profile=volume_profile,
        purchase_evidence=purchase_evidence,
        profile_warning=_profile_warning_message(info_dict),
        quality_warnings=list(diagnostic_errors.values()),
        error_message=_dashboard_error_message(info_dict, history_df),
    )


def to_plain_value(value: Any) -> Any:
    """Convert dataclasses, pydantic models, and containers to plain values."""

    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {str(key): to_plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_value(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain_value(item) for item in value]
    return value


def _safe_analysis(
    name: str,
    callback,
    fallback: Any,
    errors: dict[str, str],
) -> Any:
    try:
        return callback()
    except Exception as exc:
        errors[name] = f"{name} failed: {exc}"
        return fallback


def _apply_diagnostic_errors(
    statuses: list[DataResult], errors: dict[str, str]
) -> None:
    by_name = {item.name: item for item in statuses}
    for name, error in errors.items():
        status = by_name.get(name)
        if status is None:
            statuses.append(
                DataResult(
                    name=name,
                    source="local_calculation",
                    is_partial=True,
                    error=error,
                    cache_status="failed",
                )
            )
            continue
        status.is_partial = True
        status.error = error
        status.cache_status = "failed"


def _technical_to_dict(tech_data: Any) -> dict[str, Any]:
    if not tech_data:
        return {}
    tech_dict = to_plain_value(tech_data)
    if not isinstance(tech_dict, dict):
        return {}
    tech_dict["overall_signal_display"] = display_label(
        str(tech_dict.get("overall_signal", "")), TECHNICAL_LABELS
    )
    for key in ("contrarian_buy_zone", "price_range"):
        if key in tech_dict and isinstance(tech_dict[key], tuple):
            tech_dict[key] = list(tech_dict[key])
    return tech_dict


def _history_to_chart_data(history_df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if history_df is None or history_df.empty:
        return []

    history_view = history_df.copy()
    history_view["MA10"] = history_view["Close"].rolling(10).mean()
    history_view["MA20"] = history_view["Close"].rolling(20).mean()
    history_view["MA50"] = history_view["Close"].rolling(50).mean()
    history_view["MA200"] = history_view["Close"].rolling(200).mean()

    chart_list = []
    for date, row in history_view.iterrows():
        chart_list.append(
            {
                "name": date.strftime("%Y-%m-%d"),
                "price": float(row["Close"]),
                "volume": float(row["Volume"])
                if "Volume" in history_view.columns
                else 0.0,
                "ma10": _optional_float(row["MA10"]),
                "ma20": _optional_float(row["MA20"]),
                "ma50": _optional_float(row["MA50"]),
                "ma200": _optional_float(row["MA200"]),
            }
        )
    return chart_list


def _optional_float(value: Any) -> float | None:
    return float(value) if not pd.isna(value) else None


def _normalize_news_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("headline") or "")
    link = str(item.get("link") or item.get("url") or "")
    return {
        "title": title,
        "headline": title,
        "publisher": str(item.get("publisher") or item.get("source") or ""),
        "source": str(item.get("source") or item.get("publisher") or ""),
        "link": link,
        "url": link,
        "published": str(item.get("published") or ""),
        "summary": str(item.get("summary") or ""),
    }


def _news_headlines(items: list[Any]) -> list[str]:
    headlines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("headline") or "").strip()
        if title:
            headlines.append(title)
    return headlines[:5]


def _build_display_info(ticker: str, info: dict[str, Any]) -> dict[str, str]:
    name = _display_text(info.get("name"), ticker)
    if name == "N/A":
        name = ticker
    return {
        "name": name,
        "exchange": _display_text(info.get("exchange")),
        "sector": _display_text(info.get("sector")),
        "market_cap": _format_market_cap(info.get("market_cap")),
        "pe_ratio": _format_number(info.get("pe_ratio"), decimals=2),
        "dividend_yield": _format_percent(info.get("dividend_yield")),
        "summary": _display_summary(info.get("summary")),
    }


def _display_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return default
    return text


def _display_summary(value: Any) -> str:
    text = _display_text(value)
    if not text or text == "N/A":
        return "概要情報がありません。"
    return text


def _format_market_cap(value: Any) -> str:
    number = _coerce_float(value)
    if number is None:
        return "N/A"
    if abs(number) >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.2f}T"
    if abs(number) >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if abs(number) >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    return f"${number:,.0f}"


def _format_number(value: Any, *, decimals: int = 2) -> str:
    number = _coerce_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.{decimals}f}"


def _format_percent(value: Any) -> str:
    number = _coerce_float(value)
    if number is None:
        return "N/A"
    return f"{number:.2f}%"


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _build_data_status(
    info: dict[str, Any],
    history_df: pd.DataFrame | None,
    news_source_status: str,
    news_error_reason: str,
    has_technical: bool,
    has_probabilistic: bool,
    trend_follow: dict[str, Any],
    trade_setup: dict[str, Any],
    sector_theme_context: dict[str, Any],
) -> list[DataResult]:
    trend_quality = (
        trend_follow.get("data_quality") if isinstance(trend_follow, dict) else {}
    ) or {}
    trend_warnings = (
        trend_follow.get("warnings") if isinstance(trend_follow, dict) else []
    ) or []
    trend_ok = trend_quality.get("status") == "ok"
    return [
        DataResult(
            name="stock_profile",
            source="market_data",
            is_partial=not bool(info) or _is_limited_profile(info),
            error=_profile_warning_message(info),
            cache_status="live",
        ),
        DataResult(
            name="price_history",
            source="market_data",
            is_partial=history_df is None or history_df.empty,
            error="Price history unavailable."
            if history_df is None or history_df.empty
            else "",
            cache_status="live",
        ),
        DataResult(
            name="news",
            source=news_source_status,
            is_partial=bool(news_error_reason),
            error=news_error_reason,
            cache_status="live" if news_source_status == "available" else "failed",
        ),
        DataResult(
            name="technical_analysis",
            source="local_calculation",
            is_partial=not has_technical,
            error="" if has_technical else "Technical analysis unavailable.",
            cache_status="computed",
        ),
        DataResult(
            name="probabilistic_signal",
            source="local_calculation",
            is_partial=not has_probabilistic,
            error="" if has_probabilistic else "Probabilistic signal unavailable.",
            cache_status="computed",
        ),
        DataResult(
            name="trend_follow_diagnostics",
            source="local_calculation",
            is_partial=not trend_ok,
            error="; ".join(str(item) for item in trend_warnings[:3])
            if not trend_ok
            else "",
            cache_status="computed",
        ),
        DataResult(
            name="trade_setup",
            source="local_daily_entry_framework",
            is_partial=trade_setup.get("status") == "insufficient_data",
            error="; ".join(str(item) for item in trade_setup.get("warnings", [])[:3])
            if trade_setup.get("status") == "insufficient_data"
            else "",
            cache_status="computed",
        ),
        DataResult(
            name="sector_theme_context",
            source="sector_theme_diagnostics",
            is_partial=not bool(sector_theme_context),
            error="" if sector_theme_context else "Sector/theme context unavailable.",
            cache_status="computed",
        ),
    ]


def _is_limited_profile(info: dict[str, Any]) -> bool:
    if not info:
        return True
    ticker = _display_text(info.get("ticker"))
    name = _display_text(info.get("name"))
    has_named_profile = bool(name and name != ticker and name != "N/A")
    has_business_text = any(
        _display_text(info.get(key)) not in {"", "N/A"}
        for key in ("summary", "sector", "industry")
    )
    return not (has_named_profile or has_business_text)


def _profile_warning_message(info: dict[str, Any]) -> str:
    if _is_limited_profile(info):
        return "企業概要の一部を取得できませんでした。価格・テクニカル分析は取得済みデータで表示しています。"
    return ""


def _dashboard_error_message(
    info: dict[str, Any],
    history_df: pd.DataFrame | None,
) -> str:
    has_history = history_df is not None and not history_df.empty
    if not info and not has_history:
        return "銘柄データを取得できませんでした。ティッカーとデータプロバイダー設定を確認してください。"
    return ""
