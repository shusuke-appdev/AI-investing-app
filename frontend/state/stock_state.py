import asyncio
from collections.abc import Mapping
from typing import Any

import reflex as rx
from pydantic import BaseModel

from src.services.stock_dashboard_service import (
    build_stock_dashboard_context,
    to_plain_value,
)


class SmartItem(BaseModel):
    met: bool = False
    desc: str = ""
    value: str = ""


class SmartCriteria(BaseModel):
    all_met: bool = False
    S: SmartItem = SmartItem()
    M: SmartItem = SmartItem()
    A: SmartItem = SmartItem()
    R: SmartItem = SmartItem()
    T: SmartItem = SmartItem()


def plain_state_value(value: Any) -> Any:
    """Return Reflex mutable proxy values as plain Python containers."""

    if hasattr(value, "__wrapped__"):
        return plain_state_value(value.__wrapped__)
    return to_plain_value(value)


def smart_criteria_from_mapping(value: Mapping[str, Any] | None) -> SmartCriteria:
    """Normalize SMART criteria payloads into the Reflex state model."""

    if not value:
        return SmartCriteria()
    return SmartCriteria(**plain_state_value(value))


class StockState(rx.State):
    """State for the individual stock analysis page."""

    ticker: str = ""
    is_fetching: bool = False
    error_msg: str = ""
    profile_warning: str = ""

    info: dict[str, Any] = {}
    display_name: str = ""
    display_exchange: str = ""
    display_sector: str = ""
    display_market_cap: str = "N/A"
    display_pe_ratio: str = "N/A"
    display_dividend_yield: str = "N/A"
    display_summary: str = "概要情報がありません。"
    chart_data: list[dict[str, Any]] = []
    news: list[dict[str, Any]] = []
    news_source_status: str = ""
    news_error_reason: str = ""
    technical_data: dict[str, Any] = {}
    smart_criteria: SmartCriteria = SmartCriteria()
    earnings: list[dict[str, Any]] = []
    financials: list[dict[str, Any]] = []
    ai_analysis: str = ""
    is_generating_analysis: bool = False
    probabilistic_signal: dict[str, Any] = {}
    trend_follow_diagnostics: dict[str, Any] = {}
    sector_theme_context: dict[str, Any] = {}
    sector_theme_rating: str = ""
    sector_theme_rationale: str = ""
    sector_theme_themes: list[str] = []
    sector_theme_fundamental_score: float = 0.0
    sector_theme_flow_score: float = 0.0
    sector_theme_fundamental_advantage: bool = False
    sector_theme_flow_advantage: bool = False
    stock_signal_context: dict[str, Any] = {}
    data_status: list[dict[str, Any]] = []

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    async def fetch_stock_data(self):
        """Fetch individual stock data without invoking Gemini/AI generation."""

        if not self.ticker:
            self.error_msg = "ティッカーシンボルを入力してください。"
            return

        self.is_fetching = True
        self.error_msg = ""
        self.profile_warning = ""
        yield

        try:
            context = await asyncio.to_thread(
                build_stock_dashboard_context, self.ticker
            )
            self.info = plain_state_value(context.info)
            display_info = plain_state_value(context.display_info)
            self.display_name = display_info.get("name", self.ticker)
            self.display_exchange = display_info.get("exchange", "")
            self.display_sector = display_info.get("sector", "")
            self.display_market_cap = display_info.get("market_cap", "N/A")
            self.display_pe_ratio = display_info.get("pe_ratio", "N/A")
            self.display_dividend_yield = display_info.get("dividend_yield", "N/A")
            self.display_summary = display_info.get("summary", "概要情報がありません。")
            self.chart_data = plain_state_value(context.chart_data)
            self.news = plain_state_value(context.news)
            self.news_source_status = context.news_source_status
            self.news_error_reason = context.news_error_reason
            self.smart_criteria = smart_criteria_from_mapping(context.smart_criteria)
            self.technical_data = plain_state_value(context.technical_data)
            self.probabilistic_signal = plain_state_value(context.probabilistic_signal)
            self.trend_follow_diagnostics = plain_state_value(
                context.trend_follow_diagnostics
            )
            self.sector_theme_context = plain_state_value(context.sector_theme_context)
            self.sector_theme_rating = self.sector_theme_context.get(
                "combined_rating", ""
            )
            self.sector_theme_rationale = self.sector_theme_context.get("rationale", "")
            self.sector_theme_themes = list(self.sector_theme_context.get("themes", []))
            self.sector_theme_fundamental_score = float(
                self.sector_theme_context.get("stock_fundamental_score", 0.0)
            )
            self.sector_theme_flow_score = float(
                self.sector_theme_context.get("stock_flow_score", 0.0)
            )
            self.sector_theme_fundamental_advantage = bool(
                self.sector_theme_context.get("fundamental_advantage", False)
            )
            self.sector_theme_flow_advantage = bool(
                self.sector_theme_context.get("flow_advantage", False)
            )
            self.stock_signal_context = plain_state_value(context.stock_signal_context)
            self.data_status = plain_state_value(context.data_status)
            self.profile_warning = context.profile_warning
            if context.error_message:
                self.error_msg = context.error_message
        except Exception as exc:
            self.error_msg = f"データの取得に失敗しました: {exc}"
            self.profile_warning = ""
            self.info = {}
            self.display_name = ""
            self.display_exchange = ""
            self.display_sector = ""
            self.display_market_cap = "N/A"
            self.display_pe_ratio = "N/A"
            self.display_dividend_yield = "N/A"
            self.display_summary = "概要情報がありません。"
            self.chart_data = []
            self.news = []
            self.news_source_status = ""
            self.news_error_reason = ""
            self.technical_data = {}
            self.probabilistic_signal = {}
            self.trend_follow_diagnostics = {}
            self.sector_theme_context = {}
            self.sector_theme_rating = ""
            self.sector_theme_rationale = ""
            self.sector_theme_themes = []
            self.sector_theme_fundamental_score = 0.0
            self.sector_theme_flow_score = 0.0
            self.sector_theme_fundamental_advantage = False
            self.sector_theme_flow_advantage = False
            self.stock_signal_context = {}
            self.data_status = []
            self.smart_criteria = SmartCriteria()
        finally:
            self.is_fetching = False
            yield

    async def generate_ai_analysis(self):
        """Generate the Gemini-backed stock recap only when explicitly requested."""

        if not self.ticker or not self.info:
            return
        self.is_generating_analysis = True
        yield

        try:
            from src.stock_analyst import generate_stock_analysis_report

            recap = await asyncio.to_thread(
                generate_stock_analysis_report,
                self.ticker,
                plain_state_value(self.info),
                None,
                None,
                self._news_headlines(),
                plain_state_value(self.probabilistic_signal),
                plain_state_value(self.stock_signal_context),
            )

            if recap:
                self.ai_analysis = recap
            else:
                self.error_msg = "分析レポートの生成に失敗しました。"
        except Exception as exc:
            self.error_msg = f"AI分析エラー: {exc}"
        finally:
            self.is_generating_analysis = False
            yield

    def _news_headlines(self) -> list[str]:
        headlines = []
        for item in plain_state_value(self.news):
            if not isinstance(item, dict):
                continue
            title = str(item.get("headline") or item.get("title") or "").strip()
            if title:
                headlines.append(title)
        return headlines[:5]
