"""Portfolio dashboard validation and serialization helpers."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any


@dataclass
class HoldingInput:
    """Validated holding input from the UI."""

    ticker: str = ""
    shares: float = 0.0
    avg_cost: float | None = None
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.error


def validate_holding_input(ticker: str, shares: str, avg_cost: str) -> HoldingInput:
    """Validate and normalize a portfolio holding form input."""

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        return HoldingInput(error="ティッカーを入力してください")

    try:
        parsed_shares = float(shares) if shares else 0.0
    except ValueError:
        return HoldingInput(
            ticker=normalized_ticker, error="株数は数値で入力してください"
        )

    if not math.isfinite(parsed_shares) or parsed_shares <= 0:
        return HoldingInput(
            ticker=normalized_ticker, error="株数は0より大きい数値で入力してください"
        )

    parsed_cost = None
    if avg_cost:
        try:
            parsed_cost = float(avg_cost)
        except ValueError:
            return HoldingInput(
                ticker=normalized_ticker,
                shares=parsed_shares,
                error="取得単価は数値で入力してください",
            )
        if not math.isfinite(parsed_cost) or parsed_cost < 0:
            return HoldingInput(
                ticker=normalized_ticker,
                shares=parsed_shares,
                error="取得単価は0以上の数値で入力してください",
            )

    return HoldingInput(
        ticker=normalized_ticker,
        shares=parsed_shares,
        avg_cost=parsed_cost,
    )


def holdings_to_payload(holdings: list[Any]) -> list[dict[str, Any]]:
    """Serialize UI holding models for storage."""

    return [
        {
            "ticker": str(holding.ticker),
            "shares": float(holding.shares),
            "avg_cost": holding.avg_cost,
        }
        for holding in holdings
        if float(holding.shares) > 0
    ]


def run_portfolio_analysis(
    holdings: list[dict[str, Any]],
    market_context: Any | None = None,
) -> dict[str, Any]:
    """Run portfolio analysis and return Reflex-safe dictionaries."""

    from src.portfolio_advisor import PortfolioHolding, analyze_portfolio

    holding_objects = [
        PortfolioHolding(
            ticker=str(item["ticker"]),
            shares=float(item["shares"]),
            avg_cost=item.get("avg_cost"),
        )
        for item in holdings
        if float(item.get("shares") or 0) > 0
    ]
    result = analyze_portfolio(holding_objects, market_context=market_context)
    return serialize_analysis_result(result or {})


def serialize_analysis_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert analysis dataclasses to plain dictionaries for Reflex state."""

    safe_result: dict[str, Any] = {}
    for key, value in result.items():
        if key != "holdings":
            safe_result[key] = value
            continue

        safe_holdings = []
        for holding_data in value:
            safe_holding = {}
            for item_key, item_value in holding_data.items():
                if item_key == "technical" and item_value is not None:
                    safe_holding[item_key] = dataclasses.asdict(item_value)
                else:
                    safe_holding[item_key] = item_value
            safe_holdings.append(safe_holding)
        safe_result[key] = safe_holdings
    return safe_result
