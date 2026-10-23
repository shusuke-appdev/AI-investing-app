"""Explicit, source-linked valuation inputs; no implicit provider override."""

from __future__ import annotations

import math
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.services.equity_valuation_service import calculate_dcf, calculate_sotp


class Quantity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    value: float
    unit: Literal["currency", "shares"]
    source_ids: list[str] = Field(min_length=1)
    period_end: date
    period_start: date | None = None

    @field_validator("value", mode="before")
    @classmethod
    def not_boolean(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Financial quantity must be a number, not text or boolean")
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.period_end > date.today() or (
            self.period_start and self.period_start > self.period_end
        ):
            raise ValueError("Invalid financial period")
        return self


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str
    metric: Quantity
    metric_name: str = Field(min_length=1)
    multiple: float = Field(gt=0)
    multiple_rationale: str = Field(min_length=1)
    value_basis: Literal["enterprise", "equity"] = "enterprise"

    @field_validator("multiple", mode="before")
    @classmethod
    def numeric_multiple(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Segment multiple must be a number, not text or boolean")
        return value


class ValuationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ticker: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    method: Literal["fcff_dcf", "sotp", "residual_income", "reit_multiple"]
    cash: Quantity | None = None
    debt: Quantity | None = None
    shares: Quantity
    fcff: Quantity | None = None
    book_equity: Quantity | None = None
    reit_cashflow: Quantity | None = None
    reit_metric: Literal["ffo", "core_ffo", "affo"] = "affo"
    sustainable_roe: float = Field(default=0.10, ge=-1, le=1)
    reit_multiple: float = Field(default=14, gt=0, le=100)
    # Assumptions are explicit, not facts extracted by the model.
    growth_rate: float = Field(default=0.05, gt=-1, le=1)
    wacc: float = Field(default=0.09, gt=0, le=1)
    terminal_growth: float = Field(default=0.02, gt=-1, le=1)
    assumption_rationale: str = Field(min_length=1)
    segments: list[Segment] = Field(default_factory=list)
    all_reported_segments: list[str] = Field(default_factory=list)
    corporate_adjustment: Quantity | None = None
    noncontrolling_interest: Quantity | None = None
    nonoperating_assets: Quantity | None = None
    bridge_rationale: str = ""
    derivation: str = ""
    denominator_basis: str = "period-end ordinary shares"
    ownership_basis: str = "consolidated"
    reporting_scope: Literal["consolidated", "standalone"] = "consolidated"
    debt_scope: Literal["consolidated", "enterprise_segments_only"] = "consolidated"

    @field_validator(
        "sustainable_roe",
        "reit_multiple",
        "growth_rate",
        "wacc",
        "terminal_growth",
        mode="before",
    )
    @classmethod
    def numeric_assumptions(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                "Valuation assumption must be a number, not text or boolean"
            )
        return value

    @model_validator(mode="after")
    def coherent_inputs(self):
        if (
            (self.cash is not None and self.cash.unit != "currency")
            or (self.debt is not None and self.debt.unit != "currency")
            or self.shares.unit != "shares"
        ):
            raise ValueError(
                "Cash/debt must be base currency; shares must be share count"
            )
        if (
            any(q.value < 0 for q in (self.cash, self.debt) if q is not None)
            or self.shares.value <= 0
        ):
            raise ValueError("Invalid cash, debt or shares")
        if (
            len(
                {
                    q.period_end
                    for q in (self.cash, self.debt, self.shares)
                    if q is not None
                }
            )
            != 1
        ):
            raise ValueError("Balance sheet dates must match")
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must exceed terminal growth")
        if self.method in {"fcff_dcf", "sotp"} and (
            self.cash is None or self.debt is None
        ):
            raise ValueError("Enterprise valuation requires explicit cash and debt")
        metrics = [
            segment.metric
            for segment in self.segments
            if segment.value_basis == "enterprise"
        ]
        for segment in self.segments:
            if segment.value_basis == "equity" and (
                segment.metric.unit != "currency"
                or segment.metric.period_end != self.shares.period_end
            ):
                raise ValueError(
                    "Segment equity quantity must match the valuation date"
                )
        if self.fcff:
            metrics.append(self.fcff)
        if self.reit_cashflow:
            metrics.append(self.reit_cashflow)
        for metric in metrics:
            if metric.period_end != self.shares.period_end:
                raise ValueError(
                    "Flow and balance sheet endpoints must match; reconcile periods explicitly"
                )
            if metric.unit != "currency" or metric.period_start is None:
                raise ValueError("Flow metrics require base currency and a full period")
            if not 330 <= (metric.period_end - metric.period_start).days <= 380:
                raise ValueError(
                    "Use annual or TTM flows, not unannualized interim data"
                )
        if len({(metric.period_start, metric.period_end) for metric in metrics}) > 1:
            raise ValueError("Flow periods cannot be mixed")
        if self.corporate_adjustment and self.corporate_adjustment.unit != "currency":
            raise ValueError(
                "Corporate adjustment must be base currency enterprise value"
            )
        if (
            self.corporate_adjustment
            and self.corporate_adjustment.period_end != self.shares.period_end
        ):
            raise ValueError("Corporate adjustment date must match the balance sheet")
        if len({segment.name for segment in self.segments}) != len(self.segments):
            raise ValueError("Duplicate segment name")
        if self.book_equity and (
            self.book_equity.unit != "currency"
            or self.book_equity.period_start is not None
            or self.book_equity.period_end != self.shares.period_end
        ):
            raise ValueError("Book equity must be a matching balance-sheet quantity")
        for q in (self.noncontrolling_interest, self.nonoperating_assets):
            if q is not None and (
                q.unit != "currency"
                or q.period_start is not None
                or q.period_end != self.shares.period_end
                or q.value < 0
            ):
                raise ValueError("Invalid enterprise-to-equity bridge quantity")
        return self

    def named_quantities(self) -> list[tuple[str, Quantity]]:
        return [
            *([("cash", self.cash)] if self.cash else []),
            *([("debt", self.debt)] if self.debt else []),
            ("shares", self.shares),
            *([("fcff", self.fcff)] if self.fcff else []),
            *([("book_equity", self.book_equity)] if self.book_equity else []),
            *([(self.reit_metric, self.reit_cashflow)] if self.reit_cashflow else []),
            *(
                [("corporate_adjustment", self.corporate_adjustment)]
                if self.corporate_adjustment
                else []
            ),
            *((f"segment:{segment.name}", segment.metric) for segment in self.segments),
            *(
                [("noncontrolling_interest", self.noncontrolling_interest)]
                if self.noncontrolling_interest
                else []
            ),
            *(
                [("nonoperating_assets", self.nonoperating_assets)]
                if self.nonoperating_assets
                else []
            ),
        ]

    def quantities(self) -> list[Quantity]:
        return [quantity for _, quantity in self.named_quantities()]

    def reverse_dcf(self, price: float | None, observed_on: str | None) -> dict:
        """Invert only the source-linked DCF; keep price and accounting dates distinct."""
        result = {
            "method": self.method,
            "price": price,
            "price_observed_on": observed_on,
            "valuation_period_end": self.shares.period_end.isoformat(),
            "status": "unavailable",
            "implied_growth": None,
        }
        if self.method != "fcff_dcf":
            return {
                **result,
                "reason": "逆DCFはDCF方式のみ。別方式の倍率・ROEでは代用しません。",
            }
        if (
            self.fcff is None
            or self.cash is None
            or self.debt is None
            or not observed_on
        ):
            return {
                **result,
                "reason": "FCFF・貸借対照表・価格観測日の確認が必要です。",
            }
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(price)
            or price <= 0
        ):
            return {**result, "reason": "有効な現在価格がありません。"}
        try:
            when = date.fromisoformat(observed_on)
        except (ValueError, TypeError):
            return {**result, "reason": "価格観測日が不正です。"}
        if when > date.today():
            return {**result, "reason": "将来の価格観測日は使用しません。"}
        bridge = (self.nonoperating_assets.value if self.nonoperating_assets else 0) - (
            self.noncontrolling_interest.value if self.noncontrolling_interest else 0
        )

        def value(growth):
            return calculate_dcf(
                starting_fcf=self.fcff.value,
                growth_rate=growth,
                wacc=self.wacc,
                terminal_growth=self.terminal_growth,
                net_debt=self.debt.value - self.cash.value - bridge,
                shares=self.shares.value,
            )

        low, high = -0.20, 0.50
        lo, hi = value(low), value(high)
        if lo is None or hi is None or not lo <= price <= hi:
            return {
                **result,
                "reason": "価格が探索範囲（年率-20%〜50%）外。境界値を解として表示しません。",
            }
        for _ in range(70):
            middle = (low + high) / 2
            estimate = value(middle)
            if estimate is None:
                return {**result, "reason": "DCF計算不能。"}
            if estimate < price:
                low = middle
            else:
                high = middle
        return {
            **result,
            "status": "available",
            "implied_growth": (low + high) / 2,
            "assumptions": {
                "wacc": self.wacc,
                "terminal_growth": self.terminal_growth,
                "horizon_years": 5,
            },
            "warning": "現在価格から逆算した仮定であり、会社予測ではありません。",
        }

    def calculate(self) -> dict:
        common = {
            "currency": self.currency,
            "method": self.method,
            "readiness": "screen-grade",
            "inputs": self.model_dump(mode="json"),
            "warning": "一次資料確認は入力者の記録。倍率・成長率・割引率は仮定。",
        }
        net_debt = (
            (self.debt.value - self.cash.value)
            if self.debt is not None and self.cash is not None
            else None
        )
        bridge = (self.nonoperating_assets.value if self.nonoperating_assets else 0) - (
            self.noncontrolling_interest.value if self.noncontrolling_interest else 0
        )
        if self.method in {"residual_income", "reit_multiple"}:
            required = (
                self.book_equity
                if self.method == "residual_income"
                else self.reit_cashflow
            )
            if required is None or required.value <= 0:
                return {
                    **common,
                    "status": "unavailable",
                    "cases": [],
                    "reason": "Positive source-linked book equity or FFO/AFFO required",
                }
            cases = []
            for label, delta in [("bear", -1), ("base", 0), ("bull", 1)]:
                if self.method == "residual_income":
                    cost = self.wacc - delta * 0.01
                    roe = self.sustainable_roe + delta * 0.03
                    book = required.value / self.shares.value
                    value = (
                        book + book * (roe - cost) / (cost - self.terminal_growth)
                        if cost > self.terminal_growth
                        else None
                    )
                    assumptions = {
                        "roe": roe,
                        "cost_of_equity": cost,
                        "growth": self.terminal_growth,
                    }
                else:
                    multiple = self.reit_multiple + delta * 4
                    value = (
                        required.value / self.shares.value * multiple
                        if multiple > 0
                        else None
                    )
                    assumptions = {"multiple": multiple, "metric": self.reit_metric}
                cases.append(
                    {
                        "case": label,
                        "value": value
                        if value is not None and math.isfinite(value) and value > 0
                        else None,
                        "assumptions": assumptions,
                    }
                )
            return {
                **common,
                "status": "available"
                if all(item["value"] is not None for item in cases)
                else "partial",
                "cases": cases,
            }
        if self.method == "fcff_dcf":
            if not self.fcff:
                return {
                    **common,
                    "status": "unavailable",
                    "reason": "Explicit unlevered FCFF missing",
                }
            cases = []
            for label, delta_growth, delta_wacc in [
                ("bear", -0.03, 0.01),
                ("base", 0, 0),
                ("bull", 0.03, -0.01),
            ]:
                growth = self.growth_rate + delta_growth
                wacc = self.wacc + delta_wacc
                cases.append(
                    {
                        "case": label,
                        "growth": growth,
                        "wacc": wacc,
                        "value": calculate_dcf(
                            starting_fcf=self.fcff.value,
                            growth_rate=growth,
                            wacc=wacc,
                            terminal_growth=self.terminal_growth,
                            net_debt=net_debt - bridge,
                            shares=self.shares.value,
                        ),
                    }
                )
            return {
                **common,
                "status": "available"
                if all(case["value"] is not None for case in cases)
                else "partial",
                "cases": cases,
            }
        complete = bool(self.all_reported_segments) and set(
            self.all_reported_segments
        ) == {segment.name for segment in self.segments}
        if not complete or self.corporate_adjustment is None:
            return {
                **common,
                "status": "unavailable",
                "per_share": None,
                "reason": "Complete reported segments and explicit corporate adjustment required",
            }
        result = calculate_sotp(
            [
                {
                    "name": segment.name,
                    "metric": segment.metric.value,
                    "multiple": segment.multiple,
                }
                for segment in self.segments
            ],
            net_debt=net_debt - self.corporate_adjustment.value - bridge,
            shares=self.shares.value,
        )
        if any(s.value_basis == "equity" for s in self.segments):
            result["segment_value_sum"] = result.pop("enterprise_value", None)
        cases = []
        for label, factor in [("bear", 0.8), ("base", 1.0), ("bull", 1.2)]:
            scenario = calculate_sotp(
                [
                    {
                        "name": s.name,
                        "metric": s.metric.value,
                        "multiple": s.multiple * factor,
                    }
                    for s in self.segments
                ],
                net_debt=net_debt - self.corporate_adjustment.value - bridge,
                shares=self.shares.value,
            )
            cases.append(
                {
                    "case": label,
                    "value": scenario["per_share"],
                    "multiple_factor": factor,
                }
            )
        return {
            **common,
            **result,
            "cases": cases,
            "aggregation_basis": "sum of segment enterprise/equity values with explicitly scoped bridge",
        }
