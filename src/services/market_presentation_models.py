"""Typed display models for Market Intelligence presentation."""

from typing import Any

from pydantic import BaseModel


class MarketSignal(BaseModel):
    name: str = ""
    score: float = 0.0
    weight: float = 0.0
    rationale: str = ""
    category: str = "neutral"


class OptionHorizonSummary(BaseModel):
    key: str = ""
    label: str = ""
    dte: str = "-"
    expiration: str = ""
    iv: str = "-"
    expected_move: str = "-"
    price_range: str = "-"
    pcr_vol: str = "-"
    skew: str = "-"
    skew_label: str = "25Δ IVスキュー"
    skew_method: str = "unavailable"
    skew_status: str = "unavailable"
    skew_status_label: str = "未取得"
    skew_liquidity: str = "unknown"
    gex: str = "-"
    data_quality: str = "unavailable"


class OptionSummary(BaseModel):
    ticker: str = ""
    sentiment: str = "Neutral"
    current_price: float = 0.0
    current_price_str: str = ""
    pcr_vol: float | None = None
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
    provider_active: bool = False
    fallback_reason: str = ""
    gamma_coverage: float | None = None
    gamma_coverage_str: str = ""
    complete_status: str = "unavailable"
    complete_status_label: str = "未取得"
    horizons: list[OptionHorizonSummary] = []
    term_structure_summary: str = ""


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


class ShortForecastDisplay(BaseModel):
    ticker: str = ""
    horizon: str = ""
    status: str = "unavailable"
    status_label: str = "未算出"
    probability_up: str = "算出不可"
    range_text: str = "算出不可"
    implied_move: str = "算出不可"
    risk_level: str = "unknown"
    risk_label: str = "不明"
    direction_label: str = ""
    confidence: str = ""
    as_of: str = ""


class CompositeEvidenceDisplay(BaseModel):
    label: str = ""
    status: str = "unavailable"
    status_label: str = "未取得"
    value: str = "不明"
    threshold: str = ""
    source: str = ""
    detail: str = ""


class CompositeSentimentDisplay(BaseModel):
    ticker: str = ""
    state: str = "mixed"
    state_label: str = "材料混在"
    status: str = "unavailable"
    status_label: str = "未判定"
    risk_floor: str = "none"
    risk_label: str = "補正なし"
    summary: str = ""
    reversal_watch: bool = False
    as_of: str = ""
    evidence: list[CompositeEvidenceDisplay] = []


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
    volume_profile_summary: str = ""
    poc_str: str = ""
    value_area_str: str = ""
    support_zone_str: str = ""
    resistance_zone_str: str = ""
    proxy_note: str = ""
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
    duration_ms: int = 0
    duration_label: str = ""
    summary: str = ""
    target: str = ""
    error_message: str = ""
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


class VixSqAlertDisplay(BaseModel):
    status: str = ""
    status_label: str = "未判定"
    summary: str = ""
    score: float = 0.0
    level: str = "neutral"
    in_sq_week: bool = False
    monthly_expiration: str = ""
    vix: str = "-"
    macd_cross: str = ""
    psar_trend: str = ""


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
