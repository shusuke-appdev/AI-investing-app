"""Structured analysis contexts shared by UI state and AI prompts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


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
    japan_conditions: dict[str, Any] = field(default_factory=dict)
    sector_flow: dict[str, Any] = field(default_factory=dict)
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
            ),
            evaluation=value.get("evaluation") or {},
            ibd_regime=value.get("ibd_regime") or {},
            regime_playbook=value.get("regime_playbook") or {},
            microstructure=value.get("microstructure") or {},
            momentum=value.get("momentum") or {},
            monitor=value.get("monitor") or {},
            market_distortions=value.get("market_distortions") or {},
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
    technical_data: dict[str, Any] = field(default_factory=dict)
    smart_criteria: dict[str, Any] = field(default_factory=dict)
    probabilistic_signal: dict[str, Any] = field(default_factory=dict)
    trend_follow_diagnostics: dict[str, Any] = field(default_factory=dict)
    fomo_regime: dict[str, Any] = field(default_factory=dict)
    trade_setup: dict[str, Any] = field(default_factory=dict)
    sector_theme_context: dict[str, Any] = field(default_factory=dict)
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
