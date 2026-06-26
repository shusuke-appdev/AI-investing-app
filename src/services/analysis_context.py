"""Structured analysis contexts shared by UI state and AI prompts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TypedDict


class ProvenanceKind(str, Enum):
    """How a displayed or AI-consumed value was produced."""

    DIRECT = "direct"
    COMPUTED = "computed"
    PROXY = "proxy"
    ESTIMATED = "estimated"
    MODEL_OUTPUT = "model_output"
    FIXED_FALLBACK = "fixed_fallback"
    STALE_CACHE = "stale_cache"
    UNAVAILABLE = "unavailable"


@dataclass
class ProvenanceItem:
    """Auditable provenance for one user-visible analysis value."""

    item_id: str
    label: str
    kind: ProvenanceKind = ProvenanceKind.UNAVAILABLE
    source: str = ""
    as_of: str = ""
    method: str = ""
    limitation: str = ""
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        return value

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ProvenanceItem:
        raw_kind = str(value.get("kind") or ProvenanceKind.UNAVAILABLE.value)
        try:
            kind = ProvenanceKind(raw_kind)
        except ValueError:
            kind = ProvenanceKind.UNAVAILABLE
        return cls(
            item_id=str(value.get("item_id") or ""),
            label=str(value.get("label") or ""),
            kind=kind,
            source=str(value.get("source") or ""),
            as_of=str(value.get("as_of") or ""),
            method=str(value.get("method") or ""),
            limitation=str(value.get("limitation") or ""),
            risk_level=str(value.get("risk_level") or "low"),
        )


@dataclass
class DataResult:
    """External or derived data retrieval status for UI and AI consumers."""

    name: str
    source: str = ""
    fetched_at: str = ""
    is_stale: bool = False
    is_partial: bool = False
    error: str = ""
    cache_status: str = "live"
    cache_age_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyRegimeContext(TypedDict, total=False):
    """Strategy-regime wire shape shared by Market UI and AI prompts."""

    key: str
    label: str
    rationale: str
    risk_budget: str
    invalidation: str
    evidence: list[str]


class TrendRankingItemContext(TypedDict, total=False):
    """One integrated trend-ranking row."""

    rank: int
    theme: str
    parent_sector: str
    proxy_ticker: str
    option_proxy_ticker: str
    option_asymmetry: str
    total_score: float
    rank_points: float
    data_quality: str


class TrendRankingContext(TypedDict, total=False):
    """Integrated trend-ranking payload."""

    items: list[TrendRankingItemContext]
    summary: str
    quality_warnings: list[str]


class SectorFlowLeaderContext(TypedDict, total=False):
    """Sector/theme flow leader payload."""

    market: str
    theme: str
    flow_score: float
    confidence: str
    continuation: str
    action: str
    evidence: str


class SectorFlowContext(TypedDict, total=False):
    """US/JP sector-flow monitor payload."""

    summary: str
    markets: dict[str, dict[str, list[SectorFlowLeaderContext]]]
    quality_warnings: list[str]


class TechnicalSummaryContext(TypedDict, total=False):
    """Stock technical summary fields consumed by UI and AI."""

    overall_signal: str
    overall_signal_display: str
    overall_score: float
    rsi: float
    rsi_signal: str
    macd_signal: str
    support_price: float | None
    resistance_price: float | None


class StockDataStatusContext(TypedDict, total=False):
    """Lightweight status summary for a stock-analysis run."""

    ticker: str
    has_profile: bool
    has_history: bool
    has_news: bool
    warnings: list[str]


class TradeSetupContextDict(TypedDict, total=False):
    """Serializable daily entry-framework payload."""

    ticker: str
    status: str
    grade: str
    score: float
    score_display: str
    summary: str
    blocked_reasons: list[str]
    warnings: list[str]


@dataclass
class OptionContext:
    """Option-market analysis inputs and retrieval status."""

    items: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    status: str = "unavailable"
    failed_tickers: list[str] = field(default_factory=list)
    source: str = ""
    fetched_at: str = ""
    is_stale: bool = False
    is_partial: bool = False
    quality_warnings: list[str] = field(default_factory=list)
    cache_status: str = "live"
    cache_age_seconds: float | None = None
    data_as_of: str = ""
    data_mode: str = ""
    resolved_expiration: str = ""
    resolved_dte: int | None = None
    expiration_policy: str = ""
    expiration_fallback_reason: str = ""
    credits_consumed: int | None = None
    credits_remaining: int | None = None
    provider_active: bool = False
    fallback_reason: str = ""
    gamma_coverage: float | None = None
    complete_status: str = "unavailable"
    horizons: list[dict[str, Any]] = field(default_factory=list)
    term_structure: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarketContext:
    """Current market state used by monitoring UI and market AI reports."""

    market_type: str
    market_data: dict[str, Any] = field(default_factory=dict)
    market_config: dict[str, Any] = field(default_factory=dict)
    options: OptionContext = field(default_factory=OptionContext)
    evaluation: dict[str, Any] = field(default_factory=dict)
    ibd_regime: dict[str, Any] = field(default_factory=dict)
    regime_playbook: dict[str, Any] = field(default_factory=dict)
    microstructure: dict[str, Any] = field(default_factory=dict)
    momentum: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    monitor: dict[str, Any] = field(default_factory=dict)
    market_distortions: dict[str, Any] = field(default_factory=dict)
    trend_ranking: TrendRankingContext = field(default_factory=dict)
    opportunity_themes: dict[str, Any] = field(default_factory=dict)
    important_levels: dict[str, Any] = field(default_factory=dict)
    market_timeframes: dict[str, Any] = field(default_factory=dict)
    strategy_regime: StrategyRegimeContext = field(default_factory=dict)
    market_driver_monitor: dict[str, Any] = field(default_factory=dict)
    japan_conditions: dict[str, Any] = field(default_factory=dict)
    sector_flow: SectorFlowContext = field(default_factory=dict)
    credit_stress: dict[str, Any] = field(default_factory=dict)
    flow_monitor: dict[str, Any] = field(default_factory=dict)
    flow_alignment: dict[str, Any] = field(default_factory=dict)
    cross_market: dict[str, Any] = field(default_factory=dict)
    volatility_regime: dict[str, Any] = field(default_factory=dict)
    sentiment: dict[str, Any] = field(default_factory=dict)
    top_risk_signposts: dict[str, Any] = field(default_factory=dict)
    fomo_scan: dict[str, Any] = field(default_factory=dict)
    detail_stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_status: list[DataResult] = field(default_factory=list)
    provenance: list[ProvenanceItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str = ""
    fetched_at: str = ""
    is_stale: bool = False
    is_partial: bool = False
    quality_warnings: list[str] = field(default_factory=list)
    cache_status: str = "live"
    cache_age_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_type": self.market_type,
            "market_data": self.market_data,
            "market_config": self.market_config,
            "options": self.options.to_dict(),
            "evaluation": self.evaluation,
            "ibd_regime": self.ibd_regime,
            "regime_playbook": self.regime_playbook,
            "microstructure": self.microstructure,
            "momentum": self.momentum,
            "monitor": self.monitor,
            "market_distortions": self.market_distortions,
            "trend_ranking": self.trend_ranking,
            "opportunity_themes": self.opportunity_themes,
            "important_levels": self.important_levels,
            "market_timeframes": self.market_timeframes,
            "strategy_regime": self.strategy_regime,
            "market_driver_monitor": self.market_driver_monitor,
            "japan_conditions": self.japan_conditions,
            "sector_flow": self.sector_flow,
            "credit_stress": self.credit_stress,
            "flow_monitor": self.flow_monitor,
            "flow_alignment": self.flow_alignment,
            "cross_market": self.cross_market,
            "volatility_regime": self.volatility_regime,
            "sentiment": self.sentiment,
            "top_risk_signposts": self.top_risk_signposts,
            "fomo_scan": self.fomo_scan,
            "detail_stages": self.detail_stages,
            "data_status": [item.to_dict() for item in self.data_status],
            "provenance": [item.to_dict() for item in self.provenance],
            "errors": self.errors,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "is_stale": self.is_stale,
            "is_partial": self.is_partial,
            "quality_warnings": self.quality_warnings,
            "cache_status": self.cache_status,
            "cache_age_seconds": self.cache_age_seconds,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> MarketContext:
        options = value.get("options") or {}
        data_status = [
            DataResult(
                name=str(item.get("name") or ""),
                source=str(item.get("source") or ""),
                fetched_at=str(item.get("fetched_at") or ""),
                is_stale=bool(item.get("is_stale", False)),
                is_partial=bool(item.get("is_partial", False)),
                error=str(item.get("error") or ""),
                cache_status=str(item.get("cache_status") or "live"),
                cache_age_seconds=_optional_float(item.get("cache_age_seconds")),
            )
            for item in value.get("data_status", [])
            if isinstance(item, dict)
        ]
        return cls(
            market_type=value.get("market_type", "US"),
            market_data=value.get("market_data") or {},
            market_config=value.get("market_config") or {},
            options=OptionContext(
                items=list(options.get("items") or []),
                error_message=str(options.get("error_message") or ""),
                status=str(options.get("status") or "unavailable"),
                failed_tickers=list(options.get("failed_tickers") or []),
                source=str(options.get("source") or ""),
                fetched_at=str(options.get("fetched_at") or ""),
                is_stale=bool(options.get("is_stale", False)),
                is_partial=bool(options.get("is_partial", False)),
                quality_warnings=list(options.get("quality_warnings") or []),
                cache_status=str(options.get("cache_status") or "live"),
                cache_age_seconds=_optional_float(options.get("cache_age_seconds")),
                data_as_of=str(options.get("data_as_of") or ""),
                data_mode=str(options.get("data_mode") or ""),
                resolved_expiration=str(options.get("resolved_expiration") or ""),
                resolved_dte=_optional_int(options.get("resolved_dte")),
                expiration_policy=str(options.get("expiration_policy") or ""),
                expiration_fallback_reason=str(
                    options.get("expiration_fallback_reason") or ""
                ),
                credits_consumed=_optional_int(options.get("credits_consumed")),
                credits_remaining=_optional_int(options.get("credits_remaining")),
                provider_active=bool(options.get("provider_active", False)),
                fallback_reason=str(options.get("fallback_reason") or ""),
                gamma_coverage=_optional_float(options.get("gamma_coverage")),
                complete_status=str(options.get("complete_status") or "unavailable"),
                horizons=list(options.get("horizons") or []),
                term_structure=dict(options.get("term_structure") or {}),
            ),
            evaluation=value.get("evaluation") or {},
            ibd_regime=value.get("ibd_regime") or {},
            regime_playbook=value.get("regime_playbook") or {},
            microstructure=value.get("microstructure") or {},
            momentum=value.get("momentum") or {},
            monitor=value.get("monitor") or {},
            market_distortions=value.get("market_distortions") or {},
            trend_ranking=value.get("trend_ranking") or {},
            opportunity_themes=value.get("opportunity_themes") or {},
            important_levels=value.get("important_levels") or {},
            market_timeframes=value.get("market_timeframes") or {},
            strategy_regime=value.get("strategy_regime") or {},
            market_driver_monitor=value.get("market_driver_monitor") or {},
            japan_conditions=value.get("japan_conditions") or {},
            sector_flow=value.get("sector_flow") or {},
            credit_stress=value.get("credit_stress") or {},
            flow_monitor=value.get("flow_monitor") or {},
            flow_alignment=value.get("flow_alignment") or {},
            cross_market=value.get("cross_market") or {},
            volatility_regime=value.get("volatility_regime") or {},
            sentiment=value.get("sentiment") or {},
            top_risk_signposts=value.get("top_risk_signposts") or {},
            fomo_scan=value.get("fomo_scan") or {},
            detail_stages=value.get("detail_stages") or {},
            data_status=data_status,
            provenance=[
                ProvenanceItem.from_mapping(item)
                for item in value.get("provenance", [])
                if isinstance(item, dict)
            ],
            errors=list(value.get("errors") or []),
            source=str(value.get("source") or ""),
            fetched_at=str(value.get("fetched_at") or ""),
            is_stale=bool(value.get("is_stale", False)),
            is_partial=bool(value.get("is_partial", False)),
            quality_warnings=list(value.get("quality_warnings") or []),
            cache_status=str(value.get("cache_status") or "live"),
            cache_age_seconds=_optional_float(value.get("cache_age_seconds")),
        )


@dataclass
class StockSignalContext:
    """Single-stock prediction context used by the stock UI and AI prompts."""

    ticker: str
    stock_info: dict[str, Any] = field(default_factory=dict)
    technical_data: TechnicalSummaryContext = field(default_factory=dict)
    smart_criteria: dict[str, Any] = field(default_factory=dict)
    probabilistic_signal: dict[str, Any] = field(default_factory=dict)
    trend_follow_diagnostics: dict[str, Any] = field(default_factory=dict)
    fomo_regime: dict[str, Any] = field(default_factory=dict)
    trade_setup: TradeSetupContextDict = field(default_factory=dict)
    sector_theme_context: dict[str, Any] = field(default_factory=dict)
    fundamental_profile: dict[str, Any] = field(default_factory=dict)
    volume_profile: dict[str, Any] = field(default_factory=dict)
    purchase_evidence: dict[str, Any] = field(default_factory=dict)
    news_headlines: list[str] = field(default_factory=list)
    news_source_status: str = ""
    news_error_reason: str = ""
    data_status: list[DataResult] = field(default_factory=list)
    provenance: list[ProvenanceItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["provenance"] = [item.to_dict() for item in self.provenance]
        return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
