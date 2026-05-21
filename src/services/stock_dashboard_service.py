"""Stock dashboard use-case orchestration for Reflex state."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pydantic import BaseModel

from src.advisor.probabilistic_signal import (
    generate_probabilistic_stock_signal,
    signal_to_dict,
)
from src.advisor.smart_criteria import evaluate_smart_criteria
from src.advisor.technical import analyze_technical
from src.market_data import get_stock_data, get_stock_info, get_stock_news_with_status
from src.services.analysis_context import DataResult, StockSignalContext


@dataclass
class StockDashboardContext:
    """Prepared individual-stock dashboard payload."""

    info: dict[str, Any] = field(default_factory=dict)
    chart_data: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    news_source_status: str = ""
    news_error_reason: str = ""
    technical_data: dict[str, Any] = field(default_factory=dict)
    smart_criteria: dict[str, Any] = field(default_factory=dict)
    probabilistic_signal: dict[str, Any] = field(default_factory=dict)
    stock_signal_context: dict[str, Any] = field(default_factory=dict)
    data_status: list[DataResult] = field(default_factory=list)
    error_message: str = ""


def build_stock_dashboard_context(ticker: str) -> StockDashboardContext:
    """Fetch and prepare all non-AI stock dashboard data."""

    normalized_ticker = ticker.strip().upper()
    info_data = get_stock_info(normalized_ticker, translate_summary=False)
    history_df = get_stock_data(normalized_ticker, "1y")
    news_result = get_stock_news_with_status(normalized_ticker, 5)
    tech_data = analyze_technical(normalized_ticker, "1y")

    info_dict = to_plain_value(info_data) if info_data else {}
    technical_dict = _technical_to_dict(tech_data)
    smart_res = evaluate_smart_criteria(
        normalized_ticker,
        dict(info_dict) if info_dict else {},
        "Unknown",
    )

    probabilistic = generate_probabilistic_stock_signal(
        normalized_ticker,
        "5y",
        "SPY",
        info_dict,
        technical_dict,
    )
    probabilistic_dict = to_plain_value(signal_to_dict(probabilistic))
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
    )
    stock_signal_context = StockSignalContext(
        ticker=normalized_ticker,
        stock_info=info_dict,
        technical_data=technical_dict,
        probabilistic_signal=probabilistic_dict,
        news_source_status=news_source_status,
        news_error_reason=news_error_reason,
        data_status=data_status,
    ).to_dict()

    return StockDashboardContext(
        info=info_dict,
        chart_data=_history_to_chart_data(history_df),
        news=[_normalize_news_item(dict(item)) for item in news_items],
        news_source_status=news_source_status,
        news_error_reason=news_error_reason,
        technical_data=technical_dict,
        smart_criteria=to_plain_value(smart_res),
        probabilistic_signal=probabilistic_dict,
        stock_signal_context=stock_signal_context,
        data_status=data_status,
        error_message=_profile_error_message(info_dict),
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


def _technical_to_dict(tech_data: Any) -> dict[str, Any]:
    if not tech_data:
        return {}
    tech_dict = to_plain_value(tech_data)
    if not isinstance(tech_dict, dict):
        return {}
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


def _build_data_status(
    info: dict[str, Any],
    history_df: pd.DataFrame | None,
    news_source_status: str,
    news_error_reason: str,
    has_technical: bool,
    has_probabilistic: bool,
) -> list[DataResult]:
    return [
        DataResult(
            name="stock_profile",
            source="market_data",
            is_partial=not bool(info) or _is_missing_profile(info),
            error=_profile_error_message(info),
        ),
        DataResult(
            name="price_history",
            source="market_data",
            is_partial=history_df is None or history_df.empty,
            error="Price history unavailable."
            if history_df is None or history_df.empty
            else "",
        ),
        DataResult(
            name="news",
            source=news_source_status,
            is_partial=bool(news_error_reason),
            error=news_error_reason,
        ),
        DataResult(
            name="technical_analysis",
            source="local_calculation",
            is_partial=not has_technical,
            error="" if has_technical else "Technical analysis unavailable.",
        ),
        DataResult(
            name="probabilistic_signal",
            source="local_calculation",
            is_partial=not has_probabilistic,
            error="" if has_probabilistic else "Probabilistic signal unavailable.",
        ),
    ]


def _is_missing_profile(info: dict[str, Any]) -> bool:
    return info.get("summary") == "N/A" and info.get("sector") == "N/A"


def _profile_error_message(info: dict[str, Any]) -> str:
    if not info or _is_missing_profile(info):
        return "企業情報を取得できませんでした。価格データやプロバイダー設定を確認してください。"
    return ""
