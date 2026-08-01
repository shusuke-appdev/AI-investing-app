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
from frontend.state.error_handling import log_state_exception
from frontend.state.request_tracking import is_current_request
from src.log_config import get_logger
from src.services.analysis_context import MarketContext
from src.services.market_analysis_inputs import build_market_analysis_inputs
from src.services.market_analyst_service import generate_market_analysis_report
from src.services.market_dashboard_service import (
    build_fomo_scan_context,
    build_market_high_context,
    build_market_option_snapshot,
    build_market_options_context,
    build_market_summary_context,
    build_market_theme_flow_context,
    build_market_volatility_sentiment_context,
    load_cached_market_full_context,
    load_cached_market_summary_context,
)
from src.services.market_presentation_service import (
    CompositeSentimentDisplay,
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
    ShortForecastDisplay,
    StageStatusDisplay,
    StrategyRegimeDisplay,
    TimeframeOutlookDisplay,
    TrendRankingDisplay,
    VixSqAlertDisplay,
    build_market_display_context,
)

logger = get_logger(__name__)


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
    option_provider_active: bool = False
    option_fallback_reason: str = ""
    option_gamma_coverage: str = "-"
    option_complete_status: str = "unavailable"

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
    vix_sq_alert: VixSqAlertDisplay = VixSqAlertDisplay()
    flow_alignment: FlowAlignmentDisplay = FlowAlignmentDisplay()
    strategy_regime: StrategyRegimeDisplay = StrategyRegimeDisplay()
    market_timeframes: list[TimeframeOutlookDisplay] = []
    short_horizon_forecasts: list[ShortForecastDisplay] = []
    composite_sentiment_items: list[CompositeSentimentDisplay] = []
    important_levels: list[ImportantLevelDisplay] = []
    important_levels_summary: str = ""
    market_drivers: list[MarketDriverDisplay] = []
    market_drivers_summary: str = ""
    trend_ranking_items: list[TrendRankingDisplay] = []
    top_theme_items: list[TrendRankingDisplay] = []
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
    context_fetched_at: str = ""
    context_cache_status: str = ""
    context_is_stale: bool = False
    context_is_partial: bool = False
    market_request_id: int = 0
    recap_request_id: int = 0

    def set_market_type(self, m_type: str):
        if m_type != self.market_type:
            self.market_request_id += 1
            self.recap_request_id += 1
        self.market_type = m_type
        return MarketState.fetch_market_summary_fast

    def toggle_recap_focus(self):
        self.recap_focus_visible = not self.recap_focus_visible

    def set_custom_recap_focus(self, value: str):
        self.custom_recap_focus = value

    async def fetch_market_summary_fast(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_summary = True
        self.is_fetching = not self._has_visible_market_data()
        self.error_msg = ""
        self.option_error_msg = ""
        yield

        try:
            cached = await asyncio.to_thread(
                load_cached_market_summary_context, market_type
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            if cached:
                self._apply_market_context(cached)
                self.is_fetching = False
                self.is_fetching_summary = False
                yield
                self.is_fetching_summary = True

            context = await asyncio.to_thread(build_market_summary_context, market_type)
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            error = log_state_exception(logger, "市場データの取得", exc)
            self.error_msg = error.message
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching = False
                self.is_fetching_summary = False
                yield

    async def prepare_market_watch(self):
        """Show the last detailed result first, then refresh only the watch overview."""

        request_id, market_type = self._begin_market_request()
        self.is_fetching_summary = True
        self.is_fetching = not self._has_visible_market_data()
        self.error_msg = ""
        yield

        try:
            cached = await asyncio.to_thread(
                load_cached_market_full_context, market_type
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            if cached:
                try:
                    self._apply_market_context(cached)
                except (AttributeError, TypeError, ValueError) as exc:
                    logger.warning("Ignoring incompatible market cache: %s", exc)
                else:
                    self.is_fetching = False
                    yield

            summary = await asyncio.to_thread(build_market_summary_context, market_type)
            if not self._is_current_market_request(request_id, market_type):
                return
            overview = self._merge_summary_into_visible_context(summary)
            self._apply_market_context(overview)
            yield

            inputs = await asyncio.to_thread(
                build_market_analysis_inputs,
                market_type,
                include_detail=False,
            )
            context = await asyncio.to_thread(
                build_market_theme_flow_context,
                market_type,
                self.market_context or None,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            error = log_state_exception(logger, "市場監視の概要更新", exc)
            self.error_msg = error.message
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching = False
                self.is_fetching_summary = False
                yield

    async def refresh_market_details(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_details = True
        self.error_msg = ""
        self._set_stage_status("core", "loading", "前回成功データを確認中...")
        yield

        cached_context = await asyncio.to_thread(
            load_cached_market_full_context, market_type
        )
        if not self._is_current_market_request(request_id, market_type):
            return
        if cached_context:
            try:
                self._apply_market_context(cached_context)
            except (AttributeError, TypeError, ValueError) as exc:
                logger.warning("Ignoring incompatible market cache: %s", exc)
                self._set_stage_status(
                    "core", "partial", "互換性のない前回キャッシュを無視しました。"
                )
            else:
                yield
        else:
            self._set_stage_status("core", "live", "表示中の市場サマリーを使用します。")
            yield

        base_context = self.market_context or None
        inputs = await asyncio.to_thread(
            build_market_analysis_inputs,
            market_type,
            include_detail=True,
        )
        try:
            self._set_stage_status(
                "theme_flow", "loading", "市場状態、テーマ、資金フローを取得中..."
            )
            yield
            context = await asyncio.to_thread(
                build_market_theme_flow_context,
                market_type,
                base_context,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
            base_context = self.market_context or None
            yield
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self._set_stage_failure(
                "theme_flow",
                "Theme/Flowの更新に失敗しました。",
                "Theme/Flowの更新",
                exc,
            )
            yield

        self._set_stage_status(
            "credit_distortion",
            "loading",
            "信用ストレス、歪み検知、天井警戒を取得中...",
        )
        self._set_stage_status("options", "loading", "オプション分析を取得中...")
        self.is_fetching_options = True
        yield
        credit_result, option_result = await asyncio.gather(
            asyncio.to_thread(build_market_high_context, market_type, base_context),
            asyncio.to_thread(build_market_option_snapshot, market_type),
            return_exceptions=True,
        )
        if not self._is_current_market_request(request_id, market_type):
            return
        if isinstance(credit_result, Exception):
            self._set_stage_failure(
                "credit_distortion",
                "Credit/Riskの更新に失敗しました。",
                "Credit/Riskの更新",
                credit_result,
            )
        else:
            self._apply_market_context(credit_result)
        base_context = self.market_context or base_context

        if isinstance(option_result, Exception):
            self.option_status = "failed"
            self.option_error_msg = self._set_stage_failure(
                "options",
                "Optionsの更新に失敗しました。",
                "Optionsの更新",
                option_result,
            )
        else:
            try:
                option_context = await asyncio.to_thread(
                    build_market_options_context,
                    market_type,
                    base_context,
                    option_context=option_result,
                    inputs=inputs,
                )
                self._apply_market_context(option_context)
                base_context = self.market_context or base_context
            except Exception as exc:
                self.option_status = "failed"
                self.option_error_msg = self._set_stage_failure(
                    "options", "Optionsの統合に失敗しました。", "Optionsの統合", exc
                )
        self.is_fetching_options = False
        yield

        try:
            self._set_stage_status(
                "volatility_sentiment",
                "loading",
                "最新の信用・オプションをボラティリティと予測へ反映中...",
            )
            yield
            context = await asyncio.to_thread(
                build_market_volatility_sentiment_context,
                market_type,
                base_context,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self._set_stage_failure(
                "volatility_sentiment",
                "Vol/Sentimentの更新に失敗しました。",
                "Vol/Sentimentの更新",
                exc,
            )
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching_details = False
                self.is_fetching_options = False
                yield

    async def refresh_theme_flow(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_details = True
        self.error_msg = ""
        self._set_stage_status(
            "theme_flow", "loading", "市場状態、テーマ、資金フローを取得中..."
        )
        yield
        try:
            inputs = await asyncio.to_thread(
                build_market_analysis_inputs,
                market_type,
                include_detail=False,
            )
            context = await asyncio.to_thread(
                build_market_theme_flow_context,
                market_type,
                self.market_context or None,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self._set_stage_failure(
                "theme_flow",
                "Theme/Flowの更新に失敗しました。",
                "Theme/Flowの更新",
                exc,
            )
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching_details = False
                yield

    async def refresh_volatility_sentiment(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_details = True
        self.error_msg = ""
        self._set_stage_status(
            "volatility_sentiment",
            "loading",
            "ボラティリティ・レジームと独自Fear & Greedを取得中...",
        )
        yield
        try:
            inputs = await asyncio.to_thread(
                build_market_analysis_inputs,
                market_type,
                include_detail=True,
            )
            context = await asyncio.to_thread(
                build_market_volatility_sentiment_context,
                market_type,
                self.market_context or None,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self._set_stage_failure(
                "volatility_sentiment",
                "Vol/Sentimentの更新に失敗しました。",
                "Vol/Sentimentの更新",
                exc,
            )
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching_details = False
                yield

    async def refresh_credit_distortion(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_details = True
        self.error_msg = ""
        self._set_stage_status(
            "credit_distortion",
            "loading",
            "信用ストレス、歪み検知、天井警戒を取得中...",
        )
        yield
        try:
            inputs = await asyncio.to_thread(
                build_market_analysis_inputs,
                market_type,
                include_detail=True,
            )
            context = await asyncio.to_thread(
                build_market_high_context,
                market_type,
                self.market_context or None,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
            self._set_stage_status(
                "volatility_sentiment",
                "loading",
                "更新した信用ストレスをボラティリティ・予測へ反映中...",
            )
            yield
            context = await asyncio.to_thread(
                build_market_volatility_sentiment_context,
                market_type,
                self.market_context or None,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self._set_stage_failure(
                "credit_distortion",
                "Credit/Riskの更新に失敗しました。",
                "Credit/Riskの更新",
                exc,
            )
        finally:
            if self._is_current_market_request(request_id, market_type):
                self.is_fetching_details = False
                yield

    async def refresh_options(self):
        request_id, market_type = self._begin_market_request()
        self.is_fetching_options = True
        self.error_msg = ""
        self.option_error_msg = ""
        self._set_stage_status("options", "loading", "オプション分析を取得中...")
        yield

        try:
            inputs = await asyncio.to_thread(
                build_market_analysis_inputs,
                market_type,
                include_detail=True,
            )
            context = await asyncio.to_thread(
                build_market_options_context,
                market_type,
                self.market_context or None,
                inputs=inputs,
            )
            if not self._is_current_market_request(request_id, market_type):
                return
            self._apply_market_context(context)
        except Exception as exc:
            if not self._is_current_market_request(request_id, market_type):
                return
            self.option_status = "failed"
            self.option_error_msg = self._set_stage_failure(
                "options", "Optionsの更新に失敗しました。", "Optionsの更新", exc
            )
        finally:
            if self._is_current_market_request(request_id, market_type):
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
                logger.warning("FOMO scan partial failures: %s", result["errors"][:3])
                self.error_msg = "一部銘柄のスキャンを完了できませんでした。取得できた結果だけを表示します。"
        except Exception as exc:
            error = log_state_exception(logger, "FOMOスキャン", exc)
            self.error_msg = error.message
        finally:
            self.is_scanning_fomo = False
            yield

    async def fetch_market_data(self):
        async for _ in self.refresh_market_details():
            yield

    async def generate_ai_recap(self):
        request_id, market_type = self._begin_recap_request()
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
        self.ai_recap_notice_msg = ""
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                market_type,
                market_context=self.market_context or None,
                custom_focus=None,
            )
            if not self._is_current_recap_request(request_id, market_type):
                return
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
            if not self._is_current_recap_request(request_id, market_type):
                return
            error = log_state_exception(logger, "AI Market Recapの生成", exc)
            self.ai_recap_error_type = "exception"
            self.ai_recap_notice_msg = error.message
        finally:
            if self._is_current_recap_request(request_id, market_type):
                self.is_generating_recap = False
                yield

    async def generate_ai_recap_with_focus(self):
        request_id, market_type = self._begin_recap_request()
        custom_focus = self.custom_recap_focus.strip()
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
        self.ai_recap_notice_msg = ""
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                market_type,
                market_context=self.market_context or None,
                custom_focus=custom_focus,
            )
            if not self._is_current_recap_request(request_id, market_type):
                return
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
            if not self._is_current_recap_request(request_id, market_type):
                return
            error = log_state_exception(logger, "AI Market Recapの生成", exc)
            self.ai_recap_error_type = "exception"
            self.ai_recap_notice_msg = error.message
        finally:
            if self._is_current_recap_request(request_id, market_type):
                self.is_generating_recap = False
                yield

    def _begin_market_request(self) -> tuple[int, str]:
        self.market_request_id += 1
        return self.market_request_id, self.market_type

    def _is_current_market_request(self, request_id: int, market_type: str) -> bool:
        return is_current_request(
            current_id=self.market_request_id,
            current_key=self.market_type,
            request_id=request_id,
            request_key=market_type,
        )

    def _begin_recap_request(self) -> tuple[int, str]:
        self.recap_request_id += 1
        return self.recap_request_id, self.market_type

    def _is_current_recap_request(self, request_id: int, market_type: str) -> bool:
        return is_current_request(
            current_id=self.recap_request_id,
            current_key=self.market_type,
            request_id=request_id,
            request_key=market_type,
        )

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
        self.option_provider_active = context.options.provider_active
        self.option_fallback_reason = context.options.fallback_reason
        self.option_gamma_coverage = (
            "-"
            if context.options.gamma_coverage is None
            else f"{context.options.gamma_coverage:.0%}"
        )
        self.option_complete_status = context.options.complete_status
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
        self.vix_sq_alert = display.vix_sq_alert
        self.flow_alignment = display.flow_alignment
        self.strategy_regime = display.strategy_regime
        self.market_timeframes = display.market_timeframes
        self.short_horizon_forecasts = display.short_horizon_forecasts
        self.composite_sentiment_items = display.composite_sentiment_items
        self.important_levels = display.important_levels
        self.important_levels_summary = display.important_levels_summary
        self.market_drivers = display.market_drivers
        self.market_drivers_summary = display.market_drivers_summary
        self.trend_ranking_items = display.trend_ranking_items
        self.top_theme_items = display.trend_ranking_items[:5]
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
        self.context_fetched_at = context.fetched_at
        self.context_cache_status = context.cache_status
        self.context_is_stale = context.is_stale
        self.context_is_partial = context.is_partial

    def _merge_summary_into_visible_context(
        self, summary: MarketContext
    ) -> MarketContext:
        if not self.market_context:
            return summary

        merged = MarketContext.from_mapping(self.market_context)
        merged.market_type = summary.market_type
        merged.market_data = summary.market_data
        merged.market_config = summary.market_config
        if summary.detail_stages.get("core"):
            merged.detail_stages = {
                **merged.detail_stages,
                "core": summary.detail_stages["core"],
            }
        detail_names = {item.name for item in summary.data_status}
        merged.data_status = [
            *summary.data_status,
            *(item for item in merged.data_status if item.name not in detail_names),
        ]
        summary_provenance = {item.item_id for item in summary.provenance}
        merged.provenance = [
            *summary.provenance,
            *(
                item
                for item in merged.provenance
                if item.item_id not in summary_provenance
            ),
        ]
        merged.source = summary.source
        merged.fetched_at = summary.fetched_at
        merged.cache_status = summary.cache_status
        merged.cache_age_seconds = summary.cache_age_seconds
        merged.is_stale = summary.is_stale
        merged.is_partial = summary.is_partial or merged.is_partial
        merged.errors = list(dict.fromkeys([*merged.errors, *summary.errors]))
        merged.quality_warnings = list(
            dict.fromkeys([*merged.quality_warnings, *summary.quality_warnings])
        )
        return merged

    def _has_visible_market_data(self) -> bool:
        return bool(self.indices_data or self.sectors_data or self.others_data)

    def _set_stage_failure(
        self,
        key: str,
        summary: str,
        operation: str,
        exc: Exception,
    ) -> str:
        """Log provider details and expose only a stable retry message."""

        error = log_state_exception(logger, operation, exc)
        self._set_stage_status(key, "failed", summary, error.message)
        return error.message

    def _set_stage_status(
        self, key: str, status: str, summary: str = "", error_message: str = ""
    ) -> None:
        defaults = {
            "core": (
                "Core: 市場概要/キャッシュ",
                "低",
                "主要指数、設定、前回成功キャッシュ",
            ),
            "theme_flow": (
                "Theme/Flow: 市場状態/資金流入",
                "中",
                "IBD式市場状態、モメンタム、統合トレンド、セクター/テーマ資金流入",
            ),
            "volatility_sentiment": (
                "Vol/Sentiment: ボラ/センチメント",
                "中",
                "ボラティリティ、1/5/20日短期予測、複合センチメント、時間軸別方向感",
            ),
            "credit_distortion": (
                "Credit/Risk: 信用/歪み/天井警戒",
                "高",
                "FRED信用ストレス、市場の歪み検知、天井警戒サインポスト",
            ),
            "options": (
                "高: オプション",
                "高",
                "SPY/QQQ/IWMと上位テーマETF proxyのPCR、IV、Greeks、GEX可否",
            ),
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
            label, difficulty, target = defaults[stage_key]
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
                    target=current.target,
                    error_message=current.error_message,
                    quality_warnings=current.quality_warnings,
                )
            else:
                row = StageStatusDisplay(
                    key=stage_key,
                    label=label,
                    difficulty=difficulty,
                    target=target,
                    status="pending",
                    status_label="未取得",
                )
            if stage_key == key:
                row.status = status
                row.status_label = self._stage_status_label(status)
                row.summary = summary or row.summary
                row.error_message = error_message
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
