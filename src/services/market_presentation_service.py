"""Presentation formatting for Market Intelligence state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.services.analysis_context import MarketContext


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
    source: str = ""
    data_as_of: str = ""
    data_mode: str = ""


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


class IbdBenchmarkDisplay(BaseModel):
    ticker: str = ""
    close: float = 0.0
    change_1d: float = 0.0
    ma50: float | None = None
    ma200: float | None = None
    above_ma50: bool = False
    above_ma200: bool = False
    distribution_count: int = 0
    ftd_status: str = ""
    data_quality: str = "unavailable"


class IbdRegimeDisplay(BaseModel):
    status_key: str = ""
    label: str = ""
    score: float = 0.0
    weight: float = 2.0
    exposure_level: str = ""
    rationale: str = ""
    action_summary: str = ""
    benchmarks: list[IbdBenchmarkDisplay] = []


class RegimePlaybookDisplay(BaseModel):
    stance: str = ""
    risk_budget: str = ""
    think_about: list[str] = []
    do_now: list[str] = []
    avoid: list[str] = []


class DistortionItem(BaseModel):
    theme: str = ""
    tickers: list[str] = []
    fundamental_score: float | None = None
    flow_score: float | None = None
    distortion_score: float | None = None
    fundamental_score_str: str = "算出不可"
    flow_score_str: str = "算出不可"
    distortion_score_str: str = "算出不可"
    fundamental_coverage_str: str = "0%"
    flow_coverage_str: str = "0%"
    classification: str = ""
    rating: str = ""
    rationale: str = ""
    fundamental_evidence: list[str] = []
    flow_evidence: list[str] = []


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


class FlowAlignmentDisplay(BaseModel):
    alignment_label: str = ""
    summary: str = ""
    etf_role: str = ""
    sector_role: str = ""


class StrategyRegimeDisplay(BaseModel):
    key: str = ""
    label: str = ""
    rationale: str = ""
    risk_budget: str = ""
    invalidation: str = ""
    evidence: list[str] = []


class TimeframeOutlookDisplay(BaseModel):
    key: str = ""
    label: str = ""
    score: float = 0.0
    score_str: str = ""
    market_tone: str = ""
    direction: str = ""
    direction_label: str = ""
    confidence: str = ""
    evidence: list[str] = []


class ImportantLevelDisplay(BaseModel):
    label: str = ""
    ticker: str = ""
    close_str: str = ""
    support_str: str = ""
    resistance_str: str = ""
    lower_support_str: str = ""
    ma20_str: str = ""
    ma50_str: str = ""
    ma200_str: str = ""
    change_1d_str: str = ""
    behavior: str = ""
    behavior_label: str = ""
    data_quality: str = "unavailable"


class MarketDriverDisplay(BaseModel):
    label: str = ""
    ticker: str = ""
    value_str: str = ""
    change_5d_str: str = ""
    change_20d_str: str = ""
    interpretation: str = ""
    data_quality: str = "unavailable"


class TrendRankingDisplay(BaseModel):
    rank: int = 0
    theme: str = ""
    parent_sector: str = ""
    proxy_ticker: str = ""
    option_proxy_ticker: str = ""
    total_score: float = 0.0
    total_score_str: str = ""
    rank_points: int = 0
    performance_1w_str: str = ""
    performance_1m_str: str = ""
    performance_6m_str: str = ""
    flow_score_str: str = ""
    participation_str: str = ""
    option_asymmetry: str = ""
    option_score_str: str = ""
    option_summary: str = ""
    option_source: str = ""
    option_data_as_of: str = ""
    option_data_quality: str = ""
    representative_tickers: list[str] = []


class OpportunityThemeDisplay(BaseModel):
    theme: str = ""
    parent_sector: str = ""
    proxy_ticker: str = ""
    option_proxy_ticker: str = ""
    rank: int = 0
    opportunity_score: float = 0.0
    opportunity_score_str: str = ""
    label: str = ""
    reason: str = ""
    representative_tickers: list[str] = []
    option_asymmetry: str = ""
    invalidation: str = ""


class StageStatusDisplay(BaseModel):
    key: str = ""
    label: str = ""
    difficulty: str = ""
    status: str = "pending"
    status_label: str = "未取得"
    cache_status: str = ""
    fetched_at: str = ""
    summary: str = ""
    quality_warnings: list[str] = []


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
    yield_10y: float | None = None
    spreads: Spreads = Spreads()
    overall_status: str = "neutral"
    available: bool = False
    warnings: list[str] = []


class MarketMonitorData(BaseModel):
    distribution_spy: DistributionData = DistributionData()
    distribution_ndx: DistributionData = DistributionData()
    climax: ClimaxData = ClimaxData()
    yield_spread: YieldSpreadData = YieldSpreadData()


class MarketDisplayContext(BaseModel):
    option_analysis: list[OptionSummary] = []
    evaluation: dict[str, Any] = {}
    market_signals: list[MarketSignal] = []
    microstructure: MicrostructureData = MicrostructureData()
    momentum_data: list[MomentumCategory] = []
    market_monitor: MarketMonitorData = MarketMonitorData()
    ibd_regime: IbdRegimeDisplay = IbdRegimeDisplay()
    regime_playbook: RegimePlaybookDisplay = RegimePlaybookDisplay()
    bullish_distortions: list[DistortionItem] = []
    bearish_distortions: list[DistortionItem] = []
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
    indices_data: list[dict[str, Any]] = []
    sectors_data: list[dict[str, Any]] = []
    others_data: list[dict[str, Any]] = []
    watch_indices_data: list[dict[str, Any]] = []


def build_market_display_context(context: MarketContext) -> MarketDisplayContext:
    """Convert a market analysis context into Reflex-safe display models."""

    indices_data, sectors_data, others_data = _market_lists(
        context.market_data, context.market_config
    )
    distortions = context.market_distortions or {}
    return MarketDisplayContext(
        option_analysis=[
            OptionSummary(**item)
            for item in format_option_summaries(context.options.items)
        ],
        evaluation=context.evaluation,
        market_signals=_format_signals(context.evaluation),
        microstructure=_format_microstructure(context.microstructure),
        momentum_data=_format_momentum(context.momentum),
        market_monitor=MarketMonitorData(**context.monitor)
        if context.monitor
        else MarketMonitorData(),
        ibd_regime=_format_ibd_regime(context.ibd_regime),
        regime_playbook=_format_playbook(context.regime_playbook),
        bullish_distortions=_format_distortions(distortions.get("bullish", [])),
        bearish_distortions=_format_distortions(distortions.get("bearish", [])),
        sector_flow_groups=_format_sector_flow(context.sector_flow),
        sector_flow_summary=context.sector_flow.get("summary", ""),
        cross_market_stance=context.cross_market.get("stance", ""),
        credit_stress=_format_credit_stress(context.credit_stress),
        flow_monitor=_format_flow_monitor(context.flow_monitor),
        flow_alignment=_format_flow_alignment(context.flow_alignment),
        strategy_regime=_format_strategy_regime(context.strategy_regime),
        market_timeframes=_format_timeframes(context.market_timeframes),
        important_levels=_format_important_levels(context.important_levels),
        important_levels_summary=context.important_levels.get("summary", ""),
        market_drivers=_format_market_drivers(context.market_driver_monitor),
        market_drivers_summary=context.market_driver_monitor.get("summary", ""),
        trend_ranking_items=_format_trend_ranking(context.trend_ranking),
        trend_ranking_summary=context.trend_ranking.get("summary", ""),
        opportunity_theme_items=_format_opportunities(context.opportunity_themes),
        opportunity_theme_summary=context.opportunity_themes.get("summary", ""),
        detail_stages=_format_detail_stages(context.detail_stages),
        japan_conditions=_format_japan_conditions(context.japan_conditions),
        japan_conditions_summary=context.japan_conditions.get("summary", ""),
        japan_conditions_score_label=context.japan_conditions.get("score_label", ""),
        japan_conditions_score=float(context.japan_conditions.get("score", 0.0)),
        indices_data=indices_data,
        sectors_data=sectors_data,
        others_data=others_data,
        watch_indices_data=[
            item
            for item in indices_data
            if item.get("name") in {"S&P 500", "Nasdaq 100"}
        ],
    )


def format_option_summaries(option_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Reflex-safe option summary dictionaries."""

    formatted: list[dict[str, Any]] = []
    for opt in option_data:
        pcr = opt.get("pcr") or {}
        gex = opt.get("gex")
        pcr_val = float(pcr.get("volume_pcr", 0.0))
        has_gex = isinstance(gex, dict) and gex.get("nearby_net_gex") is not None
        gex_val = float(gex.get("nearby_net_gex", 0.0)) if has_gex else 0.0
        current_price = float(opt.get("current_price") or 0.0)
        iv_val = opt.get("iv")
        max_pain = opt.get("max_pain")
        formatted.append(
            {
                "ticker": opt.get("ticker", ""),
                "sentiment": opt.get("sentiment", "Neutral"),
                "current_price": current_price,
                "current_price_str": f"${current_price:,.2f}"
                if current_price > 0
                else "",
                "pcr_vol": pcr_val,
                "pcr_vol_str": f"{pcr_val:.2f}",
                "net_gex": gex_val,
                "net_gex_str": f"{gex_val / 1e6:+.0f}M" if has_gex else "-",
                "net_gex_available": has_gex,
                "iv": f"{iv_val * 100:.1f}%" if iv_val is not None else "-",
                "max_pain": f"${max_pain:.0f}" if max_pain is not None else "-",
                "analysis": opt.get("analysis", []),
                "data_quality": opt.get("data_quality", "unavailable"),
                "quality_warnings": list(opt.get("quality_warnings") or []),
                "source": str(opt.get("source") or ""),
                "data_as_of": str(opt.get("data_as_of") or ""),
                "data_mode": str(opt.get("data_mode") or ""),
            }
        )
    return formatted


def _format_signals(evaluation: dict[str, Any]) -> list[MarketSignal]:
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


def _format_microstructure(data: dict[str, Any]) -> MicrostructureData:
    if not data:
        return MicrostructureData()
    cta = data.get("cta_proxy") or {}
    liq = data.get("liquidity") or {}
    vrp_val = data.get("vrp")
    return MicrostructureData(
        unwind_score=data.get("unwind_score", 0),
        unwind_level=data.get("unwind_level", ""),
        vrp=f"{vrp_val:.2%}" if vrp_val is not None else "-",
        cta_score=cta.get("score", 0),
        cta_extremity=cta.get("extremity", ""),
        liquidity_status=liq.get("status", ""),
        narrative=data.get("narrative_text", ""),
    )


def _format_momentum(raw: dict[str, list[dict[str, Any]]]) -> list[MomentumCategory]:
    result = []
    for category, themes in raw.items():
        theme_list = []
        for item in themes[:3]:
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


def _format_ibd_regime(raw: dict[str, Any]) -> IbdRegimeDisplay:
    if not raw:
        return IbdRegimeDisplay()
    benchmarks = []
    raw_benchmarks = raw.get("benchmarks") or {}
    for item in raw_benchmarks.values():
        if isinstance(item, dict):
            benchmarks.append(IbdBenchmarkDisplay(**item))
    return IbdRegimeDisplay(
        status_key=raw.get("status_key", ""),
        label=raw.get("label", ""),
        score=float(raw.get("score", 0.0)),
        weight=float(raw.get("weight", 2.0)),
        exposure_level=raw.get("exposure_level", ""),
        rationale=raw.get("rationale", ""),
        action_summary=raw.get("action_summary", ""),
        benchmarks=benchmarks,
    )


def _format_playbook(raw: dict[str, Any]) -> RegimePlaybookDisplay:
    if not raw:
        return RegimePlaybookDisplay()
    return RegimePlaybookDisplay(
        stance=raw.get("stance", ""),
        risk_budget=raw.get("risk_budget", ""),
        think_about=list(raw.get("think_about", [])),
        do_now=list(raw.get("do_now", [])),
        avoid=list(raw.get("avoid", [])),
    )


def _format_distortions(rows: list[dict[str, Any]]) -> list[DistortionItem]:
    return [
        DistortionItem(
            theme=item.get("theme", ""),
            tickers=list(item.get("tickers", [])),
            fundamental_score=_optional_float(item.get("fundamental_score")),
            flow_score=_optional_float(item.get("flow_score")),
            distortion_score=_optional_float(item.get("distortion_score")),
            fundamental_score_str=_optional_score(item.get("fundamental_score")),
            flow_score_str=_optional_score(item.get("flow_score")),
            distortion_score_str=_optional_score(item.get("distortion_score")),
            fundamental_coverage_str=_coverage_str(item.get("fundamental_coverage")),
            flow_coverage_str=_coverage_str(item.get("flow_coverage")),
            classification=item.get("classification", ""),
            rating=item.get("rating", ""),
            rationale=item.get("rationale", ""),
            fundamental_evidence=list(item.get("fundamental_evidence", [])),
            flow_evidence=list(item.get("flow_evidence", [])),
        )
        for item in rows
        if isinstance(item, dict)
    ]


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_score(value: Any) -> str:
    number = _optional_float(value)
    return f"{number:.2f}" if number is not None else "算出不可"


def _coverage_str(value: Any) -> str:
    number = _optional_float(value)
    return f"{number:.0%}" if number is not None else "0%"


def _format_sector_flow(raw: dict[str, Any]) -> list[SectorFlowGroup]:
    groups = []
    markets = raw.get("markets", {}) if raw else {}
    ordered = [market for market in ("US", "JP") if market in markets]
    ordered.extend(market for market in markets if market not in {"US", "JP"})
    for market in ordered:
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


def _format_japan_conditions(raw: dict[str, Any]) -> list[JapanConditionDisplay]:
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


def _format_credit_stress(raw: dict[str, Any]) -> CreditStressDisplay:
    if not raw:
        return CreditStressDisplay()
    return CreditStressDisplay(
        status=raw.get("status", ""),
        status_label=raw.get("status_label", ""),
        level=raw.get("level", "gray"),
        summary=raw.get("summary", ""),
        rapid_stress=bool(raw.get("rapid_stress", False)),
        indicators=[
            _format_credit_indicator(item) for item in raw.get("indicators", [])
        ],
        confirmations=[
            _format_credit_indicator(item) for item in raw.get("confirmations", [])[:6]
        ],
        source=raw.get("source", ""),
        fetched_at=raw.get("fetched_at", ""),
    )


def _format_credit_indicator(item: dict[str, Any]) -> CreditStressIndicator:
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


def _format_flow_monitor(raw: dict[str, Any]) -> FlowProxyDisplay:
    if not raw:
        return FlowProxyDisplay()
    return FlowProxyDisplay(
        status=raw.get("status", ""),
        summary=raw.get("summary", ""),
        leaders=[_format_flow_proxy_item(item) for item in raw.get("leaders", [])],
        laggards=[_format_flow_proxy_item(item) for item in raw.get("laggards", [])],
        source=raw.get("source", ""),
    )


def _format_flow_alignment(raw: dict[str, Any]) -> FlowAlignmentDisplay:
    if not raw:
        return FlowAlignmentDisplay()
    return FlowAlignmentDisplay(
        alignment_label=raw.get("alignment_label", ""),
        summary=raw.get("summary", ""),
        etf_role=raw.get("etf_role", ""),
        sector_role=raw.get("sector_role", ""),
    )


def _format_strategy_regime(raw: dict[str, Any]) -> StrategyRegimeDisplay:
    if not raw:
        return StrategyRegimeDisplay()
    return StrategyRegimeDisplay(
        key=raw.get("key", ""),
        label=raw.get("label", ""),
        rationale=raw.get("rationale", ""),
        risk_budget=raw.get("risk_budget", ""),
        invalidation=raw.get("invalidation", ""),
        evidence=list(raw.get("evidence", [])),
    )


def _format_timeframes(raw: dict[str, Any]) -> list[TimeframeOutlookDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        score = float(item.get("score", 0.0))
        rows.append(
            TimeframeOutlookDisplay(
                key=item.get("key", ""),
                label=item.get("label", ""),
                score=score,
                score_str=f"{score:+.2f}",
                market_tone=item.get("market_tone", ""),
                direction=item.get("direction", ""),
                direction_label=item.get("direction_label", ""),
                confidence=item.get("confidence", ""),
                evidence=list(item.get("evidence", [])),
            )
        )
    return rows


def _format_important_levels(raw: dict[str, Any]) -> list[ImportantLevelDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        rows.append(
            ImportantLevelDisplay(
                label=item.get("label", ""),
                ticker=item.get("ticker", ""),
                close_str=_price_str(item.get("close")),
                support_str=_price_str(item.get("support")),
                resistance_str=_price_str(item.get("resistance")),
                lower_support_str=_price_str(item.get("lower_support")),
                ma20_str=_price_str(item.get("ma20")),
                ma50_str=_price_str(item.get("ma50")),
                ma200_str=_price_str(item.get("ma200")),
                change_1d_str=_pct_str(item.get("change_1d")),
                behavior=item.get("behavior", ""),
                behavior_label=item.get("behavior_label", ""),
                data_quality=item.get("data_quality", "unavailable"),
            )
        )
    return rows


def _format_market_drivers(raw: dict[str, Any]) -> list[MarketDriverDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        rows.append(
            MarketDriverDisplay(
                label=item.get("label", ""),
                ticker=item.get("ticker", ""),
                value_str=_driver_value_str(item.get("label", ""), item.get("value")),
                change_5d_str=_pct_str(item.get("change_5d")),
                change_20d_str=_pct_str(item.get("change_20d")),
                interpretation=item.get("interpretation", ""),
                data_quality=item.get("data_quality", "unavailable"),
            )
        )
    return rows


def _format_trend_ranking(raw: dict[str, Any]) -> list[TrendRankingDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        total_score = float(item.get("total_score", 0.0))
        rows.append(
            TrendRankingDisplay(
                rank=int(item.get("rank", 0) or 0),
                theme=item.get("theme", ""),
                parent_sector=item.get("parent_sector", ""),
                proxy_ticker=item.get("proxy_ticker", ""),
                option_proxy_ticker=item.get("option_proxy_ticker", ""),
                total_score=total_score,
                total_score_str=f"{total_score:+.1f}",
                rank_points=int(item.get("rank_points", 0) or 0),
                performance_1w_str=_pct_str(item.get("performance_1w")),
                performance_1m_str=_pct_str(item.get("performance_1m")),
                performance_6m_str=_pct_str(item.get("performance_6m")),
                flow_score_str=_signed_str(item.get("flow_score")),
                participation_str=_ratio_percent_str(item.get("participation")),
                option_asymmetry=item.get("option_asymmetry", "unavailable"),
                option_score_str=_signed_str(item.get("option_score")),
                option_summary=item.get("option_summary", ""),
                option_source=item.get("option_source", ""),
                option_data_as_of=item.get("option_data_as_of", ""),
                option_data_quality=item.get("option_data_quality", ""),
                representative_tickers=list(item.get("representative_tickers", [])),
            )
        )
    return rows


def _format_opportunities(raw: dict[str, Any]) -> list[OpportunityThemeDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        score = float(item.get("opportunity_score", 0.0))
        rows.append(
            OpportunityThemeDisplay(
                theme=item.get("theme", ""),
                parent_sector=item.get("parent_sector", ""),
                proxy_ticker=item.get("proxy_ticker", ""),
                option_proxy_ticker=item.get("option_proxy_ticker", ""),
                rank=int(item.get("rank", 0) or 0),
                opportunity_score=score,
                opportunity_score_str=f"{score:+.1f}",
                label=item.get("label", ""),
                reason=item.get("reason", ""),
                representative_tickers=list(item.get("representative_tickers", [])),
                option_asymmetry=item.get("option_asymmetry", ""),
                invalidation=item.get("invalidation", ""),
            )
        )
    return rows


def _format_detail_stages(raw: dict[str, dict[str, Any]]) -> list[StageStatusDisplay]:
    stages = []
    for key in (
        "core",
        "theme_flow",
        "volatility_sentiment",
        "credit_distortion",
        "options",
    ):
        item = raw.get(key, {}) if raw else {}
        if not item:
            continue
        stages.append(
            StageStatusDisplay(
                key=item.get("key", key),
                label=item.get("label", key),
                difficulty=item.get("difficulty", ""),
                status=item.get("status", "pending"),
                status_label=item.get("status_label", item.get("status", "pending")),
                cache_status=item.get("cache_status", ""),
                fetched_at=item.get("fetched_at", ""),
                summary=item.get("summary", ""),
                quality_warnings=list(item.get("quality_warnings", [])),
            )
        )
    return stages


def _format_flow_proxy_item(item: dict[str, Any]) -> FlowProxyItem:
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


def _price_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:,.2f}"


def _pct_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:+.2f}%"


def _signed_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:+.1f}"


def _ratio_percent_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:.0%}"


def _driver_value_str(label: str, value: Any) -> str:
    number = _optional_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}%" if label == "US10Y" else f"{number:,.2f}"


def _market_lists(
    raw_data: dict[str, Any], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    indices = _ordered_market_items(raw_data, config.get("indices", {}))
    sectors = _ordered_market_items(raw_data, config.get("sectors", {}))
    others = [
        *_ordered_market_items(raw_data, config.get("commodities", {})),
        *_ordered_market_items(raw_data, config.get("forex", {})),
        *_ordered_market_items(raw_data, config.get("crypto", {})),
    ]
    return indices, sectors, others


def _ordered_market_items(
    raw_data: dict[str, Any],
    configured: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in configured:
        data = raw_data.get(name)
        if not isinstance(data, dict):
            continue
        items.append(_market_item(name, data))
    return items


def _market_item(name: str, data: dict[str, Any]) -> dict[str, Any]:
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
