import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

from src.services.market_analyst_service import generate_market_analysis_report
from src.services.market_dashboard_service import (
    build_market_details_context,
    build_market_options_context,
    build_market_summary_context,
    load_cached_market_summary_context,
)
from src.services.market_presentation_service import format_option_summaries


class MarketSignal(BaseModel):
    name: str = ""
    score: float = 0.0
    weight: float = 0.0
    rationale: str = ""
    category: str = "neutral"


class OptionSummary(BaseModel):
    ticker: str = ""
    sentiment: str = "Neutral"
    current_price: float = 0.0
    current_price_str: str = ""
    pcr_vol: float = 0.0
    pcr_vol_str: str = ""
    net_gex: float = 0.0
    net_gex_str: str = ""
    net_gex_available: bool = False
    iv: str = "-"
    max_pain: str = "-"
    analysis: list[str] = []
    data_quality: str = "unavailable"
    quality_warnings: list[str] = []


class MicrostructureData(BaseModel):
    unwind_score: int = 0
    unwind_level: str = ""
    vrp: str = "-"
    cta_score: int = 0
    cta_extremity: str = ""
    liquidity_status: str = ""
    narrative: str = ""


class MomentumTheme(BaseModel):
    theme: str = ""
    performance: float = 0.0
    performance_str: str = ""


class MomentumCategory(BaseModel):
    category: str = ""
    period: str = ""
    themes: list[MomentumTheme] = []


class SectorFlowItem(BaseModel):
    market: str = ""
    theme: str = ""
    flow_score: float = 0.0
    flow_score_str: str = ""
    confidence: str = ""
    continuation: str = ""
    action: str = ""
    relative_1d_str: str = ""
    change_5d_str: str = ""
    volume_ratio_str: str = ""
    participation_str: str = ""
    evidence: str = ""


class SectorFlowGroup(BaseModel):
    market: str = ""
    market_label: str = ""
    summary: str = ""
    leaders: list[SectorFlowItem] = []


class CreditStressIndicator(BaseModel):
    series_id: str = ""
    label: str = ""
    latest: float = 0.0
    latest_str: str = ""
    latest_date: str = ""
    delta_3m: float = 0.0
    delta_3m_str: str = ""
    z_score: float = 0.0
    z_score_str: str = ""
    is_hot: bool = False
    level: str = "gray"
    warning: str = ""


class CreditStressDisplay(BaseModel):
    status: str = ""
    status_label: str = ""
    level: str = "gray"
    summary: str = ""
    rapid_stress: bool = False
    indicators: list[CreditStressIndicator] = []
    confirmations: list[CreditStressIndicator] = []
    source: str = ""
    fetched_at: str = ""


class FlowProxyItem(BaseModel):
    ticker: str = ""
    label: str = ""
    leadership_score: float = 0.0
    leadership_score_str: str = ""
    flow_pressure_z: float = 0.0
    flow_pressure_z_str: str = ""
    relative_return_20d_str: str = ""
    relative_return_60d_str: str = ""
    trend_above_ma50: bool = False
    level: str = "gray"


class FlowProxyDisplay(BaseModel):
    status: str = ""
    summary: str = ""
    leaders: list[FlowProxyItem] = []
    laggards: list[FlowProxyItem] = []
    source: str = ""


class JapanConditionDisplay(BaseModel):
    condition_no: int = 0
    title: str = ""
    category: str = ""
    status: str = ""
    status_label: str = ""
    value: str = ""
    threshold: str = ""
    score: float = 0.0
    assessment: str = ""
    evidence: str = ""


class DistributionData(BaseModel):
    count: int = 0
    status: str = ""
    level: str = "normal"


class ClimaxData(BaseModel):
    is_climax: bool = False
    warnings: list[str] = []
    level: str = "normal"


class SpreadItem(BaseModel):
    earnings_yield: float = 0.0
    spread: float = 0.0
    status: str = "neutral"
    level: str = "neutral"


class Spreads(BaseModel):
    SPY: SpreadItem = SpreadItem()
    NDX: SpreadItem = SpreadItem()


class YieldSpreadData(BaseModel):
    yield_10y: float = 0.0
    spreads: Spreads = Spreads()
    overall_status: str = "neutral"
    warnings: list[str] = []


class MarketMonitorData(BaseModel):
    distribution_spy: DistributionData = DistributionData()
    distribution_ndx: DistributionData = DistributionData()
    climax: ClimaxData = ClimaxData()
    yield_spread: YieldSpreadData = YieldSpreadData()


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
    market_context: dict[str, Any] = {}

    def set_market_type(self, m_type: str):
        self.market_type = m_type
        return MarketState.fetch_market_summary_fast

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

    def _format_options(self, option_data: list[dict[str, Any]]) -> list[OptionSummary]:
        return [OptionSummary(**item) for item in format_option_summaries(option_data)]

    def _format_signals(self, evaluation: dict[str, Any]) -> list[MarketSignal]:
        signals = []
        for signal in evaluation.get("signals", []):
            score = float(signal.get("score", 0.0))
            signals.append(
                MarketSignal(
                    name=signal.get("name", ""),
                    score=score,
                    weight=float(signal.get("weight", 0.0)),
                    rationale=signal.get("rationale", ""),
                    category="bullish"
                    if score >= 0.3
                    else "bearish"
                    if score <= -0.3
                    else "neutral",
                )
            )
        return signals

    def _format_microstructure(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return {}
        cta = data.get("cta_proxy") or {}
        liq = data.get("liquidity") or {}
        vrp_val = data.get("vrp")
        return {
            "unwind_score": data.get("unwind_score", 0),
            "unwind_level": data.get("unwind_level", ""),
            "vrp": f"{vrp_val:.2%}" if vrp_val is not None else "-",
            "cta_score": cta.get("score", 0),
            "cta_extremity": cta.get("extremity", ""),
            "liquidity_status": liq.get("status", ""),
            "narrative": data.get("narrative_text", ""),
        }

    def _format_momentum(
        self, raw: dict[str, list[dict[str, Any]]]
    ) -> list[MomentumCategory]:
        result = []
        for category, themes in raw.items():
            theme_list = []
            for item in themes:
                perf = float(item.get("performance", 0.0))
                theme_list.append(
                    MomentumTheme(
                        theme=item.get("theme", ""),
                        performance=perf,
                        performance_str=f"{perf:+.1f}%",
                    )
                )
            result.append(
                MomentumCategory(
                    category=category,
                    period=themes[-1].get("period", "") if themes else "",
                    themes=theme_list,
                )
            )
        return result

    def _format_sector_flow(self, raw: dict[str, Any]) -> list[SectorFlowGroup]:
        groups = []
        markets = raw.get("markets", {}) if raw else {}
        for market in ("US", "JP"):
            payload = markets.get(market, {})
            leaders = []
            for item in payload.get("leaders", []):
                score = float(item.get("flow_score", 0.0))
                leaders.append(
                    SectorFlowItem(
                        market=market,
                        theme=item.get("theme", ""),
                        flow_score=score,
                        flow_score_str=f"{score:+.1f}",
                        confidence=item.get("confidence", ""),
                        continuation=item.get("continuation", ""),
                        action=item.get("action", ""),
                        relative_1d_str=f"{float(item.get('relative_1d', 0.0)):+.2f}pt",
                        change_5d_str=f"{float(item.get('change_5d', 0.0)):+.2f}%",
                        volume_ratio_str=f"{float(item.get('volume_ratio', 0.0)):.2f}x",
                        participation_str=f"{float(item.get('participation', 0.0)):.0%}",
                        evidence=item.get("evidence", ""),
                    )
                )
            groups.append(
                SectorFlowGroup(
                    market=market,
                    market_label="米国" if market == "US" else "日本",
                    summary=payload.get("summary", ""),
                    leaders=leaders,
                )
            )
        return groups

    def _format_japan_conditions(
        self, raw: dict[str, Any]
    ) -> list[JapanConditionDisplay]:
        result = []
        for item in raw.get("items", []) if raw else []:
            result.append(
                JapanConditionDisplay(
                    condition_no=int(item.get("condition_no", 0)),
                    title=item.get("title", ""),
                    category=item.get("category", ""),
                    status=item.get("status", ""),
                    status_label=item.get("status_label", ""),
                    value=item.get("value", ""),
                    threshold=item.get("threshold", ""),
                    score=float(item.get("score", 0.0)),
                    assessment=item.get("assessment", ""),
                    evidence=item.get("evidence", ""),
                )
            )
        return result

    def _format_credit_stress(self, raw: dict[str, Any]) -> CreditStressDisplay:
        if not raw:
            return CreditStressDisplay()
        return CreditStressDisplay(
            status=raw.get("status", ""),
            status_label=raw.get("status_label", ""),
            level=raw.get("level", "gray"),
            summary=raw.get("summary", ""),
            rapid_stress=bool(raw.get("rapid_stress", False)),
            indicators=[
                self._format_credit_indicator(item)
                for item in raw.get("indicators", [])
            ],
            confirmations=[
                self._format_credit_indicator(item)
                for item in raw.get("confirmations", [])[:6]
            ],
            source=raw.get("source", ""),
            fetched_at=raw.get("fetched_at", ""),
        )

    def _format_credit_indicator(self, item: dict[str, Any]) -> CreditStressIndicator:
        latest = float(item.get("latest", 0.0))
        delta = float(item.get("delta_3m", 0.0))
        z_score = float(item.get("z_score", 0.0))
        return CreditStressIndicator(
            series_id=item.get("series_id", ""),
            label=item.get("label", ""),
            latest=latest,
            latest_str=f"{latest:.2f}",
            latest_date=item.get("latest_date", ""),
            delta_3m=delta,
            delta_3m_str=f"{delta:+.2f}",
            z_score=z_score,
            z_score_str=f"{z_score:+.2f}",
            is_hot=bool(item.get("is_hot", False)),
            level=item.get("level", "gray"),
            warning=item.get("warning", ""),
        )

    def _format_flow_monitor(self, raw: dict[str, Any]) -> FlowProxyDisplay:
        if not raw:
            return FlowProxyDisplay()
        return FlowProxyDisplay(
            status=raw.get("status", ""),
            summary=raw.get("summary", ""),
            leaders=[
                self._format_flow_proxy_item(item) for item in raw.get("leaders", [])
            ],
            laggards=[
                self._format_flow_proxy_item(item) for item in raw.get("laggards", [])
            ],
            source=raw.get("source", ""),
        )

    def _format_flow_proxy_item(self, item: dict[str, Any]) -> FlowProxyItem:
        score = float(item.get("leadership_score", 0.0))
        flow_z = float(item.get("flow_pressure_z", 0.0))
        return FlowProxyItem(
            ticker=item.get("ticker", ""),
            label=item.get("label", ""),
            leadership_score=score,
            leadership_score_str=f"{score:+.2f}",
            flow_pressure_z=flow_z,
            flow_pressure_z_str=f"{flow_z:+.2f}",
            relative_return_20d_str=(
                f"{float(item.get('relative_return_20d', 0.0)):+.2f}%"
            ),
            relative_return_60d_str=(
                f"{float(item.get('relative_return_60d', 0.0)):+.2f}%"
            ),
            trend_above_ma50=bool(item.get("trend_above_ma50", False)),
            level=item.get("level", "gray"),
        )

    def _set_market_lists(
        self, raw_data: dict[str, Any], config: dict[str, Any]
    ) -> None:
        indices_tickers = set(config.get("indices", {}).values())
        sector_tickers = set(config.get("sectors", {}).values())
        commodity_tickers = set(config.get("commodities", {}).values())
        crypto_tickers = set(config.get("crypto", {}).values())
        forex_tickers = set(config.get("forex", {}).values())
        indices_names = set(config.get("indices", {}).keys())
        sector_names = set(config.get("sectors", {}).keys())
        commodity_names = set(config.get("commodities", {}).keys())
        crypto_names = set(config.get("crypto", {}).keys())
        forex_names = set(config.get("forex", {}).keys())

        indices = []
        sectors = []
        others = []
        for name, data in raw_data.items():
            if name in {"trend_1mo", "weekly_performance"}:
                continue
            item = self._market_item(name, data)
            ticker = data.get("ticker", "")
            if ticker in indices_tickers or name in indices_names:
                indices.append(item)
            elif ticker in sector_tickers or name in sector_names:
                sectors.append(item)
            elif (
                ticker in commodity_tickers
                or ticker in forex_tickers
                or ticker in crypto_tickers
                or name in commodity_names
                or name in forex_names
                or name in crypto_names
            ):
                others.append(item)

        self.indices_data = indices
        self.sectors_data = sectors
        self.others_data = others

    def _market_item(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        price = float(data.get("price", 0.0))
        change = round(float(data.get("change", 0.0)), 1)
        ticker = data.get("ticker", "")
        if "Yield" in name:
            price_text = f"{price:.2f}%"
        elif "JPY" in ticker:
            price_text = f"¥{price:.2f}"
        elif "BTC" in ticker or "ETH" in ticker:
            price_text = f"${price / 1000:.1f}K"
        elif price >= 1000:
            price_text = f"{price:,.0f}"
        else:
            price_text = f"${price:.2f}"
        return {"name": name, "price": price_text, "change": change}

    async def generate_ai_recap(self):
        self.is_generating_recap = True
        self.ai_recap_error_type = ""
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                self.market_type,
                market_context=self.market_context or None,
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

        self.option_error_msg = context.options.error_message
        self.option_status = context.options.status
        self.option_failed_tickers = list(context.options.failed_tickers)
        self.option_analysis = self._format_options(context.options.items)
        if not self.option_analysis and not self.option_error_msg:
            self.option_error_msg = "Option data is currently unavailable."

        self.evaluation = context.evaluation
        self.market_signals = self._format_signals(context.evaluation)

        micro = self._format_microstructure(context.microstructure)
        self.microstructure = (
            MicrostructureData(**micro) if micro else MicrostructureData()
        )

        self.momentum_data = self._format_momentum(context.momentum)
        self.market_monitor = (
            MarketMonitorData(**context.monitor)
            if context.monitor
            else MarketMonitorData()
        )
        self.sector_flow_groups = self._format_sector_flow(context.sector_flow)
        self.sector_flow_summary = context.sector_flow.get("summary", "")
        self.cross_market_stance = context.cross_market.get("stance", "")
        self.credit_stress = self._format_credit_stress(context.credit_stress)
        self.flow_monitor = self._format_flow_monitor(context.flow_monitor)
        self.japan_conditions = self._format_japan_conditions(context.japan_conditions)
        self.japan_conditions_summary = context.japan_conditions.get("summary", "")
        self.japan_conditions_score_label = context.japan_conditions.get(
            "score_label", ""
        )
        self.japan_conditions_score = float(context.japan_conditions.get("score", 0.0))

        self._set_market_lists(context.market_data, context.market_config)

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
