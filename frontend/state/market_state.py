import asyncio
from typing import Any

import reflex as rx

from src.services.market_analyst_service import generate_market_analysis_report
from src.services.market_dashboard_service import (
    build_market_details_context,
    build_market_options_context,
    build_market_summary_context,
    load_cached_market_summary_context,
)
from src.services.market_presentation_service import (
    CreditStressDisplay,
    DistortionItem,
    FlowProxyDisplay,
    IbdRegimeDisplay,
    JapanConditionDisplay,
    MarketMonitorData,
    MarketSignal,
    MicrostructureData,
    MomentumCategory,
    OptionSummary,
    RegimePlaybookDisplay,
    SectorFlowGroup,
    build_market_display_context,
)


class MarketState(rx.State):
    """State for the Market Intelligence page."""

    market_type: str = "US"
    is_fetching: bool = False
    is_fetching_summary: bool = False
    is_fetching_details: bool = False
    is_fetching_options: bool = False
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
    japan_conditions: list[JapanConditionDisplay] = []
    japan_conditions_summary: str = ""
    japan_conditions_score_label: str = ""
    japan_conditions_score: float = 0.0

    ai_recap: str = ""
    is_generating_recap: bool = False
    ai_recap_error_type: str = ""
    recap_focus_visible: bool = False
    custom_recap_focus: str = ""
    market_context: dict[str, Any] = {}

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
        yield

        try:
            context = await asyncio.to_thread(
                build_market_details_context,
                self.market_type,
                self.market_context or None,
            )
            self._apply_market_context(context)
        except Exception as exc:
            self.error_msg = f"Failed to refresh market details: {exc}"
        finally:
            self.is_fetching_details = False
            yield

    async def refresh_options(self):
        self.is_fetching_options = True
        self.error_msg = ""
        self.option_error_msg = ""
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
        finally:
            self.is_fetching_options = False
            yield

    async def fetch_market_data(self):
        async for _ in self.refresh_market_details():
            yield

    async def generate_ai_recap(self):
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
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
                    self.error_msg = (
                        "AI recap generation returned a degraded result: "
                        + self.ai_recap_error_type
                    )
            else:
                self.ai_recap_error_type = "unknown"
                self.error_msg = "Failed to generate market recap."
        except Exception as exc:
            self.ai_recap_error_type = "exception"
            self.error_msg = f"AI recap generation error: {exc}"
        finally:
            self.is_generating_recap = False
            yield

    async def generate_ai_recap_with_focus(self):
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
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
                    self.error_msg = (
                        "AI recap generation returned a degraded result: "
                        + self.ai_recap_error_type
                    )
            else:
                self.ai_recap_error_type = "unknown"
                self.error_msg = "Failed to generate market recap."
        except Exception as exc:
            self.ai_recap_error_type = "exception"
            self.error_msg = f"AI recap generation error: {exc}"
        finally:
            self.is_generating_recap = False
            yield

    def _apply_market_context(self, context) -> None:
        self.market_context = context.to_dict()
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
        self.japan_conditions = display.japan_conditions
        self.japan_conditions_summary = display.japan_conditions_summary
        self.japan_conditions_score_label = display.japan_conditions_score_label
        self.japan_conditions_score = display.japan_conditions_score
        self.indices_data = display.indices_data
        self.sectors_data = display.sectors_data
        self.others_data = display.others_data
        self.watch_indices_data = display.watch_indices_data

        if context.quality_warnings and not self.error_msg:
            self.error_msg = "; ".join(context.quality_warnings[:3])

    def _has_visible_market_data(self) -> bool:
        return bool(self.indices_data or self.sectors_data or self.others_data)

    def _classify_recap_failure(self, recap: str) -> str:
        if "Gemini API" in recap or "APIキー" in recap:
            return "gemini"
        if "データ取得" in recap or "data" in recap.lower():
            return "data"
        if "レポート生成エラー" in recap:
            return "generation"
        return ""
