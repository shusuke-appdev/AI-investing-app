import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

from frontend.components.data_provenance import (
    DataStatusDisplay,
    ProvenanceDisplay,
    data_status_display_items,
    provenance_display_items,
)
from src.services.market_analyst_service import generate_market_analysis_report
from src.services.market_dashboard_service import (
    build_fomo_scan_context,
    build_market_high_context,
    build_market_options_context,
    build_market_summary_context,
    build_market_theme_flow_context,
    build_market_volatility_sentiment_context,
    load_cached_market_full_context,
    load_cached_market_summary_context,
)
from src.services.market_presentation_service import (
    CreditStressDisplay,
    DistortionItem,
    FlowAlignmentDisplay,
    FlowProxyDisplay,
    IbdRegimeDisplay,
    ImportantLevelDisplay,
    JapanConditionDisplay,
    MarketDriverDisplay,
    MarketMonitorData,
    MarketSignal,
    MicrostructureData,
    MomentumCategory,
    OpportunityThemeDisplay,
    OptionSummary,
    RegimePlaybookDisplay,
    SectorFlowGroup,
    StageStatusDisplay,
    StrategyRegimeDisplay,
    TimeframeOutlookDisplay,
    TrendRankingDisplay,
    build_market_display_context,
)


class FomoScanDisplay(BaseModel):
    ticker: str = ""
    label: str = ""
    risk_level: str = ""
    rank_score: float = 0.0


class MarketState(rx.State):
    """State for the Market Intelligence page."""

    market_type: str = "US"
    is_fetching: bool = False
    is_fetching_summary: bool = False
    is_fetching_details: bool = False
    is_fetching_options: bool = False
    is_scanning_fomo: bool = False
    error_msg: str = ""
    option_error_msg: str = ""
    option_status: str = "unavailable"
    option_failed_tickers: list[str] = []

    indices_data: list[dict[str, Any]] = []
    sectors_data: list[dict[str, Any]] = []
    others_data: list[dict[str, Any]] = []

    evaluation: dict[str, Any] = {}
    market_signals: list[MarketSignal] = []
    microstructure: MicrostructureData = MicrostructureData()
    option_analysis: list[OptionSummary] = []
    momentum_data: list[MomentumCategory] = []
    market_monitor: MarketMonitorData = MarketMonitorData()
    ibd_regime: IbdRegimeDisplay = IbdRegimeDisplay()
    regime_playbook: RegimePlaybookDisplay = RegimePlaybookDisplay()
    bullish_distortions: list[DistortionItem] = []
    bearish_distortions: list[DistortionItem] = []
    watch_indices_data: list[dict[str, Any]] = []
    sector_flow_groups: list[SectorFlowGroup] = []
    sector_flow_summary: str = ""
    cross_market_stance: str = ""
    credit_stress: CreditStressDisplay = CreditStressDisplay()
    flow_monitor: FlowProxyDisplay = FlowProxyDisplay()
    flow_alignment: FlowAlignmentDisplay = FlowAlignmentDisplay()
    strategy_regime: StrategyRegimeDisplay = StrategyRegimeDisplay()
    market_timeframes: list[TimeframeOutlookDisplay] = []
    important_levels: list[ImportantLevelDisplay] = []
    important_levels_summary: str = ""
    market_drivers: list[MarketDriverDisplay] = []
    market_drivers_summary: str = ""
    trend_ranking_items: list[TrendRankingDisplay] = []
    trend_ranking_summary: str = ""
    opportunity_theme_items: list[OpportunityThemeDisplay] = []
    opportunity_theme_summary: str = ""
    detail_stages: list[StageStatusDisplay] = []
    japan_conditions: list[JapanConditionDisplay] = []
    japan_conditions_summary: str = ""
    japan_conditions_score_label: str = ""
    japan_conditions_score: float = 0.0
    volatility_summary: str = ""
    volatility_posture: str = ""
    sentiment_summary: str = ""
    sentiment_coverage: str = ""
    top_risk_summary: str = ""
    fomo_scan_summary: str = ""
    fomo_scan_items: list[FomoScanDisplay] = []

    ai_recap: str = ""
    is_generating_recap: bool = False
    ai_recap_error_type: str = ""
    ai_recap_notice_msg: str = ""
    recap_focus_visible: bool = False
    custom_recap_focus: str = ""
    market_context: dict[str, Any] = {}
    data_status: list[DataStatusDisplay] = []
    provenance: list[ProvenanceDisplay] = []

    def set_market_type(self, m_type: str):
        self.market_type = m_type
        return MarketState.fetch_market_summary_fast

    def toggle_recap_focus(self):
        self.recap_focus_visible = not self.recap_focus_visible

    def set_custom_recap_focus(self, value: str):
        self.custom_recap_focus = value

    async def fetch_market_summary_fast(self):
        self.is_fetching_summary = True
        self.is_fetching = not self._has_visible_market_data()
        self.error_msg = ""
        self.option_error_msg = ""
        yield

        try:
            cached = await asyncio.to_thread(
                load_cached_market_summary_context, self.market_type
            )
            if cached:
                self._apply_market_context(cached)
                self.is_fetching = False
                self.is_fetching_summary = False
                yield
                self.is_fetching_summary = True

            context = await asyncio.to_thread(
                build_market_summary_context, self.market_type
            )
            self._apply_market_context(context)
        except Exception as exc:
            self.error_msg = f"Failed to fetch market data: {exc}"
            self.indices_data = []
            self.sectors_data = []
            self.others_data = []
            self.option_analysis = []
            self.option_status = "failed"
            self.option_failed_tickers = []
            self.market_signals = []
        finally:
            self.is_fetching = False
            self.is_fetching_summary = False
            yield

    async def refresh_market_details(self):
        self.is_fetching_details = True
        self.error_msg = ""
        self._set_stage_status("core", "loading", "前回成功データを確認中...")
        yield

        cached_context = await asyncio.to_thread(
            load_cached_market_full_context, self.market_type
        )
        if cached_context:
            self._apply_market_context(cached_context)
            yield
        else:
            self._set_stage_status("core", "live", "表示中の市場サマリーを使用します。")
            yield

        base_context = self.market_context or None
        try:
            self._set_stage_status(
                "theme_flow", "loading", "市場状態、テーマ、資金フローを取得中..."
            )
            yield
            context = await asyncio.to_thread(
                build_market_theme_flow_context,
                self.market_type,
                base_context,
            )
            self._apply_market_context(context)
            base_context = self.market_context or None
            yield
        except Exception as exc:
            self._set_stage_status("theme_flow", "failed", str(exc))
            self.error_msg = f"Theme/flow stage failed: {exc}"
            yield

        try:
            self._set_stage_status(
                "volatility_sentiment",
                "loading",
                "ボラティリティ・レジームと独自Fear & Greedを取得中...",
            )
            yield
            context = await asyncio.to_thread(
                build_market_volatility_sentiment_context,
                self.market_type,
                base_context,
            )
            self._apply_market_context(context)
            base_context = self.market_context or None
            yield
        except Exception as exc:
            self._set_stage_status("volatility_sentiment", "failed", str(exc))
            self.error_msg = f"Volatility/sentiment stage failed: {exc}"
            yield

        try:
            self._set_stage_status(
                "credit_distortion",
                "loading",
                "信用ストレス、歪み検知、天井警戒を取得中...",
            )
            yield
            context = await asyncio.to_thread(
                build_market_high_context,
                self.market_type,
                base_context,
            )
            self._apply_market_context(context)
            base_context = self.market_context or None
            yield
        except Exception as exc:
            self._set_stage_status("credit_distortion", "failed", str(exc))
            self.error_msg = f"Credit/risk stage failed: {exc}"
            yield

        try:
            self._set_stage_status("options", "loading", "オプション分析を取得中...")
            yield
            context = await asyncio.to_thread(
                build_market_options_context,
                self.market_type,
                base_context,
            )
            self._apply_market_context(context)
        except Exception as exc:
            self.option_status = "failed"
            self.option_error_msg = f"Failed to refresh option data: {exc}"
            self._set_stage_status("options", "failed", str(exc))
        finally:
            self.is_fetching_details = False
            yield

    async def refresh_options(self):
        self.is_fetching_options = True
        self.error_msg = ""
        self.option_error_msg = ""
        self._set_stage_status("options", "loading", "オプション分析を取得中...")
        yield

        try:
            context = await asyncio.to_thread(
                build_market_options_context,
                self.market_type,
                self.market_context or None,
            )
            self._apply_market_context(context)
        except Exception as exc:
            self.option_status = "failed"
            self.option_error_msg = f"Failed to refresh option data: {exc}"
            self._set_stage_status("options", "failed", str(exc))
        finally:
            self.is_fetching_options = False
            yield

    async def refresh_fomo_scan(self):
        self.is_scanning_fomo = True
        yield
        try:
            result = await asyncio.to_thread(build_fomo_scan_context)
            self.fomo_scan_summary = str(result.get("summary", ""))
            self.fomo_scan_items = [
                FomoScanDisplay(
                    ticker=str(item.get("ticker", "")),
                    label=str(item.get("label", "")),
                    risk_level=str(item.get("risk_level", "")),
                    rank_score=float(item.get("rank_score", 0.0)),
                )
                for item in result.get("items", [])
            ]
            if result.get("errors"):
                self.error_msg = "; ".join(result["errors"][:3])
        except Exception as exc:
            self.error_msg = f"FOMO scan failed: {exc}"
        finally:
            self.is_scanning_fomo = False
            yield

    async def fetch_market_data(self):
        async for _ in self.refresh_market_details():
            yield

    async def generate_ai_recap(self):
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
        self.ai_recap_notice_msg = ""
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                self.market_type,
                market_context=self.market_context or None,
                custom_focus=None,
            )
            if recap:
                self.ai_recap = recap
                self.ai_recap_error_type = self._classify_recap_failure(recap)
                if self.ai_recap_error_type:
                    self.ai_recap_notice_msg = (
                        "AI Recapは利用不可または簡易結果です: "
                        + self.ai_recap_error_type
                    )
            else:
                self.ai_recap_error_type = "unknown"
                self.ai_recap_notice_msg = "AI Recapを生成できませんでした。"
        except Exception as exc:
            self.ai_recap_error_type = "exception"
            self.ai_recap_notice_msg = f"AI Recap生成エラー: {exc}"
        finally:
            self.is_generating_recap = False
            yield

    async def generate_ai_recap_with_focus(self):
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
        self.ai_recap_notice_msg = ""
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                self.market_type,
                market_context=self.market_context or None,
                custom_focus=self.custom_recap_focus.strip(),
            )
            if recap:
                self.ai_recap = recap
                self.ai_recap_error_type = self._classify_recap_failure(recap)
                if self.ai_recap_error_type:
                    self.ai_recap_notice_msg = (
                        "AI Recapは利用不可または簡易結果です: "
                        + self.ai_recap_error_type
                    )
            else:
                self.ai_recap_error_type = "unknown"
                self.ai_recap_notice_msg = "AI Recapを生成できませんでした。"
        except Exception as exc:
            self.ai_recap_error_type = "exception"
            self.ai_recap_notice_msg = f"AI Recap生成エラー: {exc}"
        finally:
            self.is_generating_recap = False
            yield

    def _apply_market_context(self, context) -> None:
        self.market_context = context.to_dict()
        from src.services.provider_health import (
            record_data_results,
            record_option_context,
        )

        record_data_results(context.data_status, scope=f"market.{context.market_type}")
        record_option_context(context.options, scope=f"market.{context.market_type}")
        display = build_market_display_context(context)

        self.option_error_msg = context.options.error_message
        self.option_status = context.options.status
        self.option_failed_tickers = list(context.options.failed_tickers)
        self.option_analysis = display.option_analysis
        if not self.option_analysis and not self.option_error_msg:
            self.option_error_msg = "Option data is currently unavailable."

        self.evaluation = display.evaluation
        self.market_signals = display.market_signals
        self.microstructure = display.microstructure
        self.momentum_data = display.momentum_data
        self.market_monitor = display.market_monitor
        self.ibd_regime = display.ibd_regime
        self.regime_playbook = display.regime_playbook
        self.bullish_distortions = display.bullish_distortions
        self.bearish_distortions = display.bearish_distortions
        self.sector_flow_groups = display.sector_flow_groups
        self.sector_flow_summary = display.sector_flow_summary
        self.cross_market_stance = display.cross_market_stance
        self.credit_stress = display.credit_stress
        self.flow_monitor = display.flow_monitor
        self.flow_alignment = display.flow_alignment
        self.strategy_regime = display.strategy_regime
        self.market_timeframes = display.market_timeframes
        self.important_levels = display.important_levels
        self.important_levels_summary = display.important_levels_summary
        self.market_drivers = display.market_drivers
        self.market_drivers_summary = display.market_drivers_summary
        self.trend_ranking_items = display.trend_ranking_items
        self.trend_ranking_summary = display.trend_ranking_summary
        self.opportunity_theme_items = display.opportunity_theme_items
        self.opportunity_theme_summary = display.opportunity_theme_summary
        self.detail_stages = display.detail_stages
        self.japan_conditions = display.japan_conditions
        self.japan_conditions_summary = display.japan_conditions_summary
        self.japan_conditions_score_label = display.japan_conditions_score_label
        self.japan_conditions_score = display.japan_conditions_score
        self.volatility_summary = str(context.volatility_regime.get("summary", ""))
        self.volatility_posture = str(context.volatility_regime.get("posture", ""))
        self.sentiment_summary = str(context.sentiment.get("summary", ""))
        self.sentiment_coverage = str(context.sentiment.get("coverage", ""))
        self.top_risk_summary = str(context.top_risk_signposts.get("summary", ""))
        self.indices_data = display.indices_data
        self.sectors_data = display.sectors_data
        self.others_data = display.others_data
        self.watch_indices_data = display.watch_indices_data
        self.data_status = data_status_display_items(context.data_status)
        self.provenance = provenance_display_items(context.provenance)

    def _has_visible_market_data(self) -> bool:
        return bool(self.indices_data or self.sectors_data or self.others_data)

    def _set_stage_status(self, key: str, status: str, summary: str = "") -> None:
        defaults = {
            "core": ("Core: 市場概要/キャッシュ", "低"),
            "theme_flow": ("Theme/Flow: 市場状態/資金流入", "中"),
            "volatility_sentiment": ("Vol/Sentiment: ボラ/センチメント", "中"),
            "credit_distortion": ("Credit/Risk: 信用/歪み/天井警戒", "高"),
            "options": ("高: オプション", "高"),
        }
        existing = {item.key: item for item in self.detail_stages}
        rows: list[StageStatusDisplay] = []
        for stage_key in (
            "core",
            "theme_flow",
            "volatility_sentiment",
            "credit_distortion",
            "options",
        ):
            current = existing.get(stage_key)
            label, difficulty = defaults[stage_key]
            if current:
                row = StageStatusDisplay(
                    key=current.key,
                    label=current.label,
                    difficulty=current.difficulty,
                    status=current.status,
                    status_label=current.status_label,
                    cache_status=current.cache_status,
                    fetched_at=current.fetched_at,
                    summary=current.summary,
                    quality_warnings=current.quality_warnings,
                )
            else:
                row = StageStatusDisplay(
                    key=stage_key,
                    label=label,
                    difficulty=difficulty,
                    status="pending",
                    status_label="未取得",
                )
            if stage_key == key:
                row.status = status
                row.status_label = self._stage_status_label(status)
                row.summary = summary or row.summary
            rows.append(row)
        self.detail_stages = rows

    def _stage_status_label(self, status: str) -> str:
        labels = {
            "pending": "未取得",
            "loading": "取得中",
            "live": "最新",
            "partial": "一部取得",
            "cache": "キャッシュ",
            "stale_cache": "古いキャッシュ",
            "failed": "取得失敗",
        }
        return labels.get(status, status)

    def _classify_recap_failure(self, recap: str) -> str:
        if "Gemini API" in recap or "APIキー" in recap:
            return "gemini"
        if "データ取得" in recap or "data" in recap.lower():
            return "data"
        if "レポート生成エラー" in recap:
            return "generation"
        return ""
