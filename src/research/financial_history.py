"""Three-year/interim completeness and auditable currency/unit reconciliation."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FACTORS = {
    "currency": 1,
    "thousand": 1000,
    "million": 1000000,
    "shares": 1,
    "thousand_shares": 1000,
    "million_shares": 1000000,
    "ratio": 1,
    "percent": 0.01,
}
FLOW_METRICS = {
    "revenue",
    "operating_income",
    "net_income",
    "operating_cashflow",
    "capex",
    "fcff",
    "ffo",
    "affo",
    "core_ffo",
    "modified_ffo",
    "depreciation",
    "interest_paid",
    "income_tax",
    "working_capital_change",
    "distributions",
    "real_estate_gains",
    "wc_receivables",
    "wc_vendor_receivables",
    "wc_inventory",
    "wc_payables",
    "corporate_operating_cost",
    "core_ffo_unit_adjustment",
}
PROFILE_METRICS = {
    "general": [
        "revenue",
        "operating_income",
        "net_income",
        "operating_cashflow",
        "capex",
        "cash",
        "debt",
        "shares",
    ],
    "financial": ["net_income", "book_equity", "shares", "roe"],
    "reit": ["revenue", "ffo", "affo", "debt", "shares"],
}


class PeriodComponent(BaseModel):
    """An original flow period contributing to an auditable TTM sum."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    period_start: date
    period_end: date
    base_value: float
    source_ids: list[str] = Field(min_length=1)

    @field_validator("base_value", mode="before")
    @classmethod
    def numeric(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Flow must be a number, not text or boolean")
        return value

    @model_validator(mode="after")
    def bounds(self):
        if self.period_start >= self.period_end or self.period_end > date.today():
            raise ValueError("Invalid component period")
        if isinstance(self.base_value, bool):
            raise ValueError("Boolean is not a flow")
        return self


class FinancialFact(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: str = Field(min_length=1)
    definition: str = Field(default="", max_length=1000)
    locator: str = ""
    value: float
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit: Literal[
        "currency",
        "thousand",
        "million",
        "shares",
        "thousand_shares",
        "million_shares",
        "ratio",
        "percent",
    ]
    period_type: Literal["annual", "interim", "fiscal_half", "ttm"]
    period_end: date
    period_start: date | None = None
    consolidation: Literal["consolidated", "standalone"]
    accounting_standard: str = Field(min_length=1)
    measure_basis: Literal["gaap", "company_non_gaap", "derived"] = "gaap"
    source_ids: list[str] = Field(min_length=1)
    components: list[PeriodComponent] = Field(default_factory=list)
    ownership_basis: str = "consolidated"
    derivation: str = ""

    @field_validator("value", mode="before")
    @classmethod
    def numeric(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Financial fact must be a number, not text or boolean")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if not math.isfinite(self.value * FACTORS[self.unit]):
            raise ValueError("Unit conversion overflow")
        if self.period_end > date.today():
            raise ValueError("Future financial period")
        if self.metric in FLOW_METRICS:
            if self.period_start is None:
                raise ValueError("Flow facts require period bounds")
            span = (self.period_end - self.period_start).days
            if self.period_type in {"annual", "ttm"} and not 330 <= span <= 380:
                raise ValueError("Annual fact cannot be an interim flow")
            if self.period_type == "interim" and not 1 <= span < 330:
                raise ValueError("Invalid interim period")
            if self.period_type == "fiscal_half" and not 150 <= span <= 200:
                raise ValueError("Invalid semiannual fiscal period")
            if self.period_type == "ttm":
                parts = sorted(self.components, key=lambda p: p.period_start)
                if (
                    len(parts) < 2
                    or parts[0].period_start != self.period_start
                    or parts[-1].period_end != self.period_end
                ):
                    raise ValueError("TTM requires complete original components")
                if any(
                    a.period_end + timedelta(days=1) != b.period_start
                    for a, b in zip(parts, parts[1:], strict=False)
                ):
                    raise ValueError("TTM periods overlap or contain gaps")
                if not math.isclose(
                    sum(p.base_value for p in parts),
                    self.base_value,
                    rel_tol=1e-9,
                    abs_tol=1e-6,
                ):
                    raise ValueError("TTM does not reconcile with component sum")
                if set(self.source_ids) != {s for p in parts for s in p.source_ids}:
                    raise ValueError("TTM source union mismatch")
            elif self.components:
                raise ValueError("Only TTM flows have aggregation components")
        elif self.period_start is not None:
            raise ValueError("Balance/ratio fact has no flow period")
        elif self.components:
            raise ValueError("Balance/ratio facts cannot have flow components")
        if self.metric == "shares" and self.unit not in {
            "shares",
            "thousand_shares",
            "million_shares",
        }:
            raise ValueError("Shares unit mismatch")
        if self.metric == "roe" and self.unit not in {"ratio", "percent"}:
            raise ValueError("ROE needs ratio/percent units")
        if self.metric not in {"shares", "roe"} and self.unit not in {
            "currency",
            "thousand",
            "million",
        }:
            raise ValueError("Monetary metric unit mismatch")
        return self

    @property
    def base_value(self) -> float:
        return self.value * FACTORS[self.unit]


class FinancialHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    profile: Literal["general", "financial", "reit"] = "general"
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    expected_annual_ends: list[date] = Field(min_length=3, max_length=3)
    reporting_scope: Literal["consolidated", "standalone"] = "consolidated"
    latest_interim_end: date | None = None
    expected_periods: list[dict[str, str]] = Field(default_factory=list)
    facts: list[FinancialFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def comparable(self):
        ends = sorted(self.expected_annual_ends)
        if len(set(ends)) != 3 or any(
            not 330 <= (b - a).days <= 400 for a, b in zip(ends, ends[1:], strict=False)
        ):
            raise ValueError("Three consecutive fiscal years required")
        if not self.expected_periods and (
            self.latest_interim_end is None
            or self.latest_interim_end <= ends[-1]
            or self.latest_interim_end > date.today()
        ):
            raise ValueError("Latest interim must follow the latest annual period")
        identities = [
            (item.metric, item.period_type, item.period_end, item.consolidation)
            for item in self.facts
        ]
        if len(identities) != len(set(identities)):
            raise ValueError(
                "Conflicting duplicate fact; reconcile instead of overwriting"
            )
        if any(item.currency != self.currency for item in self.facts):
            raise ValueError("Mixed currencies require explicit reconciliation")
        if len({item.accounting_standard for item in self.facts}) > 1:
            raise ValueError("Mixed accounting standards require reconciliation")
        if self.expected_periods:
            declared = set()
            for period in self.expected_periods:
                if set(period) != {"kind", "end"} or period["kind"] not in {
                    "annual",
                    "interim",
                    "fiscal_half",
                    "ttm",
                }:
                    raise ValueError("Invalid declared period")
                end = date.fromisoformat(period["end"])
                if end > date.today() or (period["kind"], end) in declared:
                    raise ValueError("Future or duplicate declared period")
                declared.add((period["kind"], end))
            if not {
                (kind, end)
                for kind in ("annual", "ttm")
                for end in ends
                if (kind, end) in declared
            } or any(
                not any((kind, end) in declared for kind in ("annual", "ttm"))
                for end in ends
            ):
                raise ValueError("Three annual or TTM comparison periods required")
        for item in self.facts:
            if self.expected_periods:
                if (item.period_type, item.period_end) not in declared:
                    raise ValueError("Unexpected declared fiscal period")
                continue
            expected = (
                ends if item.period_type == "annual" else [self.latest_interim_end]
            )
            if item.period_end not in expected:
                raise ValueError("Unexpected fiscal period")
        return self

    def completeness(self) -> dict:
        found = {
            (item.metric, item.period_type, item.period_end)
            for item in self.facts
            if item.consolidation == self.reporting_scope
        }
        required = PROFILE_METRICS[self.profile]
        periods = (
            [(p["kind"], date.fromisoformat(p["end"])) for p in self.expected_periods]
            if self.expected_periods
            else [("annual", end) for end in sorted(self.expected_annual_ends)]
            + [("interim", self.latest_interim_end)]
        )
        missing = [
            f"{kind} {end} {metric}"
            for kind, end in periods
            for metric in required
            if (metric, kind, end) not in found
        ]
        return {
            "status": "partial" if missing else "available",
            "profile": self.profile,
            "reporting_scope": self.reporting_scope,
            "expected_annual_ends": [
                end.isoformat() for end in self.expected_annual_ends
            ],
            "latest_interim_end": self.latest_interim_end.isoformat()
            if self.latest_interim_end
            else None,
            "expected_periods": self.expected_periods,
            "missing": missing,
            "facts": [
                {**item.model_dump(mode="json"), "base_value": item.base_value}
                for item in self.facts
            ],
            "warning": "集計単位・期間の照合であり、内容の真実性や最新資料の網羅性は原資料で確認。",
        }
