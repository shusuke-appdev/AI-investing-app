"""Structured analysis contexts shared by UI state and AI prompts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class OptionContext:
    """Option-market analysis inputs and retrieval status."""

    items: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    status: str = "unavailable"
    failed_tickers: list[str] = field(default_factory=list)

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
    microstructure: dict[str, Any] = field(default_factory=dict)
    momentum: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    monitor: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_type": self.market_type,
            "market_data": self.market_data,
            "market_config": self.market_config,
            "options": self.options.to_dict(),
            "evaluation": self.evaluation,
            "microstructure": self.microstructure,
            "momentum": self.momentum,
            "monitor": self.monitor,
            "errors": self.errors,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> MarketContext:
        options = value.get("options") or {}
        return cls(
            market_type=value.get("market_type", "US"),
            market_data=value.get("market_data") or {},
            market_config=value.get("market_config") or {},
            options=OptionContext(
                items=list(options.get("items") or []),
                error_message=str(options.get("error_message") or ""),
                status=str(options.get("status") or "unavailable"),
                failed_tickers=list(options.get("failed_tickers") or []),
            ),
            evaluation=value.get("evaluation") or {},
            microstructure=value.get("microstructure") or {},
            momentum=value.get("momentum") or {},
            monitor=value.get("monitor") or {},
            errors=list(value.get("errors") or []),
        )


@dataclass
class StockSignalContext:
    """Single-stock prediction context used by the stock UI and AI prompts."""

    ticker: str
    stock_info: dict[str, Any] = field(default_factory=dict)
    technical_data: dict[str, Any] = field(default_factory=dict)
    probabilistic_signal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
