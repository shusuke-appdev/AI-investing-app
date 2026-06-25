import asyncio
from collections.abc import Mapping
from typing import Any

import reflex as rx
from pydantic import BaseModel

from frontend.components.data_provenance import (
    DataStatusDisplay,
    ProvenanceDisplay,
    data_status_display_items,
    provenance_display_items,
)
from src.display_labels import SECTOR_RATING_LABELS, display_label
from src.services.stock_dashboard_service import (
    build_stock_dashboard_context,
    to_plain_value,
)


class SmartItem(BaseModel):
    met: bool = False
    status: str = "unknown"
    desc: str = ""
    value: str = ""


class SmartCriteria(BaseModel):
    all_met: bool = False
    overall_status: str = "pending"
    S: SmartItem = SmartItem()
    M: SmartItem = SmartItem()
    A: SmartItem = SmartItem()
    R: SmartItem = SmartItem()
    T: SmartItem = SmartItem()


class FundamentalMetricDisplay(BaseModel):
    axis: str = ""
    metric: str = ""
    actual: str = "-"
    benchmark: str = "-"
    score: str = "算出不可"


class VolumeProfileBinDisplay(BaseModel):
    label: str = ""
    width: str = "0%"
    share: str = ""
    is_poc: bool = False
    in_value_area: bool = False


def _number_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


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
    fomo_regime: dict[str, Any] = {}
    fomo_label: str = ""
    fomo_risk_level: str = ""
    fomo_evidence: list[str] = []
    fomo_confirmation: str = ""
    fomo_invalidation: str = ""
    trade_setup: dict[str, Any] = {}
    sector_theme_context: dict[str, Any] = {}
    sector_theme_rating: str = ""
    sector_theme_rating_display: str = ""
    sector_theme_rationale: str = ""
    sector_theme_themes: list[str] = []
    sector_theme_fundamental_score: float = 0.0
    sector_theme_flow_score: float = 0.0
    sector_theme_fundamental_score_display: str = "算出不可"
    sector_theme_flow_score_display: str = "算出不可"
    sector_theme_fundamental_advantage: bool = False
    sector_theme_flow_advantage: bool = False
    sector_theme_parent_sector: str = ""
    sector_theme_proxy_ticker: str = ""
    sector_theme_option_proxy: str = ""
    sector_theme_best_rank: str = ""
    sector_theme_rank_points: str = ""
    sector_theme_ranking_summary: str = ""
    sector_theme_option_signal: str = ""
    sector_theme_option_score: str = ""
    sector_theme_option_summary: str = ""
    sector_theme_option_source: str = ""
    sector_theme_option_complete_status: str = ""
    sector_theme_option_provider_active: bool = False
    sector_theme_option_fallback_reason: str = ""
    sector_theme_option_gamma_coverage: str = "-"
    fundamental_profile: dict[str, Any] = {}
    fundamental_size_label: str = ""
    fundamental_size_borderline: bool = False
    fundamental_style_label: str = ""
    fundamental_sector_label: str = ""
    fundamental_score_display: str = "算出不可"
    fundamental_coverage_display: str = "0%"
    fundamental_status: str = "unavailable"
    fundamental_summary: str = ""
    fundamental_metrics: list[FundamentalMetricDisplay] = []
    fundamental_missing_reasons: list[str] = []
    fundamental_cap_reasons: list[str] = []
    fundamental_excluded_metrics: list[str] = []
    volume_profile: dict[str, Any] = {}
    volume_profile_summary: str = ""
    volume_profile_bins: list[VolumeProfileBinDisplay] = []
    purchase_evidence: dict[str, Any] = {}
    purchase_evidence_label: str = "算出不可"
    purchase_evidence_score_display: str = "算出不可"
    purchase_evidence_summary: str = ""
    purchase_evidence_cap_reasons: list[str] = []
    purchase_evidence_available: bool = False
    sector_theme_option_data_as_of: str = ""
    sector_theme_option_data_quality: str = ""
    stock_signal_context: dict[str, Any] = {}
    trade_analysis_visible: bool = False
    trade_analysis: dict[str, Any] = {}
    trade_analysis_error: str = ""
    data_status: list[DataStatusDisplay] = []
    provenance: list[ProvenanceDisplay] = []
    data_issue_summary: str = ""

    def prepare_page(self):
        """Normalize transient flags before the stock page renders."""

        self.is_fetching = False
        self.is_generating_analysis = False
        self.error_msg = ""
        self.profile_warning = ""

    def set_ticker(self, value: str):
        self.ticker = value.upper()
        self._reset_trade_analysis()

    def show_trade_analysis(self):
        """Build the trade analysis from the current stock payload on demand."""

        if not self.stock_signal_context:
            self.trade_analysis_error = "先に銘柄データを取得してください。"
            self.trade_analysis_visible = False
            return
        from src.services.stock_trade_analysis_service import (
            build_stock_trade_analysis,
        )

        self.trade_analysis = build_stock_trade_analysis(
            plain_state_value(self.stock_signal_context)
        )
        self.trade_analysis_visible = True
        self.trade_analysis_error = ""

    def hide_trade_analysis(self):
        self.trade_analysis_visible = False

    async def fetch_stock_data(self):
        """Fetch individual stock data without invoking Gemini/AI generation."""

        if not self.ticker:
            self.error_msg = "ティッカーシンボルを入力してください。"
            return

        self.is_fetching = True
        self.error_msg = ""
        self.profile_warning = ""
        self._reset_trade_analysis()
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
            self.fomo_regime = plain_state_value(context.fomo_regime)
            self.fomo_label = str(self.fomo_regime.get("label", ""))
            self.fomo_risk_level = str(self.fomo_regime.get("risk_level", ""))
            self.fomo_evidence = list(self.fomo_regime.get("evidence", []))
            self.fomo_confirmation = str(self.fomo_regime.get("confirmation", ""))
            self.fomo_invalidation = str(self.fomo_regime.get("invalidation", ""))
            self.trade_setup = plain_state_value(context.trade_setup)
            self.sector_theme_context = plain_state_value(context.sector_theme_context)
            self.sector_theme_rating = self.sector_theme_context.get(
                "combined_rating", ""
            )
            self.sector_theme_rating_display = display_label(
                self.sector_theme_rating, SECTOR_RATING_LABELS
            )
            self.sector_theme_rationale = self.sector_theme_context.get("rationale", "")
            self.sector_theme_themes = list(self.sector_theme_context.get("themes", []))
            self.sector_theme_fundamental_score = float(
                self.sector_theme_context.get("stock_fundamental_score") or 0.0
            )
            self.sector_theme_flow_score = float(
                self.sector_theme_context.get("stock_flow_score") or 0.0
            )
            self.sector_theme_fundamental_score_display = str(
                self.sector_theme_context.get(
                    "stock_fundamental_score_display", "算出不可"
                )
            )
            self.sector_theme_flow_score_display = str(
                self.sector_theme_context.get("stock_flow_score_display", "算出不可")
            )
            self.sector_theme_fundamental_advantage = bool(
                self.sector_theme_context.get("fundamental_advantage", False)
            )
            self.sector_theme_flow_advantage = bool(
                self.sector_theme_context.get("flow_advantage", False)
            )
            self.sector_theme_parent_sector = str(
                self.sector_theme_context.get("parent_sector", "")
            )
            self.sector_theme_proxy_ticker = str(
                self.sector_theme_context.get("proxy_ticker", "")
            )
            self.sector_theme_option_proxy = str(
                self.sector_theme_context.get("option_proxy_ticker", "")
            )
            rank = self.sector_theme_context.get("best_theme_rank")
            self.sector_theme_best_rank = "" if rank in (None, "") else str(rank)
            rank_points = self.sector_theme_context.get("best_theme_rank_points")
            self.sector_theme_rank_points = (
                "" if rank_points in (None, "") else str(rank_points)
            )
            self.sector_theme_ranking_summary = str(
                self.sector_theme_context.get("ranking_summary", "")
            )
            self.sector_theme_option_signal = str(
                self.sector_theme_context.get("theme_option_signal", "")
            )
            option_score = self.sector_theme_context.get("theme_option_score")
            self.sector_theme_option_score = (
                "" if option_score is None else f"{float(option_score):+.1f}"
            )
            self.sector_theme_option_summary = str(
                self.sector_theme_context.get("theme_option_summary", "")
            )
            self.sector_theme_option_source = str(
                self.sector_theme_context.get("theme_option_source", "")
            )
            self.sector_theme_option_complete_status = str(
                self.sector_theme_context.get("theme_option_complete_status", "")
            )
            self.sector_theme_option_provider_active = bool(
                self.sector_theme_context.get("theme_option_provider_active", False)
            )
            self.sector_theme_option_fallback_reason = str(
                self.sector_theme_context.get("theme_option_fallback_reason", "")
            )
            gamma_coverage = self.sector_theme_context.get(
                "theme_option_gamma_coverage"
            )
            self.sector_theme_option_gamma_coverage = (
                "-" if gamma_coverage is None else f"{float(gamma_coverage):.0%}"
            )
            self.sector_theme_option_data_as_of = str(
                self.sector_theme_context.get("theme_option_data_as_of", "")
            )
            self.sector_theme_option_data_quality = str(
                self.sector_theme_context.get("theme_option_data_quality", "")
            )
            self.fundamental_profile = plain_state_value(context.fundamental_profile)
            size_profile = self.fundamental_profile.get("size") or {}
            style_profile = self.fundamental_profile.get("style") or {}
            sector_profile = self.fundamental_profile.get("sector_profile") or {}
            self.fundamental_size_label = str(size_profile.get("label") or "分類不能")
            self.fundamental_size_borderline = bool(size_profile.get("borderline"))
            self.fundamental_style_label = str(style_profile.get("label") or "分類不能")
            self.fundamental_sector_label = str(sector_profile.get("label") or "未分類")
            self.fundamental_score_display = str(
                self.fundamental_profile.get("score_display") or "算出不可"
            )
            self.fundamental_coverage_display = str(
                self.fundamental_profile.get("coverage_display") or "0%"
            )
            self.fundamental_status = str(
                self.fundamental_profile.get("status") or "unavailable"
            )
            self.fundamental_summary = str(
                self.fundamental_profile.get("summary") or ""
            )
            self.fundamental_metrics = [
                FundamentalMetricDisplay(
                    axis=str(item.get("axis") or ""),
                    metric=str(item.get("metric") or ""),
                    actual=_number_text(item.get("actual")),
                    benchmark=_number_text(item.get("benchmark")),
                    score=_number_text(item.get("score")),
                )
                for item in self.fundamental_profile.get("metric_details", [])
                if isinstance(item, dict)
            ]
            self.fundamental_missing_reasons = list(
                self.fundamental_profile.get("missing_reasons") or []
            )
            self.fundamental_cap_reasons = list(
                self.fundamental_profile.get("cap_reasons") or []
            )
            self.fundamental_excluded_metrics = list(
                self.fundamental_profile.get("excluded_metrics") or []
            )
            self.volume_profile = plain_state_value(context.volume_profile)
            self.volume_profile_summary = str(self.volume_profile.get("summary") or "")
            self.volume_profile_bins = [
                VolumeProfileBinDisplay(
                    label=f"{float(item.get('low', 0)):.2f}～{float(item.get('high', 0)):.2f}",
                    width=f"{float(item.get('relative_volume', 0)) * 100:.0f}%",
                    share=f"{float(item.get('share', 0)):.1%}",
                    is_poc=bool(item.get("is_poc")),
                    in_value_area=bool(item.get("in_value_area")),
                )
                for item in self.volume_profile.get("bins", [])
                if isinstance(item, dict)
            ]
            self.purchase_evidence = plain_state_value(context.purchase_evidence)
            self.purchase_evidence_label = str(
                self.purchase_evidence.get("label") or "算出不可"
            )
            self.purchase_evidence_score_display = str(
                self.purchase_evidence.get("score_display") or "算出不可"
            )
            self.purchase_evidence_summary = str(
                self.purchase_evidence.get("summary") or ""
            )
            self.purchase_evidence_cap_reasons = list(
                self.purchase_evidence.get("cap_reasons") or []
            )
            self.purchase_evidence_available = (
                self.purchase_evidence.get("status") == "available"
            )
            self.stock_signal_context = plain_state_value(context.stock_signal_context)
            self.data_status = data_status_display_items(context.data_status)
            self.provenance = provenance_display_items(context.provenance)
            self.data_issue_summary = self._data_issue_summary()
            from src.services.provider_health import record_data_results

            record_data_results(context.data_status, scope=f"stock.{self.ticker}")
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
            self.fomo_regime = {}
            self.fomo_label = ""
            self.fomo_risk_level = ""
            self.fomo_evidence = []
            self.fomo_confirmation = ""
            self.fomo_invalidation = ""
            self.trade_setup = {}
            self.sector_theme_context = {}
            self.sector_theme_rating = ""
            self.sector_theme_rating_display = ""
            self.sector_theme_rationale = ""
            self.sector_theme_themes = []
            self.sector_theme_fundamental_score = 0.0
            self.sector_theme_flow_score = 0.0
            self.sector_theme_fundamental_score_display = "算出不可"
            self.sector_theme_flow_score_display = "算出不可"
            self.sector_theme_fundamental_advantage = False
            self.sector_theme_flow_advantage = False
            self.sector_theme_parent_sector = ""
            self.sector_theme_proxy_ticker = ""
            self.sector_theme_option_proxy = ""
            self.sector_theme_best_rank = ""
            self.sector_theme_rank_points = ""
            self.sector_theme_ranking_summary = ""
            self.sector_theme_option_signal = ""
            self.sector_theme_option_score = ""
            self.sector_theme_option_summary = ""
            self.fundamental_profile = {}
            self.fundamental_size_label = ""
            self.fundamental_size_borderline = False
            self.fundamental_style_label = ""
            self.fundamental_sector_label = ""
            self.fundamental_score_display = "算出不可"
            self.fundamental_coverage_display = "0%"
            self.fundamental_status = "unavailable"
            self.fundamental_summary = ""
            self.fundamental_metrics = []
            self.fundamental_missing_reasons = []
            self.fundamental_cap_reasons = []
            self.fundamental_excluded_metrics = []
            self.volume_profile = {}
            self.volume_profile_summary = ""
            self.volume_profile_bins = []
            self.purchase_evidence = {}
            self.purchase_evidence_label = "算出不可"
            self.purchase_evidence_score_display = "算出不可"
            self.purchase_evidence_summary = ""
            self.purchase_evidence_cap_reasons = []
            self.purchase_evidence_available = False
            self.sector_theme_option_source = ""
            self.sector_theme_option_complete_status = ""
            self.sector_theme_option_provider_active = False
            self.sector_theme_option_fallback_reason = ""
            self.sector_theme_option_gamma_coverage = "-"
            self.sector_theme_option_data_as_of = ""
            self.sector_theme_option_data_quality = ""
            self.stock_signal_context = {}
            self._reset_trade_analysis()
            self.data_status = []
            self.provenance = []
            self.data_issue_summary = ""
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

    def _reset_trade_analysis(self) -> None:
        self.trade_analysis_visible = False
        self.trade_analysis = {}
        self.trade_analysis_error = ""

    def _data_issue_summary(self) -> str:
        issues = [
            f"{item.name}: {item.error or item.status_label}"
            for item in self.data_status
            if item.status_key in {"partial", "failed", "stale"}
        ]
        if not issues:
            return "主要データは取得済みです。"
        return " / ".join(issues[:4])
